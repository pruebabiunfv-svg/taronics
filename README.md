> **VERSIÓN CON ACCESO POR ROLES.** Para consultar la separación entre administrador, jefatura y técnico, el registro único, las aprobaciones directas desde Historial y cómo generar los datos de los desplegables, lea [GUIA_ROLES_Y_DATOS_EJEMPLO.md](GUIA_ROLES_Y_DATOS_EJEMPLO.md). Se preservan las características de PDF con QR, aprobación y Gmail incluidas anteriormente.

# TATRONICS PERÚ · CalibPro Enterprise UI

**Despliegue en Railway:** consulte [GUIA_RAILWAY.md](GUIA_RAILWAY.md) para configurar
`SECRET_KEY`, el puerto dinámico, el almacenamiento persistente y el dominio.

Actualización del proyecto Flask que **unifica la portada corporativa, el inicio de sesión, el registro y el panel de calibraciones**. Mantiene los módulos y endpoints de negocio del CalibPro original, pero reordena los archivos para mantenimiento. La apariencia es nueva; esto **no implica certificación de seguridad ni acreditación metrológica**.

## 1. Vistas principales

- `/inicio` — presentación comercial, servicios, contacto y cotización por WhatsApp (como en la versión anterior).
- `/auth/login` — acceso renovado con diseño idéntico a la marca corporativa.
- `/registro` — alta de usuario técnico con código de invitación opcional; **deshabilitada por defecto en producción**.
- `/dashboard` — acceso único al espacio de trabajo: los administradores y jefes ven el dashboard general; los técnicos ven su resumen personal de diagnósticos.
- `/historial` — entrada al módulo de historial tras iniciar sesión.

**Colores:** azul petróleo `#071b33`, turquesa `#00ccb0`, blanco y gris de interfaz `#f1f6f7`. Fuentes: Manrope / DM Sans.

## 2. Organización del código

```text
app/
├── __init__.py               # Factory de Flask, registro de módulos
├── security.py               # CSRF, cookies y encabezados HTTP
├── cli.py                    # Creación de administrador sin contraseña predeterminada
├── models/
│   ├── auth.py               # Autenticación y roles
│   ├── database.py           # SQLite y migraciones de seguridad
│   ├── catalog_examples.py   # Catálogos ficticios marcados DEMO (solo desarrollo)
│   └── login_rate_limit.py   # Control básico de intentos de acceso
├── routes/                   # Rutas independientes por área de negocio
│   ├── home.py, auth.py, registro.py, dashboard.py
│   ├── diagnostico.py, equipos.py, clientes.py, reportes.py, api.py
├── templates/
│   ├── public/home.html      # Página corporativa
│   ├── auth/base.html        # Base reutilizable del portal
│   ├── auth/login.html
│   ├── auth/register.html
│   └── platform/
│       ├── app.html          # Armazón principal
│       ├── partials/         # Sidebar, encabezado, modales
│       └── panels/           # Cada módulo en una plantilla distinta
└── static/
    ├── css/{public,auth,platform}/
    │   ├── platform/legacy.css   # Reglas necesarias del proyecto previo
    │   └── platform/platform.css # Identidad visual renovada
    └── js/{public,auth,platform}/
config.py                     # Configuraciones por entorno
run.py                        # Punto de entrada Flask / Gunicorn
instance/                     # Datos de ejecución: NO versionar
migration/                    # Copia de datos y fotos del ZIP previo, NO se cargan automáticamente
scripts/import_legacy.py     # Herramienta de migración opcional
Dockerfile, docker-compose.yml, .env.example
```

Los estilos del panel están separados en `legacy.css` y `platform.css` para **reducir el riesgo de romper funcionalidades originales**. La próxima refactorización puede desacoplar CSS/JavaScript dentro de cada módulo, tras pruebas funcionales.

## 3. Ejecución local (Windows, Linux o macOS)

Requisitos: Python 3.10+ recomendado 3.12, y pip. **No incluye paquetes de Python dentro del ZIP**.

```bash
cd tatronics
python -m venv .venv
```

Activar el entorno:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- Windows CMD: `.venv\Scripts\activate.bat`
- Linux/macOS: `source .venv/bin/activate`

```bash
pip install -r requirements.txt
python -m flask --app run:app create-admin
python run.py
```

