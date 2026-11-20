"""Flask application factory."""
import os
from flask import Flask
from config import config

def create_app(config_name='default'):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config[config_name])
    if config_name == 'production' and app.config.get('SECRET_KEY') in (
        None,
        '',
        'REEMPLAZAR_POR_64_CARACTERES_GENERADOS',
        'dev-only-not-for-deployment-change-me',
    ):
        raise RuntimeError(
            'Falta una SECRET_KEY segura. En Railway > Servicio > Variables, '
            'cree SECRET_KEY con un valor aleatorio (python -c '
            '"import secrets; print(secrets.token_hex(32))") y despliegue los cambios.'
        )
    if config_name == 'production' and app.config['ALLOW_PUBLIC_REGISTRATION'] and not app.config['REGISTRATION_CODE']:
        raise RuntimeError('El registro de producción requiere REGISTRATION_CODE, o deshabilitarlo.')
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

    from app.models.database import init_db
    init_db(app.config['DATABASE_PATH'], seed_demo=app.config['SEED_DEMO_DATA'],
            seed_catalog=app.config['SEED_CATALOG_EXAMPLES'])
    from app.security import setup_security
    setup_security(app)

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.diagnostico import diagnostico_bp
    from app.routes.equipos import equipos_bp
    from app.routes.clientes import clientes_bp
    from app.routes.reportes import reportes_bp
    from app.routes.api import api_bp
    from app.routes.home import home_bp
    from app.routes.registro import registro_bp
    for bp in [home_bp, registro_bp, auth_bp, dashboard_bp, diagnostico_bp, equipos_bp, clientes_bp, reportes_bp]:
        app.register_blueprint(bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.cli import setup_cli
    setup_cli(app)
    return app
