"""
CalibPro — Database Layer (SQLite via sqlite3)
All CRUD helpers live here as simple functions.
"""
import sqlite3
import os
from datetime import datetime, date


# ──────────────────────────────────────────
#  CONNECTION
# ──────────────────────────────────────────
_DB_PATH = None

def get_db(path=None):
    p = path or _DB_PATH
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path, seed_demo=False, seed_catalog=False):
    global _DB_PATH
    _DB_PATH = path
    conn = get_db(path)
    _create_tables(conn)
    _migrate_certificates(conn)
    _migrate_notifications(conn)
    if seed_demo:
        raise RuntimeError('No se crean usuarios ficticios con contraseñas predeterminadas; utilice create-admin.')
    if seed_catalog:
        from app.models.catalog_examples import seed_catalog_examples
        seed_catalog_examples(conn)
    conn.close()


# ──────────────────────────────────────────
#  SCHEMA
# ──────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    password    TEXT NOT NULL,
    rol         TEXT NOT NULL DEFAULT 'tecnico',  -- admin | jefe | tecnico
    laboratorio TEXT DEFAULT '',  -- compatibilidad legado, sin uso por sedes
    activo      INTEGER DEFAULT 1,
    creado      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    ruc         TEXT,
    contacto    TEXT,
    email       TEXT,
    telefono    TEXT,
    direccion   TEXT,
    activo      INTEGER DEFAULT 1,
    creado      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS equipos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL UNIQUE,
    descripcion     TEXT NOT NULL,
    fabricante      TEXT,
    modelo          TEXT,
    serie           TEXT,
    rango           TEXT,
    resolucion      TEXT,
    tolerancia      TEXT,
    magnitud        TEXT,
    ubicacion       TEXT,
    cliente_id      INTEGER REFERENCES clientes(id),
    activo          INTEGER DEFAULT 1,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS patrones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL UNIQUE,
    descripcion     TEXT NOT NULL,
    fabricante      TEXT,
    modelo          TEXT,
    serie           TEXT,
    magnitud        TEXT,
    incertidumbre   TEXT,
    n_certificado   TEXT,
    trazabilidad    TEXT,
    vencimiento     TEXT,
    activo          INTEGER DEFAULT 1,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS diagnosticos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    n_certificado   TEXT UNIQUE,
    equipo_id       INTEGER NOT NULL REFERENCES equipos(id),
    patron_id       INTEGER REFERENCES patrones(id),
    tecnico_id      INTEGER NOT NULL REFERENCES usuarios(id),
    procedimiento   TEXT,
    magnitud        TEXT,
    unidad          TEXT,
    resultado       TEXT DEFAULT 'pendiente',  -- conforme|no_conforme|observacion|pendiente
    dictamen        TEXT,
    estado_visual   TEXT,
    observaciones   TEXT,
    temp_inicio     REAL, temp_fin     REAL,
    humedad_inicio  REAL, humedad_fin  REAL,
    presion_atm     REAL,
    fecha_inicio    TEXT DEFAULT (datetime('now')),
    fecha_fin       TEXT,
    prox_calibracion TEXT,
    enviado_email   INTEGER DEFAULT 0,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lecturas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id  INTEGER NOT NULL REFERENCES diagnosticos(id) ON DELETE CASCADE,
    ciclo           INTEGER DEFAULT 1,
    punto           INTEGER DEFAULT 1,
    valor_nominal   REAL,
    porcentaje_rango REAL,
    lectura_ebp     REAL,
    lectura_patron  REAL,
    desviacion      REAL,
    error_pct       REAL,
    incertidumbre   REAL
);

CREATE TABLE IF NOT EXISTS fotos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id  INTEGER NOT NULL REFERENCES diagnosticos(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    label           TEXT,
    tipo            TEXT DEFAULT 'referencia',  -- requerida|adicional|no_conformidad
    mime_type       TEXT DEFAULT 'image/jpeg',
    size_bytes      INTEGER,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alertas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT NOT NULL,   -- vencimiento|no_conformidad|patron|info
    titulo          TEXT NOT NULL,
    mensaje         TEXT,
    entidad         TEXT,
    entidad_id      INTEGER,
    resuelta        INTEGER DEFAULT 0,
    creado          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS login_attempts (
    clave        TEXT PRIMARY KEY,
    intentos     INTEGER NOT NULL DEFAULT 0,
    primero      INTEGER NOT NULL,
    bloqueo_hasta INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER REFERENCES usuarios(id),
    accion      TEXT NOT NULL,
    modulo      TEXT,
    objeto      TEXT,
    detalle     TEXT,
    ip          TEXT,
    ts          TEXT DEFAULT (datetime('now'))
);
"""


def _create_tables(conn):
    conn.executescript(SCHEMA)
    conn.commit()



def _migrate_certificates(conn):
    """Migración idempotente compatible con bases existentes (sin borrar registros)."""
    known = {r['name'] for r in conn.execute('PRAGMA table_info(diagnosticos)')}
    fields = {
        'estado_aprobacion': "TEXT NOT NULL DEFAULT 'borrador'",
        'solicitado_por': 'INTEGER',
        'solicitado_en': 'TEXT',
        'aprobado_por': 'INTEGER',
        'aprobado_en': 'TEXT',
        'huella_aprobada': 'TEXT',
        'token_verificacion': 'TEXT',
        'comentario_aprobacion': 'TEXT',
    }
    for name, definition in fields.items():
        if name not in known:
            conn.execute(f'ALTER TABLE diagnosticos ADD COLUMN {name} {definition}')
    conn.executescript("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_verificacion_token
          ON diagnosticos(token_verificacion) WHERE token_verificacion IS NOT NULL;
        CREATE TABLE IF NOT EXISTS historial_aprobaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnostico_id INTEGER NOT NULL REFERENCES diagnosticos(id),
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            accion TEXT NOT NULL,
            comentario TEXT,
            huella TEXT,
            fecha TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS historial_correos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnostico_id INTEGER NOT NULL REFERENCES diagnosticos(id),
            usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
            destinatarios TEXT NOT NULL,
            estado TEXT NOT NULL,
            pdf_sha256 TEXT,
            fecha TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()



def _migrate_notifications(conn):
    # Destinatarios y lectura independiente sin eliminar alertas
    columns={r['name'] for r in conn.execute('PRAGMA table_info(alertas)')}
    if 'destinatario_id' not in columns:
        conn.execute('ALTER TABLE alertas ADD COLUMN destinatario_id INTEGER REFERENCES usuarios(id)')
    if 'destinatario_rol' not in columns:
        conn.execute('ALTER TABLE alertas ADD COLUMN destinatario_rol TEXT')
    conn.execute('''CREATE TABLE IF NOT EXISTS alertas_leidas (
        usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
        alerta_id INTEGER NOT NULL REFERENCES alertas(id),
        fecha TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY(usuario_id,alerta_id)
    )''')
    conn.commit()


# ──────────────────────────────────────────
#  HELPERS
# ──────────────────────────────────────────

def query(sql, params=(), one=False):
    conn = get_db()
    cur = conn.execute(sql, params)
    result = cur.fetchone() if one else cur.fetchall()
    conn.close()
    return result

def execute(sql, params=()):
    conn = get_db()
    cur = conn.execute(sql, params)
    last_id = cur.lastrowid
    conn.commit()
    conn.close()
    return last_id

def executemany(sql, params_list):
    conn = get_db()
    conn.executemany(sql, params_list)
    conn.commit()
    conn.close()

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]
