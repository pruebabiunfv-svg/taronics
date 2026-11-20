"""
Auth helper functions
"""
import hashlib
import hmac
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import session, redirect, url_for, jsonify, request
from app.models.database import query, execute, row_to_dict


def hash_password(pw: str) -> str:
    return generate_password_hash(pw)


def get_user_by_email(email: str):
    row = query("SELECT * FROM usuarios WHERE email=? AND activo=1", (email,), one=True)
    return row_to_dict(row)


def get_user_by_id(uid: int):
    row = query("SELECT * FROM usuarios WHERE id=?", (uid,), one=True)
    return row_to_dict(row)


def login_user(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None, "Usuario no encontrado"
    stored = user['password']
    # Compatibilidad con las contraseñas SHA-256 de la versión anterior.
    if len(stored) == 64 and all(c in '0123456789abcdef' for c in stored.lower()):
        valid = hmac.compare_digest(stored, hashlib.sha256(password.encode()).hexdigest())
        if valid:
            execute("UPDATE usuarios SET password=? WHERE id=?", (hash_password(password), user['id']))
    else:
        valid = check_password_hash(stored, password)
    if not valid:
        return None, "Contraseña incorrecta"
    return user, None


def log_action(modulo, accion, objeto='', detalle=''):
    uid = session.get('user_id')
    ip  = request.remote_addr
    execute(
        "INSERT INTO audit_log(usuario_id,accion,modulo,objeto,detalle,ip) VALUES(?,?,?,?,?,?)",
        (uid, accion, modulo, objeto, detalle, ip)
    )


# ── Decorators

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or not (user := get_user_by_id(session.get('user_id'))) or not user['activo']:
            session.clear()
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('auth.login'))
        # Refrescar privilegios si un administrador modificó el rol en la base de datos.
        session['user_rol'] = user['rol']
        return f(*args, **kwargs)
    return decorated


def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('user_rol') not in roles:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Sin permiso'}), 403
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated
    return decorator
