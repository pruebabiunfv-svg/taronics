"""Configuración por entorno de Tatronics / CalibPro."""
import os
from datetime import timedelta
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
# Lee el archivo .env local en desarrollo y despliegues manuales.
# En producción también admite variables inyectadas por Docker o gestor de secretos.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env', override=False)
except ImportError:
    pass  # pip install -r requirements.txt instala python-dotenv
INSTANCE_DIR = Path(os.getenv('CALIBPRO_INSTANCE_DIR', str(BASE_DIR / 'instance'))).resolve()

def _bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1','true','yes','on')

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    DATABASE_PATH = os.getenv('DATABASE_PATH', str(INSTANCE_DIR / 'calibpro.db'))
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', str(INSTANCE_DIR / 'uploads' / 'photos'))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME', ''))
    PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '')
    PDF_SIGN_P12_PATH = os.getenv('PDF_SIGN_P12_PATH', '')
    PDF_SIGN_P12_PASSWORD = os.getenv('PDF_SIGN_P12_PASSWORD', '')
    CERT_DAYS_ALERT = 30
    ITEMS_PER_PAGE = 20
    REGISTRATION_CODE = os.getenv('REGISTRATION_CODE', '')
    ALLOW_PUBLIC_REGISTRATION = _bool('ALLOW_PUBLIC_REGISTRATION', False)
    SEED_DEMO_DATA = False
    SEED_CATALOG_EXAMPLES = False
    DEBUG = False

class DevelopmentConfig(Config):
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-not-for-deployment-change-me')
    ALLOW_PUBLIC_REGISTRATION = _bool('ALLOW_PUBLIC_REGISTRATION', True)
    SEED_DEMO_DATA = _bool('SEED_DEMO_DATA', False)
    SEED_CATALOG_EXAMPLES = _bool('SEED_CATALOG_EXAMPLES', True)
    DEBUG = True

class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'

config = {'development': DevelopmentConfig, 'production': ProductionConfig, 'default': DevelopmentConfig}
