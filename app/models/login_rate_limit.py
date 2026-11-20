"""Límite básico de intentos de acceso persistido en SQLite.
Para producción distribuida, complementar con limitación en Nginx/WAF.
"""
import hashlib
import time
from flask import request
from app.models.database import query, execute

def _key(email):
    value = (request.remote_addr or 'unknown')+'|'+email.strip().lower()
    return hashlib.sha256(value.encode()).hexdigest()

def is_locked(email):
    row = query('SELECT bloqueo_hasta FROM login_attempts WHERE clave=?', (_key(email),), one=True)
    return bool(row and row['bloqueo_hasta'] > int(time.time()))

def record_failure(email):
    now = int(time.time())
    key = _key(email)
    row = query('SELECT intentos,primero FROM login_attempts WHERE clave=?',(key,),one=True)
    if not row or now-row['primero'] > 900:
        execute('INSERT INTO login_attempts(clave,intentos,primero,bloqueo_hasta) VALUES(?,?,?,?) ON CONFLICT(clave) DO UPDATE SET intentos=excluded.intentos,primero=excluded.primero,bloqueo_hasta=0',(key,1,now,0))
        return
    attempts = row['intentos']+1
    locked_until = now+900 if attempts>=6 else 0
    execute('UPDATE login_attempts SET intentos=?,bloqueo_hasta=? WHERE clave=?',(attempts,locked_until,key))

def clear_attempts(email):
    execute('DELETE FROM login_attempts WHERE clave=?',(_key(email),))
