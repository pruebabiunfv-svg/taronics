"""
General API Blueprint — patrones, usuarios, búsqueda global
"""
from flask import Blueprint, request, jsonify, session
from app.models.auth import login_required, roles_required, log_action
from app.models.database import query, execute, rows_to_list, row_to_dict

api_bp = Blueprint('api', __name__)


@api_bp.route('/patrones')
@login_required
def list_patrones():
    rows = rows_to_list(query(
        "SELECT * FROM patrones WHERE activo=1 ORDER BY codigo"))
    return jsonify(rows)


@api_bp.route('/patrones', methods=['POST'])
@login_required
@roles_required('admin','jefe')
def create_patron():
    d = request.get_json()
    pid = execute("""
        INSERT INTO patrones(codigo,descripcion,fabricante,modelo,serie,magnitud,
            incertidumbre,n_certificado,trazabilidad,vencimiento)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (d.get('codigo'), d.get('descripcion'), d.get('fabricante'), d.get('modelo'),
          d.get('serie'), d.get('magnitud'), d.get('incertidumbre'),
          d.get('n_certificado'), d.get('trazabilidad'), d.get('vencimiento')))
    log_action('Patrones', 'CREAR', d.get('codigo'))
    return jsonify({'ok': True, 'id': pid})


@api_bp.route('/usuarios/me')
@login_required
def me():
    return jsonify({
        'id':          session.get('user_id'),
        'nombre':      session.get('user_nombre'),
        'email':       session.get('user_email'),
        'rol':         session.get('user_rol'),
    })


@api_bp.route('/usuarios')
@login_required
@roles_required('admin')
def list_usuarios():
    rows = rows_to_list(query(
        "SELECT id,nombre,email,rol,activo,creado FROM usuarios ORDER BY activo DESC,nombre"))
    return jsonify(rows)


@api_bp.route('/search')
@login_required
def global_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    pat = f'%{q}%'
    results = []

    # Equipment
    for r in rows_to_list(query(
            "SELECT id,'equipo' tipo,codigo,descripcion FROM equipos WHERE activo=1 AND (codigo LIKE ? OR descripcion LIKE ?) LIMIT 5",
            (pat, pat))):
        results.append(r)

    # Diagnósticos propios para técnicos; los revisores pueden buscar todos.
    if session.get('user_rol') == 'tecnico':
        diag_sql = "SELECT id,'diagnostico' tipo,n_certificado as codigo,magnitud as descripcion FROM diagnosticos WHERE n_certificado LIKE ? AND tecnico_id=? LIMIT 5"
        diag_params = (pat,session['user_id'])
    else:
        diag_sql = "SELECT id,'diagnostico' tipo,n_certificado as codigo,magnitud as descripcion FROM diagnosticos WHERE n_certificado LIKE ? LIMIT 5"
        diag_params = (pat,)
    results.extend(rows_to_list(query(diag_sql,diag_params)))

    # Las cuentas técnicas no consultan la cartera de clientes completa.
    if session.get('user_rol') in ('admin','jefe'):
        results.extend(rows_to_list(query(
            "SELECT id,'cliente' tipo,nombre as codigo,ruc as descripcion FROM clientes WHERE activo=1 AND (nombre LIKE ? OR ruc LIKE ?) LIMIT 3",
            (pat, pat))))

    return jsonify(results)


@api_bp.route('/usuarios', methods=['POST'])
@login_required
@roles_required('admin')
def create_usuario():
    """Altas controladas por administrador; no existen sedes."""
    from app.models.auth import hash_password
    from sqlite3 import IntegrityError
    data = request.get_json(silent=True) or {}
    nombre = str(data.get('nombre') or '').strip()
    email = str(data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    rol = data.get('rol')
    if len(nombre) < 3 or len(nombre) > 120 or '@' not in email or len(email) > 254:
        return jsonify({'ok':False,'error':'Nombre o correo inválidos.'}),400
    if rol not in ('tecnico','jefe','admin'):
        return jsonify({'ok':False,'error':'Perfil no permitido.'}),400
    if len(password) < 12:
        return jsonify({'ok':False,'error':'La contraseña debe tener al menos 12 caracteres.'}),400
    try:
        uid=execute('INSERT INTO usuarios(nombre,email,password,rol,laboratorio) VALUES(?,?,?,?,?)',
                    (nombre,email,hash_password(password),rol,''))
    except IntegrityError:
        return jsonify({'ok':False,'error':'El correo ya está registrado.'}),409
    log_action('Usuarios','CREAR',email,f'Rol: {rol}')
    return jsonify({'ok':True,'id':uid}),201


@api_bp.route('/usuarios/<int:uid>', methods=['PATCH'])
@login_required
@roles_required('admin')
def manage_usuario(uid):
    """Cambios de perfil y activación, sin poder bloquearse a uno mismo."""
    data = request.get_json(silent=True) or {}
    target = row_to_dict(query('SELECT id,email,rol,activo FROM usuarios WHERE id=?',(uid,),one=True))
    if not target:
        return jsonify({'ok':False,'error':'Usuario no encontrado.'}),404
    rol = data.get('rol',target['rol'])
    activo = data.get('activo',bool(target['activo']))
    if rol not in ('admin','jefe','tecnico') or type(activo) is not bool:
        return jsonify({'ok':False,'error':'Rol o estado inválido.'}),400
    if uid == session['user_id'] and (rol != 'admin' or not activo):
        return jsonify({'ok':False,'error':'No puede quitarse el acceso administrativo.'}),409
    execute('UPDATE usuarios SET rol=?,activo=? WHERE id=?',(rol,int(activo),uid))
    log_action('Usuarios','ACTUALIZAR',target['email'],f'Rol: {rol}; activo: {activo}')
    return jsonify({'ok':True})
