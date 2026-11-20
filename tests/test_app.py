"""Pruebas básicas de rutas y protección. Ejecutar con pytest tras instalar dependencias."""
import pytest
from app import create_app
from config import DevelopmentConfig
from app.models.database import execute
from app.models.auth import hash_password

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(DevelopmentConfig, 'DATABASE_PATH', str(tmp_path/'test.db'))
    monkeypatch.setattr(DevelopmentConfig, 'UPLOAD_FOLDER', str(tmp_path/'uploads'))
    monkeypatch.setattr(DevelopmentConfig, 'SEED_DEMO_DATA', False)
    monkeypatch.setattr(DevelopmentConfig, 'SEED_CATALOG_EXAMPLES', False)
    monkeypatch.setattr(DevelopmentConfig, 'ALLOW_PUBLIC_REGISTRATION', True)
    monkeypatch.setattr(DevelopmentConfig, 'REGISTRATION_CODE', '')
    app=create_app('development')
    app.config.update(TESTING=True)
    return app.test_client()

def token(client):
    with client.session_transaction() as sess:
        return sess['_csrf_token']

def test_public_and_csrf(client):
    assert client.get('/inicio').status_code==200
    assert client.get('/auth/login').status_code==200
    assert client.get('/registro').status_code==200
    assert client.post('/registro',data={}).status_code==400

def test_registration_and_login(client):
    client.get('/registro')
    data={'csrf_token':token(client),'usuario':'Operador de Pruebas','email':'operador@example.test',
          'password':'clave-larga-y-unica-2026','password_confirm':'clave-larga-y-unica-2026'}
    assert client.post('/registro',data=data).status_code==302
    client.get('/auth/login')
    resp=client.post('/auth/login',data={'csrf_token':token(client),'email':'operador@example.test','password':'clave-larga-y-unica-2026'})
    assert resp.status_code==302
    assert client.get('/dashboard').status_code==200
    assert client.get('/api/audit').status_code==403
    assert client.get('/api/usuarios').status_code==403
    assert client.get('/api/dashboard/stats').status_code==403
    assert client.get('/api/mi-resumen').status_code==200
    assert 'panel-mi-inicio' in client.get('/dashboard').get_data(as_text=True)
    assert 'panel-dashboard' not in client.get('/dashboard').get_data(as_text=True)
    assert client.get('/auth/logout').status_code==405
    assert client.post('/auth/logout',data={'csrf_token':token(client)}).status_code==302
    assert client.get('/api/dashboard/stats').status_code==401