Abrir `http://127.0.0.1:5000/inicio`. La aplicación crea una **base nueva y vacía** dentro de `instance/calibpro.db` cuando no existe. Antes de iniciar sesión debes crear un administrador con `create-admin`, que te solicitará nombre, correo y contraseña (mínimo 12 caracteres). **No hay usuario/contraseña de prueba habilitados automáticamente**.

Para cargar los registros y fotos del sistema anterior **en una instalación aún vacía**, y con el servidor detenido:

```bash
python scripts/import_legacy.py
```

**Importante:** ese archivo contiene los registros que venían en el ZIP previo, incluidos usuarios de demostración. Revísalos y cambia sus credenciales antes de exposición pública. El importador no sobrescribe una base existente. Si ya ejecutaste `python run.py` por primera vez, tendrás que respaldar y mover la base nueva antes de usar el importador.

También puedes iniciar datos de ejemplo intencionalmente **solo en desarrollo y sobre una base vacía** configurando `SEED_DEMO_DATA=1`; no hacerlo en producción.

## 4. Puesta en producción

### Variables necesarias

- `CALIBPRO_ENV=production`
- `SECRET_KEY` largo, único y generado criptográficamente. Ejemplo: `python -c "import secrets; print(secrets.token_hex(32))"`.
- `DATABASE_PATH`, `UPLOAD_FOLDER`: rutas persistentes con permisos de escritura y copias de seguridad.
- `ALLOW_PUBLIC_REGISTRATION=false` recomendado. Si tu empresa necesita registro por invitación, configura `ALLOW_PUBLIC_REGISTRATION=true` **y** un `REGISTRATION_CODE` secreto.
- Variables `MAIL_*` solo si utilizarás SMTP real. Las credenciales van en secretos del servidor, no en git.

Ejemplo Linux con Gunicorn, después de establecer las variables:

```bash
gunicorn --workers 2 --threads 4 --bind 127.0.0.1:8000 run:app
```

**HTTPS es obligatorio en producción** debido a las cookies de sesión seguras. Publica el servicio detrás de Nginx/Caddy u otro proxy TLS, con límites de solicitud y registros de acceso, no directamente en Internet mediante Flask `app.run()`.

### Docker (opcional)

```bash
cp .env.example .env
# Completa SECRET_KEY y rutas correctamente.
mkdir -p instance
# Linux: asegurar que el usuario del contenedor (UID 10001) pueda escribir en instance/
docker compose up --build -d
docker compose exec tatronics flask --app run:app create-admin
```

`docker-compose.yml` publica solamente en `127.0.0.1:8000`. Debes configurar tu proxy y certificado TLS de forma independiente. **No está incluido el dominio ni la configuración final de HTTPS**.

### Cambios de seguridad añadidos

- Verificación CSRF en `POST/PUT/PATCH/DELETE`, incluido el API JSON y el formulario de acceso; `api.js` adjunta el token.
- Sesiones HTTP-only, SameSite y `Secure` en producción; token renovado tras el inicio de sesión.
- Cierre de sesión mediante POST y verificación de usuario activo en endpoints protegidos.
- Intentos fallidos de inicio de sesión limitados temporalmente (base SQLite); debes complementar con un WAF / proxy para despliegues distribuidos.
- Contraseñas nuevas con `werkzeug.security`; contraseñas antiguas SHA-256 se migran al autenticar (se recomienda un plan de cambio obligatorio para cuentas previas).
- Datos de muestra **no se insertan por defecto**. Comando seguro para crear el primer administrador.
- Acceso a listados de usuarios y auditoría restringido a admin/jefe.
- Archivos originales conservados en `migration/`, fuera de la ruta activa de producción.

### Validaciones que aún exige una empresa antes del lanzamiento

Esta entrega mejora el **diseño y la estructura para un escenario empresarial**, pero no debe considerarse un producto plenamente endurecido o auditado sin completar lo siguiente:

1. Instalar dependencias y ejecutar las pruebas reales de Flask en un entorno controlado: `pip install -r requirements-dev.txt && pytest -q`.
2. Revisar autorización por cliente, equipo y laboratorio en **todos los endpoints**; la aplicación heredada todavía utiliza permisos compartidos y SQLite.
3. Planificar migración a PostgreSQL y migraciones versionadas si aumenta el número de usuarios y la concurrencia.
4. Implementar restablecimiento de contraseña, invitaciones de un solo uso/verificación de correo y política de MFA según los requisitos empresariales.
5. Revisar sanitización/XSS de todo el JavaScript heredado, contenido de PDFs y cargas de archivos; agregar CSP rigurosa y escaneo de dependencias.
6. Configurar monitoreo, logging estructurado, backups y pruebas de restauración, control de acceso a fotos/reportes y limitaciones de subida.
7. **Revocar la antigua credencial SMTP** que estuvo expuesta en versiones anteriores, incluso si ya no aparece en este código.
8. Validar trazabilidad, criterios de conformidad y contenido de certificados con un responsable metrológico. No se declara acreditación ISO/IEC 17025.

