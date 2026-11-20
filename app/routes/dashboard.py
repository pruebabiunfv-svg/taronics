"""
Dashboard Blueprint
"""
from flask import Blueprint, render_template, session, jsonify
from app.models.auth import login_required, roles_required
from app.models.database import query, rows_to_list

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
@login_required
def index():
    is_manager = session.get('user_rol') in ('admin', 'jefe')
    return render_template('platform/app.html',
                           user=session,
                           panel='dashboard' if is_manager else 'mi-inicio')


@dashboard_bp.route('/api/dashboard/stats')
@login_required
@roles_required('admin', 'jefe')
def stats():
    diag_mes   = query("SELECT COUNT(*) c FROM diagnosticos WHERE strftime('%Y-%m', creado)=strftime('%Y-%m','now')", one=True)['c']
    conformes  = query("SELECT COUNT(*) c FROM diagnosticos WHERE resultado='conforme'", one=True)['c']
    no_conf    = query("SELECT COUNT(*) c FROM diagnosticos WHERE resultado='no_conforme'", one=True)['c']
    alertas    = query("SELECT COUNT(*) c FROM alertas WHERE resuelta=0", one=True)['c']

    por_magnitud = rows_to_list(query("""
        SELECT magnitud, COUNT(*) total FROM diagnosticos GROUP BY magnitud ORDER BY total DESC
    """))

    recientes = rows_to_list(query("""
        SELECT d.n_certificado, d.resultado, d.fecha_fin, d.magnitud,
               e.codigo as equipo_codigo, e.descripcion as equipo_desc,
               u.nombre as tecnico
        FROM diagnosticos d
        JOIN equipos e ON e.id=d.equipo_id
        JOIN usuarios u ON u.id=d.tecnico_id
        ORDER BY d.creado DESC LIMIT 5
    """))

    vencimientos = rows_to_list(query("""
        SELECT e.codigo, e.descripcion, e.magnitud,
               MAX(d.prox_calibracion) as prox
        FROM equipos e
        LEFT JOIN diagnosticos d ON d.equipo_id=e.id
        WHERE e.activo=1
        GROUP BY e.id
        ORDER BY prox ASC LIMIT 6
    """))

    return jsonify({
        'diag_mes': diag_mes,
        'conformes': conformes,
        'no_conformes': no_conf,
        'alertas': alertas,
        'por_magnitud': por_magnitud,
        'recientes': recientes,
        'vencimientos': vencimientos,
    })


@dashboard_bp.route('/api/mi-resumen')
@login_required
@roles_required('tecnico')
def mi_resumen():
    """Datos del técnico conectado; no exponer indicadores generales."""
    uid = session['user_id']
    resumen = query("""SELECT COUNT(*) total,
         SUM(CASE WHEN estado_aprobacion='en_revision' THEN 1 ELSE 0 END) en_revision,
         SUM(CASE WHEN estado_aprobacion='aprobado' THEN 1 ELSE 0 END) aprobados,
         SUM(CASE WHEN estado_aprobacion='rechazado' THEN 1 ELSE 0 END) devueltos
         FROM diagnosticos WHERE tecnico_id=?""", (uid,), one=True)
    recientes = rows_to_list(query("""SELECT d.id,d.n_certificado,d.estado_aprobacion,
        d.resultado,d.creado,e.codigo equipo_codigo,e.descripcion equipo_desc
        FROM diagnosticos d JOIN equipos e ON e.id=d.equipo_id
        WHERE d.tecnico_id=? ORDER BY d.creado DESC LIMIT 6""", (uid,)))
    return jsonify({'resumen': dict(resumen), 'recientes': recientes})
