"""Autenticación y cierre de sesión."""
from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify
from app.models.auth import login_user, log_action
from app.models.login_rate_limit import is_locked, record_failure, clear_attempts

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        data = request.get_json(silent=True) if request.is_json else request.form
        data = data or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        if is_locked(email):
            message = 'Demasiados intentos. Espera 15 minutos antes de volver a intentarlo.'
            if request.is_json:
                return jsonify({'ok':False,'error':message}),429
            return render_template('auth/login.html',error=message),429
        user, err = login_user(email, password)
        if err:
            record_failure(email)
            if request.is_json:
                return jsonify({'ok':False,'error':'Correo o contraseña incorrectos.'}),401
            return render_template('auth/login.html',error='Correo o contraseña incorrectos.'),401
        clear_attempts(email)
        session.clear()   # rota la sesión y el token CSRF previo al acceso
        session.permanent = True
        session.update(user_id=user['id'], user_nombre=user['nombre'], user_email=user['email'],
                       user_rol=user['rol'])
        log_action('Auth','LOGIN', user['email'])
        if request.is_json:
            return jsonify({'ok':True,'redirect':url_for('dashboard.index')})
        return redirect(url_for('dashboard.index'))
    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        log_action('Auth','LOGOUT',session.get('user_email',''))
    session.clear()
    return redirect(url_for('auth.login'))
