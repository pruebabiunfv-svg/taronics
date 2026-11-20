"""Alta de usuarios: abierta solo en desarrollo o con código de invitación de empresa."""
import hmac
from flask import Blueprint, render_template, request, redirect, url_for, current_app, session
from app.models.database import execute, query
from app.models.auth import hash_password

registro_bp = Blueprint('registro', __name__)

@registro_bp.route('/registro', methods=['GET','POST'])
def registro():
    error = None
    if session.get('user_id'):
        return redirect(url_for('dashboard.index'))
    enabled = current_app.config['ALLOW_PUBLIC_REGISTRATION']
    if request.method == 'POST':
        if not enabled:
            return render_template('auth/register.html', error='El alta pública está cerrada. Contacte a su administrador.'),403
        name = (request.form.get('usuario') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        password2 = request.form.get('password_confirm') or ''
        invitation = (request.form.get('codigo') or '').strip()
        expected_code = current_app.config['REGISTRATION_CODE']
        if expected_code and not hmac.compare_digest(invitation, expected_code):
            error = 'Código de invitación no válido.'
        elif len(name) < 3 or len(name) > 120 or '@' not in email or len(email) > 254:
            error = 'Revisa el nombre y el correo electrónico.'
        elif len(password) < 12:
            error = 'La contraseña debe tener al menos 12 caracteres.'
        elif password != password2:
            error = 'Las contraseñas no coinciden.'
        elif query('SELECT id FROM usuarios WHERE email=?',(email,),one=True):
            error = 'Ya existe una cuenta con ese correo.'
        else:
            execute('INSERT INTO usuarios(nombre,email,password,rol,laboratorio) VALUES(?,?,?,?,?)',
                    (name,email,hash_password(password),'tecnico',''))
            return redirect(url_for('auth.login',registered='1'))
    return render_template('auth/register.html',error=error)