## 5. Validaciones efectuadas en esta entrega

- Compilación Python del código fuente.
- Sintaxis JavaScript (`node --check`) de los módulos existentes y nuevos.
- Renderizado Jinja2 de las pantallas, incluido el ensamblaje de componentes del panel.
- Capturas visuales renderizadas a **1440 y 390 px** (acceso, registro y dashboard), sin desbordamiento horizontal en los anchos revisados.

**Limitación del entorno de creación:** no se pudo instalar Flask en la máquina de revisión debido a ausencia de conectividad de pip; por lo tanto, las pruebas de rutas Flask en vivo y las pruebas de integración del backend se entregan escritas, pero **no se ejecutaron**. Las previsualizaciones usan plantillas renderizadas con datos ficticios y no son evidencia de funcionamiento integral del servidor.

---

## 6. NUEVO: Certificados PDF con código QR (versión ampliada)

El botón **Certificados** incluye ahora los estados **Borrador → En revisión → Aprobado** o **Devuelto**. Un PDF descargable solo se genera para expedientes aprobados. Este PDF está creado con ReportLab y añade un QR que apunta a la página pública `https://tu-dominio/verificar/<token>`. El QR usa un token aleatorio de difícil adivinación y la página muestra exclusivamente número, fecha y estado, sin publicar datos del cliente.

Cada aprobación conserva una **huella SHA-256** de datos del equipo, lecturas, patrón, expediente y fotografías. Si hay modificaciones después de la aprobación, la descarga, verificación y envío se bloquean. Revisión y aprobación incluyen auditoría de responsable y fecha. El técnico no puede aprobar su propio expediente; un jefe o administrador confirma su identidad introduciendo otra vez su contraseña. Para corregir un expediente en revisión, el revisor debe **rechazarlo con motivo** y solicitar una nueva revisión tras las modificaciones.

**Firma electrónica interna versus firma digital criptográfica:** la aprobación con contraseña y huella es evidencia de un flujo interno; **no equivale** a una firma digital PDF de certificado acreditado. Para incorporar firma CMS criptográfica en PDF (`pyHanko`, campo `FirmaDigitalTatronics`), configurar un certificado PKCS#12 legítimo y su contraseña. El usuario debe verificar la cadena de confianza, vigencia, revocación, rol del titular y requisitos jurídicos/metrológicos que correspondan antes de emitir certificados comerciales.

Las variables en `.env` necesarias para QR externo son:

```dotenv
PUBLIC_BASE_URL=https://calibraciones.tu-empresa.pe
# OPCIONALES: firma criptográfica PDF solo con certificado auténtico autorizado
# PDF_SIGN_P12_PATH=/app/instance/secrets/certificado-firma.p12
# PDF_SIGN_P12_PASSWORD=CONTRASENA_SECRETA
```

**Nunca** incorporar un P12/PFX ni su contraseña al ZIP, Git, HTML ni directorio público. El archivo debe permanecer en una carpeta de secretos privada; el usuario de ejecución debe tener acceso de lectura. El PDF solo afirmará incluir firma criptográfica cuando esa ruta esté configurada y el paso de firmado finalice correctamente. Si falla, **no entrega** un PDF marcado como firmado. Para uso regulado, verificar la firma con herramientas de validación y agregar políticas de sello de tiempo/revocación según los requisitos aplicables; este módulo por defecto no proporciona sello de tiempo cualificado ni acreditación.

> **Importante:** existe una migración idempotente del esquema SQLite. Antes de instalar una versión nueva sobre una base ya utilizada, haga **respaldo verificable** de `instance/calibpro.db` (archivo principal, WAL y SHM si están presentes). Detenga el servicio antes de sustituir archivos o recuperar copias.

## 7. NUEVO: Envío real de Gmail SMTP

