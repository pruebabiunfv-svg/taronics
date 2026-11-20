"""Pruebas del nuevo circuito. Requiere pip install -r requirements-dev.txt."""
import pytest
from app import create_app
from config import DevelopmentConfig
from app.models.database import execute, query
from app.models.auth import hash_password


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(DevelopmentConfig,'DATABASE_PATH',str(tmp_path/'test.db'))
    monkeypatch.setattr(DevelopmentConfig,'UPLOAD_FOLDER',str(tmp_path/'photos'))
    monkeypatch.setattr(DevelopmentConfig,'SEED_DEMO_DATA',False)
    monkeypatch.setattr(DevelopmentConfig,'SEED_CATALOG_EXAMPLES',False)
    monkeypatch.setattr(DevelopmentConfig,'PUBLIC_BASE_URL','https://calibpro.example.test')
    app=create_app('development')
    app.config.update(TESTING=True)
    with app.app_context():
        execute('INSERT INTO usuarios(nombre,email,password,rol) VALUES(?,?,?,?)',
                ('Técnico','tecnico@test.example',hash_password('tecnico-password-123'),'tecnico'))
        execute('INSERT INTO usuarios(nombre,email,password,rol) VALUES(?,?,?,?)',
                ('Jefe','jefe@test.example',hash_password('jefe-password-123'),'jefe'))
        execute('INSERT INTO clientes(nombre,email) VALUES(?,?)',('Cliente prueba','cliente@test.example'))
        execute('INSERT INTO equipos(codigo,descripcion,cliente_id) VALUES(?,?,?)',('MAN-001','Manómetro de prueba',1))
        execute('INSERT INTO diagnosticos(n_certificado,equipo_id,tecnico_id,resultado,dictamen,fecha_fin) VALUES(?,?,?,?,?,?)',
                ('CERT-TEST-001',1,1,'conforme','Cumple','2026-10-11 17:00'))
        execute('INSERT INTO lecturas(diagnostico_id,ciclo,punto,valor_nominal,lectura_ebp,lectura_patron) VALUES(?,?,?,?,?,?)',
                (1,1,1,10.0,10.01,10.0))
    return app.test_client()


def csrf(client):
    import secrets
    with client.session_transaction() as sess:
        if '_csrf_token' not in sess:
            sess['_csrf_token'] = secrets.token_urlsafe(32)
        return sess['_csrf_token']


def login(client, email, password):
    return client.post('/auth/login', data={'csrf_token':csrf(client),'email':email,'password':password})


def json_post(client, path, data):
    return client.post(path,json=data,headers={'X-CSRF-Token':csrf(client)})


def test_approval_pdf_qr_verification_and_freeze(client):
    assert login(client,'tecnico@test.example','tecnico-password-123').status_code==302
    assert client.get('/api/diagnosticos/1/pdf').status_code==409
    assert json_post(client,'/api/diagnosticos/1/revision',{}).status_code==200
    assert json_post(client,'/api/diagnosticos/1/aprobacion',{'accion':'aprobar','password':'tecnico-password-123'}).status_code==403
    assert client.post('/auth/logout',data={'csrf_token':csrf(client)}).status_code==302
    assert login(client,'jefe@test.example','jefe-password-123').status_code==302
    assert json_post(client,'/api/diagnosticos/1/aprobacion',{'accion':'aprobar','password':'incorrecta'}).status_code==403
    ok=json_post(client,'/api/diagnosticos/1/aprobacion',{'accion':'aprobar','password':'jefe-password-123','comentario':'Revisado'} )
    assert ok.status_code==200
    resp=client.get('/api/diagnosticos/1/pdf')
    assert resp.status_code==200
    assert resp.mimetype=='application/pdf'
    assert resp.data.startswith(b'%PDF-')
    token=query('SELECT token_verificacion FROM diagnosticos WHERE id=1',one=True)['token_verificacion']
    valid=client.get(f'/verificar/{token}')
    assert valid.status_code==200
    assert 'CERT-TEST-001' in valid.get_data(as_text=True)
    assert client.put('/api/diagnosticos/1',json={'resultado':'pendiente'},headers={'X-CSRF-Token':csrf(client)}).status_code==409
    assert client.get('/api/diagnosticos/1/aprobaciones').get_json()['historial'][0]['accion']=='aprobar'
    # Cambios externos en equipo invalidan la huella e impiden descargar/enviar.
    execute("UPDATE equipos SET descripcion='Descripción alterada' WHERE id=1")
    assert client.get('/api/diagnosticos/1/pdf').status_code==409
    assert client.get(f'/verificar/{token}').status_code==409


def test_gmail_not_simulated_when_unconfigured(client):
    login(client,'tecnico@test.example','tecnico-password-123')
    json_post(client,'/api/diagnosticos/1/revision',{})
    client.post('/auth/logout',data={'csrf_token':csrf(client)})
    login(client,'jefe@test.example','jefe-password-123')
    json_post(client,'/api/diagnosticos/1/aprobacion',{'accion':'aprobar','password':'jefe-password-123'})
    response=json_post(client,'/api/diagnosticos/1/email',{'to':'cliente@test.example'})
    assert response.status_code==503
    assert query('SELECT enviado_email FROM diagnosticos WHERE id=1',one=True)['enviado_email']==0


def test_rejected_remains_editable(client):
    login(client,'tecnico@test.example','tecnico-password-123')
    json_post(client,'/api/diagnosticos/1/revision',{})
    client.post('/auth/logout',data={'csrf_token':csrf(client)})
    login(client,'jefe@test.example','jefe-password-123')
    assert json_post(client,'/api/diagnosticos/1/aprobacion',{
        'accion':'rechazar','password':'jefe-password-123','comentario':'Corrija las lecturas'}).status_code==200
    assert client.get('/api/diagnosticos/1/pdf').status_code==409
    assert client.put('/api/diagnosticos/1',json={'resultado':'conforme','dictamen':'Revisado'},
                      headers={'X-CSRF-Token':csrf(client)}).status_code==200
