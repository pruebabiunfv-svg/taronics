# Despliegue de Tatronics / CalibPro en Railway

## 1. Qué se corrigió

El fallo reportado `Worker failed to boot` tenía una causa concreta:
en producción no estaba definida `SECRET_KEY`. La aplicación **requiere** una
clave estable y secreta para firmar sesiones; no se genera una nueva en cada
arranque porque eso invalidaría las sesiones y no sería una solución segura.

El Dockerfile ahora enlaza Gunicorn a `0.0.0.0` en el puerto indicado por
`PORT` (si no existe, 8000). El archivo `railway.json` configura una comprobación
HTTP en `/inicio`. Se conserva la estructura de Flask, los módulos y SQLite.

## 2. Preparar el servicio

1. Despliega la **carpeta `tatronics` como raíz del proyecto**: en la raíz deben
   quedar `Dockerfile`, `run.py`, `requirements.txt` y `railway.json`.
2. En Railway abre tu proyecto → servicio `taronics` → **Variables**.
3. En tu equipo ejecuta este comando para obtener una clave aleatoria:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

4. Crea en Railway **`SECRET_KEY`** con el valor obtenido. Guárdalo en un
   administrador de contraseñas: si lo cambias después, se cerrarán las sesiones
   existentes. **No publiques el valor ni lo incluyas en este ZIP, Git o .env.example.**
5. Configura las otras variables siguientes y **aplica/despliega los cambios
   pendientes**. Railway no utiliza automáticamente `.env.example`.

### Variables sugeridas

| Clave | Valor en Railway | Uso |
| --- | --- | --- |
| `SECRET_KEY` | Resultado aleatorio de 64 caracteres | **Obligatoria.** Mantener estable y privada. |
| `CALIBPRO_ENV` | `production` | Ya viene en el Dockerfile, puede declararse explícitamente. |
| `ALLOW_PUBLIC_REGISTRATION` | `false` | Impide altas abiertas; administración crea usuarios. |
| `SEED_DEMO_DATA` | `false` | Nunca cargar usuarios demo en producción. |
| `SEED_CATALOG_EXAMPLES` | `false` | No cargar catálogos de ejemplo. |
| `DATABASE_PATH` | `/app/instance/calibpro.db` | Base SQLite. |
| `UPLOAD_FOLDER` | `/app/instance/uploads/photos` | Fotografías adjuntas. |
| `PUBLIC_BASE_URL` | `https://<tu-dominio-real>` | Necesaria para PDF con QR y verificación pública. Configurar después de obtener el dominio. |

`PORT` puede dejarse a Railway: el servidor lo detecta en tiempo de ejecución.
No agregues `SECRET_KEY` con comillas al copiar desde el formulario de Variables.

Si activas `ALLOW_PUBLIC_REGISTRATION=true`, configura también un
`REGISTRATION_CODE` secreto: sin él, la aplicación detendrá el inicio para
evitar registros públicos desprotegidos.

## 3. Hacer persistentes los datos (importante)

La base de datos es **SQLite**. Los archivos que se crean en un contenedor sin
volumen pueden desaparecer al volver a desplegar. Para guardar registros,
usuarios, diagnósticos y fotografías:

1. En Railway, agrega un **Volume** al servicio y establece el punto de montaje
   exactamente en **`/app/instance`**. Hazlo *antes* de empezar a registrar datos
   que necesites conservar.
2. Conserva `DATABASE_PATH=/app/instance/calibpro.db` y
   `UPLOAD_FOLDER=/app/instance/uploads/photos`.
3. Railway monta estos volúmenes con propietario `root`. El Dockerfile usa
   normalmente un usuario sin privilegios (`tatronics`). Si al montar el
   volumen aparecen errores `Permission denied` o `unable to open database file`,
   Railway documenta como alternativa configurar `RAILWAY_RUN_UID=0` en Variables
   para ejecutar el contenedor con permisos de escritura. **Esto hace que el
   proceso corra como root**; evalúa ese compromiso de seguridad antes de usarlo
   en un servicio público. Una alternativa futura es implementar un proceso de
   inicialización que ajuste permisos y luego baje privilegios.
4. Configura copias de seguridad del volumen y prueba una restauración.

**Atención al cambiar a un volumen:** los datos que estaban dentro de la imagen
o en el contenedor anterior **no se copian automáticamente al volumen nuevo**.
Respalda y migra los datos antes de habilitarlo. El ZIP incluye `migration/` como
material legado para recuperación; el Dockerfile no lo inserta automáticamente.
No subas bases reales o credenciales a repositorios públicos.

Por las limitaciones del volumen/SQLite, utiliza una sola réplica. Gunicorn
queda configurado con un proceso trabajador y cuatro hilos.

## 4. Publicar el sitio y comprobarlo

1. Consulta `Deploy Logs`: ya no debería aparecer el error por `SECRET_KEY`.
2. En **Settings → Networking → Public Networking**, pulsa **Generate Domain**.
   Comprueba `https://<dominio>/inicio`, que debe responder con HTTP 200.
3. Actualiza `PUBLIC_BASE_URL` con esa dirección HTTPS, sin barra final, y
   aplica los cambios en Railway.
4. Comprueba `/auth/login`. Si la base es nueva, crea el primer administrador
   conectando una terminal al contenedor mediante **Railway CLI**:

   ```bash
   railway ssh -s taronics
   python -m flask --app run:app create-admin
   ```

   El comando solicitará nombre, correo y contraseña de al menos 12 caracteres.
   No hay contraseñas predeterminadas.

5. Una vez inicies sesión, verifica operaciones reales de lectura y escritura,
   creación de clientes, registros, fotos y revisión de certificados.

## 5. Diagnóstico rápido

| Mensaje en Deploy Logs | Qué revisar |
| --- | --- |
| `Falta una SECRET_KEY segura` | La clave debe estar en **Variables** del mismo servicio y entorno desplegado. |
| `El registro de producción requiere REGISTRATION_CODE` | Configura el código o deja `ALLOW_PUBLIC_REGISTRATION=false`. |
| `Permission denied` / `unable to open database file` | Montaje, propietario del volumen, rutas de SQLite y fotos. |
| `Application failed to respond` | Puerto `PORT`, dominio asociado al puerto correcto y `0.0.0.0`. |
| La web abre, pero el QR falla | `PUBLIC_BASE_URL` debe apuntar al dominio público HTTPS. |
| Datos desaparecen tras redeploy | Falta volumen persistente o se ha montado en otra ruta. |

## 6. Limitaciones de esta revisión

Se validan los archivos de configuración y la sintaxis, pero no es posible
verificar el estado del servicio Railway ni sus variables desde este ZIP.
Tampoco es posible crear una `SECRET_KEY` secreta **dentro del código** como
sustituto de la variable real del servicio. La prueba final requiere iniciar
el contenedor con las variables correctas y consultar los nuevos Deploy Logs.

### Documentación de Railway

- [Variables](https://docs.railway.com/variables)
- [Puertos y escucha HTTP](https://docs.railway.com/networking/troubleshooting/application-failed-to-respond)
- [Volúmenes y permisos](https://docs.railway.com/volumes)
- [Dominio público](https://docs.railway.com/networking/public-networking)
- [CLI: SSH](https://docs.railway.com/cli/ssh)
