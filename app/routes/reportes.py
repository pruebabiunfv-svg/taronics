"""Certificados PDF + QR, revisión/aprobación, verificación y Gmail SMTP."""
from __future__ import annotations
import hashlib
import secrets
import smtplib
import sqlite3

from flask import Blueprint, request, jsonify, current_app, send_file, session, url_for, render_template
from app.models.auth import login_required, roles_required, log_action, login_user
from app.models.database import get_db, query, execute, rows_to_list
from app.services.certificates import load_certificate, certificate_snapshot, status, build_pdf, sign_pdf_if_configured
from app.services.mailer import send_pdf_mail
from io import BytesIO

reportes_bp = Blueprint('reportes', __name__)


def _err(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


def _log_review(conn, did, user_id, action, comment='', digest=None):
    conn.execute('INSERT INTO historial_aprobaciones(diagnostico_id,usuario_id,accion,comentario,huella) VALUES(?,?,?,?,?)',
                 (did, user_id, action, comment, digest))
    conn.execute('INSERT INTO audit_log(usuario_id,accion,modulo,objeto,detalle,ip) VALUES(?,?,?,?,?,?)',
                 (user_id, action.upper(), 'Aprobaciones', str(did), comment, request.remote_addr))


def _send_payload(did):
    diag = load_certificate(did)
    if diag and session.get('user_rol') == 'tecnico' and diag['tecnico_id'] != session.get('user_id'):
        return None, _err('Sin permiso para descargar otro expediente.', 403)
    if not diag:
        return None, _err('Diagnóstico no encontrado.', 404)
    valid, reason = status(diag, current_app.config['UPLOAD_FOLDER'])
    if not valid:
        return None, _err(reason, 409)
    base = current_app.config.get('PUBLIC_BASE_URL', '').rstrip('/')
    if not base:
        if not current_app.debug:
            return None, _err('Configure PUBLIC_BASE_URL con la URL HTTPS pública.', 503)
        base = request.url_root.rstrip('/')
    if not base.startswith('https://') and not current_app.debug:
        return None, _err('PUBLIC_BASE_URL debe usar HTTPS en producción.', 503)
    verification_url = base + url_for('reportes.verificar', token=diag['token_verificacion'])
    _, lecturas = certificate_snapshot(diag, current_app.config['UPLOAD_FOLDER'])
    crypto = bool(current_app.config.get('PDF_SIGN_P12_PATH'))
    try:
        pdf = build_pdf(diag, lecturas, verification_url, signed_label=crypto)
        pdf = sign_pdf_if_configured(
            pdf,
            p12_path=current_app.config.get('PDF_SIGN_P12_PATH', ''),
            p12_password=current_app.config.get('PDF_SIGN_P12_PASSWORD', ''),
        )
    except Exception:
        current_app.logger.exception('Error interno al construir/firma PDF certificado id=%s', did)
        return None, _err('No se pudo generar el PDF. Revise la configuración de firma.', 503)
    return (diag, pdf), None


@reportes_bp.route('/api/diagnosticos/<int:did>/revision', methods=['POST'])
@login_required
def request_review(did):
    d = load_certificate(did)
    if not d:
        return _err('Diagnóstico no encontrado.', 404)
    if session['user_id'] != d['tecnico_id'] and session['user_rol'] not in ('admin', 'jefe'):
        return _err('Solo su técnico o un responsable puede solicitar revisión.', 403)
    if d['estado_aprobacion'] not in ('borrador','rechazado'):
        return _err('El expediente no se puede enviar nuevamente.', 409)
    if str(d.get('equipo_codigo') or '').startswith('DEMO-') or str(d.get('patron_codigo') or '').startswith('DEMO-'):
        return _err('Los equipos y patrones DEMO son ficticios. Sustitúyalos por instrumentos reales y verificados antes de emitir un certificado.', 409)
    if d['resultado'] not in ('conforme','no_conforme','observacion') or not d['dictamen'] or not d['fecha_fin']:
        return _err('Guarde el resultado y dictamen final antes de solicitar aprobación.', 400)
    if not query('SELECT 1 FROM lecturas WHERE diagnostico_id=? LIMIT 1',(did,),one=True):
        return _err('Registre al menos una lectura de calibración.', 400)
    # El patrón utilizado no puede tener calibración vencida al realizarse el servicio.
    if d['patron_id'] and d['patron_vencimiento'] and d['fecha_fin'][:10] > d['patron_vencimiento'][:10]:
        return _err('El patrón registra un vencimiento anterior a la fecha de servicio.',409)
    with get_db() as db:
        cur = db.execute("""UPDATE diagnosticos SET estado_aprobacion='en_revision', solicitado_por=?,
            solicitado_en=datetime('now'), aprobado_por=NULL, aprobado_en=NULL,
            huella_aprobada=NULL,token_verificacion=NULL WHERE id=? AND estado_aprobacion IN ('borrador','rechazado')""",
            (session['user_id'], did))
        if cur.rowcount != 1:
            return _err('El expediente cambió de estado.', 409)
        _log_review(db,did,session['user_id'],'solicitar_revision')
        db.execute('''INSERT INTO alertas(tipo,titulo,mensaje,entidad,entidad_id,destinatario_rol)
            VALUES('info',?,?, 'diagnostico',?,'revisor')''',
            ('Certificado pendiente de aprobación', f"Revisar: {d['n_certificado']}", did))
    return jsonify({'ok':True,'estado':'en_revision'})


@reportes_bp.route('/api/diagnosticos/<int:did>/aprobacion', methods=['POST'])
@login_required
@roles_required('admin','jefe')
def approve_diagnostic(did):
    data = request.get_json(silent=True) or {}
    action = data.get('accion')
    comment = str(data.get('comentario') or '').strip()[:1000]
    if action not in ('aprobar','rechazar'):
        return _err('Indique aprobar o rechazar.')
    password = data.get('password','')
    # Reautenticación de responsable antes de firmar aprobación.
    approver, error = login_user(session.get('user_email',''), password)
    if error or not approver or approver['id'] != session['user_id']:
        return _err('Contraseña del responsable incorrecta.', 403)
    d = load_certificate(did)
    if not d: return _err('Diagnóstico no encontrado.',404)
    if d['estado_aprobacion'] != 'en_revision':
        return _err('El diagnóstico debe estar en revisión.',409)
    if d['tecnico_id'] == session['user_id']:
        return _err('Por separación de funciones, el autor no puede aprobar su propio expediente.',403)
    if action == 'rechazar' and len(comment) < 5:
        return _err('Indique el motivo del rechazo (mínimo cinco caracteres).')
    try:
        digest = certificate_snapshot(d,current_app.config['UPLOAD_FOLDER'])[0] if action == 'aprobar' else None
    except (OSError,ValueError):
        return _err('El expediente tiene fotografías faltantes o ilegibles; no se puede aprobar.',409)
    token = secrets.token_urlsafe(32) if action=='aprobar' else None
    with get_db() as db:
        if action=='aprobar':
            cur=db.execute("""UPDATE diagnosticos SET estado_aprobacion='aprobado',
                aprobado_por=?,aprobado_en=strftime('%Y-%m-%d %H:%M:%S','now'),huella_aprobada=?,
                token_verificacion=?,comentario_aprobacion=?
                WHERE id=? AND estado_aprobacion='en_revision'""",(session['user_id'],digest,token,comment,did))
        else:
            cur=db.execute("""UPDATE diagnosticos SET estado_aprobacion='rechazado',
                aprobado_por=NULL, aprobado_en=NULL, huella_aprobada=NULL,
                token_verificacion=NULL,comentario_aprobacion=?
                WHERE id=? AND estado_aprobacion='en_revision'""",(comment,did))
        if cur.rowcount != 1: return _err('Estado modificado por otro usuario.',409)
        _log_review(db,did,session['user_id'],action,comment,digest)
        db.execute("UPDATE alertas SET resuelta=1 WHERE entidad='diagnostico' AND entidad_id=? AND destinatario_rol='revisor'",(did,))
        db.execute('''INSERT INTO alertas(tipo,titulo,mensaje,entidad,entidad_id,destinatario_id)
            VALUES('info',?,?,?,?,?)''',
            ('Certificado aprobado' if action == 'aprobar' else 'Certificado devuelto',
             f"{d['n_certificado']}: " + ('Ya puedes descargar el PDF.' if action == 'aprobar' else 'Revisa el motivo y corrige el expediente.'),
             'diagnostico',did,d['tecnico_id']))
    return jsonify({'ok':True,'estado':'aprobado' if action=='aprobar' else 'rechazado'})


@reportes_bp.route('/api/diagnosticos/<int:did>/aprobaciones')
@login_required
def approval_history(did):
    info=query('SELECT tecnico_id FROM diagnosticos WHERE id=?',(did,),one=True)
    if not info or (session.get('user_rol')=='tecnico' and info['tecnico_id']!=session.get('user_id')):
        return _err('Historial no disponible.',403)
    entries = rows_to_list(query('''SELECT h.accion,h.comentario,h.fecha,u.nombre responsable
        FROM historial_aprobaciones h JOIN usuarios u ON u.id=h.usuario_id
        WHERE h.diagnostico_id=? ORDER BY h.id DESC''',(did,)))
    return jsonify({'ok':True,'historial':entries})


@reportes_bp.route('/api/diagnosticos/<int:did>/pdf')
@login_required
def get_pdf(did):
    payload, error = _send_payload(did)
    if error: return error
    diag, data = payload
    log_action('Certificados','DESCARGAR_PDF',diag['n_certificado'])
    response = send_file(BytesIO(data), mimetype='application/pdf', as_attachment=True,
                         download_name=f"{diag['n_certificado']}.pdf")
    response.headers['Cache-Control']='private, no-store'
    return response


@reportes_bp.route('/verificar/<token>')
def verificar(token):
    """El QR indica estado, sin exponer datos del cliente ni permitir descargar el PDF."""
    if len(token) > 80 or not token:
        return render_template('public/verificar.html',valid=False,reason='Enlace no válido.'),404
    row=query('SELECT id FROM diagnosticos WHERE token_verificacion=?',(token,),one=True)
    if not row:
        return render_template('public/verificar.html',valid=False,reason='Certificado no encontrado.'),404
    diag=load_certificate(row['id'])
    ok, detail=status(diag,current_app.config['UPLOAD_FOLDER'])
    return render_template('public/verificar.html',valid=ok,reason=detail,
                           numero=diag['n_certificado'],fecha=diag['aprobado_en'],
                           estado=diag['estado_aprobacion']),200 if ok else 409


@reportes_bp.route('/api/diagnosticos/<int:did>/email',methods=['POST'])
@login_required
@roles_required('admin','jefe')
def send_email(did):
    payload, error = _send_payload(did)
    if error: return error
    diag, pdf = payload
    data = request.get_json(silent=True) or {}
    tos = (data.get('to') or '').strip()
    ccs = (data.get('cc') or '').strip()
    try:
        recipients = send_pdf_mail(current_app.config,to=tos,cc=ccs,
                         subject=(data.get('subject') or f"Certificado {diag['n_certificado']}"),
                         body=(data.get('body') or 'Adjuntamos su certificado aprobado.'),
                         pdf_data=pdf,filename=f"{diag['n_certificado']}.pdf")
    except (RuntimeError,ValueError) as exc:
        return _err(str(exc),503 if isinstance(exc,RuntimeError) else 400)
    except (smtplib.SMTPException,OSError) as exc:
        current_app.logger.warning('Error SMTP para certificado id=%s: %s',did,type(exc).__name__)
        return _err('Gmail rechazó o no completó la entrega. Revise la cuenta, el acceso SMTP y la red.',502)
    pdf_sha = hashlib.sha256(pdf).hexdigest()
    execute('INSERT INTO historial_correos(diagnostico_id,usuario_id,destinatarios,estado,pdf_sha256) VALUES(?,?,?,?,?)',
            (did,session['user_id'],', '.join(recipients),'aceptado_smtp',pdf_sha))
    execute('UPDATE diagnosticos SET enviado_email=1 WHERE id=?',(did,))
    log_action('Email','ACEPTADO_SMTP',diag['n_certificado'],f"Destinatarios: {', '.join(recipients)}")
    return jsonify({'ok':True,'message':'Mensaje aceptado por el servidor SMTP de Gmail. La entrega final depende del destinatario.'})


@reportes_bp.route('/api/alertas')
@login_required
def list_alertas():
    uid=session['user_id']
    rol=session['user_rol']
    rows=rows_to_list(query('''SELECT a.id,a.tipo,a.titulo,a.mensaje,a.entidad,a.entidad_id,a.creado,
        CASE WHEN a.resuelta=1 OR l.alerta_id IS NOT NULL THEN 1 ELSE 0 END resuelta
        FROM alertas a LEFT JOIN alertas_leidas l ON l.alerta_id=a.id AND l.usuario_id=?
        WHERE (a.destinatario_id IS NULL OR a.destinatario_id=?)
          AND (a.destinatario_rol IS NULL OR a.destinatario_rol=?
               OR (a.destinatario_rol='revisor' AND ? IN ('admin','jefe')))
        ORDER BY resuelta ASC,a.creado DESC LIMIT 100''',(uid,uid,rol,rol)))
    return jsonify(rows)

@reportes_bp.route('/api/alertas/<int:aid>/resolver',methods=['POST'])
@login_required
def resolver_alerta(aid):
    visible=query('''SELECT id FROM alertas WHERE id=? AND
        (destinatario_id IS NULL OR destinatario_id=?) AND
        (destinatario_rol IS NULL OR destinatario_rol=? OR
            (destinatario_rol='revisor' AND ? IN ('admin','jefe')))''',
        (aid,session['user_id'],session['user_rol'],session['user_rol']),one=True)
    if not visible:
        return _err('Notificación no disponible.',404)
    execute('INSERT OR IGNORE INTO alertas_leidas(usuario_id,alerta_id) VALUES(?,?)',
            (session['user_id'],aid))
    return jsonify({'ok':True})

@reportes_bp.route('/api/audit')
@login_required
@roles_required('admin','jefe')
def audit_log():
    return jsonify(rows_to_list(query('''SELECT a.*,u.nombre usuario_nombre FROM audit_log a
        LEFT JOIN usuarios u ON u.id=a.usuario_id ORDER BY a.ts DESC LIMIT 50''')))

@reportes_bp.route('/api/estadisticas')
@login_required
@roles_required('admin','jefe')
def estadisticas():
    return jsonify({'por_resultado':rows_to_list(query('SELECT resultado,COUNT(*) total FROM diagnosticos GROUP BY resultado')),
        'por_mes':rows_to_list(query("SELECT strftime('%Y-%m',creado) mes,COUNT(*) total FROM diagnosticos GROUP BY mes ORDER BY mes DESC LIMIT 12")),
        'por_magnitud':rows_to_list(query('SELECT magnitud,COUNT(*) total FROM diagnosticos GROUP BY magnitud'))})
