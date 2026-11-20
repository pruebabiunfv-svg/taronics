# Tatronics CalibPro · Acceso por perfiles

## Un solo inicio de sesión
`/auth/login` valida las credenciales y el servidor obtiene el rol actual desde la base de datos. No existe un login independiente ni una contraseña compartida por perfil.

| Acción | Administrador | Jefatura | Técnico |
|---|:---:|:---:|:---:|
| Dashboard global | Sí | Sí | No |
| Personal, altas y roles | Sí | No | No |
| Clientes y patrones (gestión) | Sí | Sí | No |
| Equipos (consulta) | Sí | Sí | Sí |
| Equipos (alta/modificación) | Sí | Sí | No |
| Diagnóstico (propio) | Sí | Sí | Sí |
| Historial | Todos | Todos | Solo propios |
| Certificados PDF | Todos aprobados | Todos aprobados | Solo propios aprobados |
| Aprobar/rechazar (contraseña y autor distinto) | Sí | Sí | No |
| Gmail de certificados aprobados | Sí | Sí | No |
| Estadísticas y auditoría | Sí | Sí | No |
| Notificaciones | Sí | Sí | Sí |

El técnico entra a **Mi inicio**, con indicadores propios. El administrador entra al **Dashboard ejecutivo** y tiene **Personal y accesos**. Jefatura comparte las funciones de supervisión, pero no administra usuarios.

### Crear el primer administrador
`python -m flask --app run:app create-admin`.

Desde **Personal y accesos** se crean técnicos y jefaturas, y se pueden activar, desactivar o cambiar perfiles. No se entrega ningún usuario ni contraseña de ejemplo.

## Sin divisiones por sedes
Se han retirado las sedes del registro, menú y gestión de personal. El antiguo campo `laboratorio` de SQLite permanece sin uso para poder leer bases anteriores sin eliminar datos durante la migración. No existe filtro de información por sede.

## Catálogos de ejemplo para desplegables
En **desarrollo** (`CALIBPRO_ENV=development`) `SEED_CATALOG_EXAMPLES=true` por defecto llena un **almacén vacío y sin diagnósticos** con 2 clientes ficticios, 4 equipos y 4 patrones (presión, temperatura, masa y electricidad). Todos tienen prefijo **DEMO** y son solo para pruebas. **Los expedientes DEMO no pueden someterse a aprobación para emitir documentos reales.**

En bases ya usadas con diagnósticos no se insertan ejemplos automáticamente. Para agregar ejemplos por decisión expresa en un entorno de desarrollo, usa el comando `python -m flask --app run:app seed-example-catalog`, y confirma la operación. En producción los datos DEMO se mantienen deshabilitados salvo que alguien los importe manualmente; no se recomienda.

**Para producción:** configure `CALIBPRO_ENV=production`, `SEED_CATALOG_EXAMPLES=false`, desactive el registro público, importe clientes y equipos reales y registre patrones y certificados de trazabilidad auténticos. Respaldar la base de datos antes de migrar. Probar roles y autorizaciones en un entorno de ensayo antes de publicar.

## Flujo de aprobación en el Historial
Cuando el certificado pase a `en_revision`, el administrador o jefe verá **Revisar**, que abre el modal con **Aprobar** o **Rechazar**, observaciones y confirmación de contraseña. Se impide aprobar expedientes propios. Los técnicos ven el estado sin acción de aprobación. Un expediente aprobado permite descargar PDF con QR; solo administración/jefatura puede enviarlo por Gmail.