No hay envíos simulados que marquen certificados como enviados. **Solo jefe/administrador** puede enviarlos cuando están aprobados y la huella aún coincide. Se adjunta el mismo PDF con QR y, si se configura, firma criptográfica. El envío usa TLS y autenticación con Gmail, y se registra el intento **solo cuando Gmail acepta el mensaje SMTP** (esto no demuestra recepción en bandeja).

Google recomienda OAuth como opción principal. La implementación incluida utiliza una **contraseña de aplicación** de Gmail cuando la cuenta lo permite: requiere verificación en dos pasos y una contraseña de aplicación específica. Si su organización prohíbe contraseñas de aplicación, será necesario un adaptador OAuth 2.0 / Gmail API autorizado, que no está implementado en esta entrega.

1. Habilite la verificación en dos pasos en la cuenta oficial que enviará los certificados.
2. Si aparece la opción de **Contraseñas de aplicaciones**, genere una credencial para CalibPro en la configuración de seguridad de Google y guárdela como secreto del servidor.
3. Defina las variables indicadas abajo **fuera del código fuente**. La cuenta remitente debe coincidir con la cuenta autorizada, salvo que Gmail haya configurado el alias correspondiente.
4. Reinicie el servicio y ejecute `python -m flask --app run:app test-gmail --to destino@empresa.pe`, para enviar un correo de prueba **real** y confirmar recepción.

```dotenv
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=cuenta-autorizada@gmail.com
MAIL_PASSWORD=CONTRASENA_DE_APLICACION_DE_GMAIL
MAIL_DEFAULT_SENDER=cuenta-autorizada@gmail.com
```

Puerto 587 usa **STARTTLS** y 465 usa **TLS implícito**. Si la cuenta tiene MFA y no ofrece contraseña de aplicación, no use su contraseña habitual en `MAIL_PASSWORD`: incorpore Gmail API / OAuth a la integración futura.

### Para supervisores: cómo utilizar los nuevos módulos

1. El técnico registra el diagnóstico, introduce lecturas, guarda conclusiones y pulsa **Solicitar revisión**.
2. En **Certificados**, un jefe/administrador pulsa **Revisar y aprobar**, examina la información, introduce comentario opcional y confirma su contraseña. Puede rechazar con motivo para devolver a corrección.
3. Tras aprobar, aparecen **PDF con QR** y, para usuarios autorizados, **Gmail**. Descargue el PDF o envíelo al cliente.
4. El cliente escanea el QR y ve el resultado en la página pública de verificación; nunca descarga archivos internos del servidor.

### Comprobaciones técnicas

```bash
pip install -r requirements-dev.txt
pytest -q
python -m compileall app
```

Estas pruebas incluyen estados, permisos, bloqueo de ediciones, PDF válido, QR, huellas, ausencia de éxito ficticio sin Gmail y entrega SMTP con un simulador local. Para producción faltan ensayo real con la cuenta autorizada, prueba de firma con un PKCS#12 legítimo y auditoría integral de permisos y concurrencia. Hay funcionalidades heredadas no sujetas a la nueva validación exhaustiva de roles: completar esa revisión antes de exponer el proyecto a Internet.

## Actualización: perfiles empresariales y ejemplos de catálogos

- Un solo inicio de sesión (`/auth/login`) con redirección visual por rol.
- Administración: indicadores globales, usuarios, equipos, clientes, patrones, informes y aprobación.
- Técnicos: portada propia, diagnósticos, historial solo propio, certificados propios y notificaciones.
- Jefatura: dashboard y aprobaciones, sin edición de perfiles de usuarios.
- El historial muestra **Revisar** al administrador o jefe cuando el expediente está en revisión.
- Se eliminaron las sedes como ámbito operativo. La columna heredada `laboratorio` permanece por compatibilidad, sin uso en la UI.
- Los selectores de equipos, patrones y clientes contienen valores ficticios **DEMO** en una instalación nueva de desarrollo. Ejecute `python -m flask --app run:app seed-example-catalog` para añadirlos por decisión expresa a una base de desarrollo ya poblada. Nunca utilice los valores DEMO para emitir certificados válidos.
- `python-dotenv` facilita el uso del `.env` local para Gmail y otras configuraciones. No guarde contraseñas en Git.

**Comprobación:** después de `pip install -r requirements-dev.txt`, ejecutar `pytest -q` (incluye `tests/test_roles.py`). Esta entrega pasó compilación Python/JavaScript, parseo/renderizado de plantillas y ensayo de migraciones SQLite; las pruebas con Flask no se pudieron ejecutar en el entorno de generación por falta de paquetes y conectividad.
