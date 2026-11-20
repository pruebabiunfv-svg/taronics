# Ejemplos de catálogos SOLO para desarrollo y demostración.
# Se crean si TODAVÍA NO HAY DIAGNÓSTICOS ni registros en el catálogo.
# Nunca crear usuarios de prueba ni inventar certificados de calibración.

def seed_catalog_examples(conn, allow_existing=False):
    if not allow_existing and conn.execute('SELECT COUNT(*) FROM diagnosticos').fetchone()[0]:
        return
    if not conn.execute("SELECT 1 FROM clientes WHERE nombre LIKE 'DEMO · %' LIMIT 1" if allow_existing else 'SELECT 1 FROM clientes LIMIT 1').fetchone():
        conn.executemany('''INSERT INTO clientes(nombre,ruc,contacto,email,telefono,direccion)
            VALUES(?,?,?,?,?,?)''',[
            ('DEMO · Industria Ejemplo (datos ficticios)', '', 'Persona de prueba', 'cliente@ejemplo.test', '', 'Solo demostración'),
            ('DEMO · Laboratorio de Prueba (datos ficticios)', '', 'Contacto de muestra', 'lab@ejemplo.test', '', 'Solo demostración'),
        ])
    if not conn.execute("SELECT 1 FROM equipos WHERE codigo LIKE 'DEMO-%' LIMIT 1" if allow_existing else 'SELECT 1 FROM equipos LIMIT 1').fetchone():
        demo_cliente = conn.execute("SELECT id FROM clientes WHERE nombre LIKE 'DEMO · %' ORDER BY id LIMIT 1").fetchone()
        cliente = demo_cliente[0] if demo_cliente else None
        conn.executemany('''INSERT INTO equipos(codigo,descripcion,fabricante,modelo,serie,rango,resolucion,tolerancia,magnitud,ubicacion,cliente_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',[
            ('DEMO-PRE-01','Manómetro digital [EJEMPLO]','Marca de muestra','Modelo demo','DEMO-001','0–10 bar','0.01 bar','Por verificar','Presión','Área técnica',cliente),
            ('DEMO-TEM-01','Termómetro de contacto [EJEMPLO]','Marca de muestra','Modelo demo','DEMO-002','−20–150 °C','0.1 °C','Por verificar','Temperatura','Área técnica',cliente),
            ('DEMO-MAS-01','Balanza electrónica [EJEMPLO]','Marca de muestra','Modelo demo','DEMO-003','0–5000 g','0.01 g','Por verificar','Peso','Área técnica',cliente),
            ('DEMO-ELE-01','Multímetro digital [EJEMPLO]','Marca de muestra','Modelo demo','DEMO-004','0–600 V','0.01 V','Por verificar','Eléctrica','Área técnica',cliente),
        ])
    if not conn.execute("SELECT 1 FROM patrones WHERE codigo LIKE 'DEMO-%' LIMIT 1" if allow_existing else 'SELECT 1 FROM patrones LIMIT 1').fetchone():
        conn.executemany('''INSERT INTO patrones(codigo,descripcion,fabricante,modelo,serie,magnitud,incertidumbre,n_certificado,trazabilidad,vencimiento)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',[
            ('DEMO-PAT-PRE','Patrón de presión [EJEMPLO]','No válido para uso real','Demo','DEMO-REF-01','Presión','POR DETERMINAR','','Solo pruebas',None),
            ('DEMO-PAT-TEM','Patrón de temperatura [EJEMPLO]','No válido para uso real','Demo','DEMO-REF-02','Temperatura','POR DETERMINAR','','Solo pruebas',None),
            ('DEMO-PAT-MAS','Masas patrón [EJEMPLO]','No válido para uso real','Demo','DEMO-REF-03','Peso','POR DETERMINAR','','Solo pruebas',None),
            ('DEMO-PAT-ELE','Calibrador eléctrico [EJEMPLO]','No válido para uso real','Demo','DEMO-REF-04','Eléctrica','POR DETERMINAR','','Solo pruebas',None),
        ])
    conn.commit()
