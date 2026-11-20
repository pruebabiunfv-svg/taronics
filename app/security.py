"""Seguridad transversal: CSRF, encabezados y sesiones."""
import secrets
import hmac
from flask import request, session, jsonify, abort, current_app

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

def csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_urlsafe(32)
    return session['_csrf_token']

def setup_security(app):
    @app.context_processor
    def template_context():
        return {'csrf_token': csrf_token, 'registration_enabled': app.config['ALLOW_PUBLIC_REGISTRATION']}

    @app.before_request
    def verify_csrf():
        if request.method not in WRITE_METHODS:
            return
        supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
        expected = csrf_token()
        if not supplied or not hmac.compare_digest(supplied, expected):
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'ok':False, 'error':'Sesión no válida o formulario caducado. Recarga la página.'}), 400
            abort(400, description='Formulario caducado. Actualice la página e inténtelo de nuevo.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=()'
        # Permite fuentes web externas ya utilizadas por el diseño. Revisar una CSP con nonce antes de endurecerla.
        if response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        if not app.debug and request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
