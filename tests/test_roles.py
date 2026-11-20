"""Pruebas de roles y catálogos; ejecutar con dependencias instaladas."""
import pytest
from app import create_app
from app.models.auth import hash_password
from app.models.database import execute,query
from config import DevelopmentConfig

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(DevelopmentConfig,'DATABASE_PATH',str(tmp_path/'db.sqlite'))
    monkeypatch.setattr(DevelopmentConfig,'UPLOAD_FOLDER',str(tmp_path/'uploads'))
    monkeypatch.setattr(DevelopmentConfig,'SEED_DEMO_DATA',False)
    monkeypatch.setattr(DevelopmentConfig,'SEED_CATALOG_EXAMPLES',True)
    app=create_app('development')
    app.config.update(TESTING=True)
    execute('INSERT INTO usuarios(nombre,email,password,rol) VALUES(?,?,?,?)',
            ('Admin','admin@empresa.test',hash_password('Admin-clave-segura-2026'),'admin'))
    execute('INSERT INTO usuarios(nombre,email,password,rol) VALUES(?,?,?,?)',
            ('Tecnico 1','tecnico1@empresa.test',hash_password('Tecnico-uno-2026'),'tecnico'))
    execute('INSERT INTO usuarios(nombre,email,password,rol) VALUES(?,?,?,?)',
            ('Tecnico 2','tecnico2@empresa.test',hash_password('Tecnico-dos-2026'),'tecnico'))
    execute('INSERT INTO diagnosticos(n_certificado,equipo_id,tecnico_id) VALUES(?,?,?)',
            ('D-UNO',1,2))
    execute('INSERT INTO diagnosticos(n_certificado,equipo_id,tecnico_id) VALUES(?,?,?)',
            ('D-DOS',2,3))
    return app.test_client()

def token(client):
    import secrets
    with client.session_transaction() as sess:
        if '_csrf_token' not in sess:
            sess['_csrf_token']=secrets.token_urlsafe(32)
        return sess['_csrf_token']

def login(client,email,password):
    return client.post('/auth/login',data={'csrf_token':token(client), 'email':email,'password':password})

def test_tech_has_private_home_and_private_diagnostics(client):
    assert login(client,'tecnico1@empresa.test','Tecnico-uno-2026').status_code==302
    home=client.get('/dashboard').get_data(as_text=True)
    assert 'panel-mi-inicio' in home and 'panel-dashboard' not in home
    for route in ['/api/dashboard/stats','/api/usuarios','/api/estadisticas','/api/audit']:
        assert client.get(route).status_code==403
    assert client.get('/api/mi-resumen').get_json()['resumen']['total']==1
    data=client.get('/api/diagnosticos').get_json()['data']
    assert [row['n_certificado'] for row in data]==['D-UNO']
    assert client.get('/api/diagnosticos/2').status_code==403
    assert client.get('/api/diagnosticos/2/aprobaciones').status_code==403
    assert client.get('/api/diagnosticos/2/pdf').status_code==403
    assert client.get('/api/search?q=D-DOS').get_json()==[]
    assert client.get('/api/usuarios/me').get_json()['rol']=='tecnico'
    assert client.post('/api/clientes',json={'nombre':'Malicioso'},headers={'X-CSRF-Token':token(client)}).status_code==403
    assert client.post('/api/usuarios',json={'nombre':'Abuso','email':'abc@test.test','rol':'admin','password':'Segura-test-123456'},headers={'X-CSRF-Token':token(client)}).status_code==403


def test_admin_can_manage_staff_and_review_global_stats(client):
    assert login(client,'admin@empresa.test','Admin-clave-segura-2026').status_code==302
    home=client.get('/dashboard').get_data(as_text=True)
    assert 'panel-dashboard' in home and 'panel-personal' in home
    assert 'panel-mi-inicio' not in home
    assert client.get('/api/dashboard/stats').status_code==200
    assert client.get('/api/usuarios').status_code==200
    assert client.get('/api/diagnosticos').get_json()['total']==2
    new_user={'nombre':'Nuevo Técnico','email':'nuevo@empresa.test','rol':'tecnico','password':'Nueva-segura-123456'}
    res=client.post('/api/usuarios',json=new_user,headers={'X-CSRF-Token':token(client)})
    assert res.status_code==201
    uid=res.get_json()['id']
    assert client.patch(f'/api/usuarios/{uid}',json={'rol':'jefe','activo':True},headers={'X-CSRF-Token':token(client)}).status_code==200
    assert query('SELECT rol FROM usuarios WHERE id=?',(uid,),one=True)['rol']=='jefe'
    adminid=query('SELECT id FROM usuarios WHERE email=?',('admin@empresa.test',),one=True)['id']
    assert client.patch(f'/api/usuarios/{adminid}',json={'rol':'tecnico','activo':True},headers={'X-CSRF-Token':token(client)}).status_code==409


def test_notifications_are_read_by_user_not_globally(client):
    aid=execute("INSERT INTO alertas(tipo,titulo,mensaje) VALUES('info','Prueba','Notificación')")
    login(client,'tecnico1@empresa.test','Tecnico-uno-2026')
    assert client.post(f'/api/alertas/{aid}/resolver',json={},headers={'X-CSRF-Token':token(client)}).status_code==200
    assert next(x for x in client.get('/api/alertas').get_json() if x['id']==aid)['resuelta']==1
    client.post('/auth/logout',data={'csrf_token':token(client)})
    login(client,'tecnico2@empresa.test','Tecnico-dos-2026')
    assert next(x for x in client.get('/api/alertas').get_json() if x['id']==aid)['resuelta']==0


def test_development_examples_are_explicitly_marked(client):
    assert query("SELECT COUNT(*) c FROM equipos WHERE codigo LIKE 'DEMO-%'",one=True)['c']==4
    assert query("SELECT COUNT(*) c FROM patrones WHERE codigo LIKE 'DEMO-%'",one=True)['c']==4
    assert query("SELECT COUNT(*) c FROM clientes WHERE nombre LIKE 'DEMO · %'",one=True)['c']==2
