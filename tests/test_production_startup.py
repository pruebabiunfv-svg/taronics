"""Regresiones del arranque de Railway/producción."""
import pytest

from app import create_app
from config import ProductionConfig


@pytest.mark.parametrize('secret', [
    None,
    '',
    'REEMPLAZAR_POR_64_CARACTERES_GENERADOS',
    'dev-only-not-for-deployment-change-me',
])
def test_production_requires_a_real_secret(secret, monkeypatch):
    monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', secret)
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        create_app('production')


def test_production_starts_with_secret_and_writable_database(tmp_path, monkeypatch):
    monkeypatch.setattr(ProductionConfig, 'SECRET_KEY', 'a' * 64)
    monkeypatch.setattr(ProductionConfig, 'DATABASE_PATH', str(tmp_path / 'calibpro.db'))
    monkeypatch.setattr(ProductionConfig, 'UPLOAD_FOLDER', str(tmp_path / 'uploads' / 'photos'))
    monkeypatch.setattr(ProductionConfig, 'ALLOW_PUBLIC_REGISTRATION', False)
    monkeypatch.setattr(ProductionConfig, 'REGISTRATION_CODE', '')
    monkeypatch.setattr(ProductionConfig, 'SEED_DEMO_DATA', False)
    monkeypatch.setattr(ProductionConfig, 'SEED_CATALOG_EXAMPLES', False)
    app = create_app('production')
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert app.test_client().get('/inicio').status_code == 200
