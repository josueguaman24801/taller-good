# Taller Molina-Henze — Proyecto unificado

Este proyecto integra la interfaz visual del sitio principal con las funciones ampliadas de gestión del taller (jefe de taller, secretario, presupuestos, turnos y exportaciones). Se conservaron el CSS y las plantillas visuales principales del proyecto raíz, y se añadieron las pantallas necesarias para las funciones nuevas.

## Ejecutar en Windows

1. Crear/activar el entorno virtual.
2. Instalar dependencias: `pip install -r requirements.txt`
3. Aplicar migraciones: `python manage.py migrate`
4. Crear un usuario administrador si hace falta: `python manage.py createsuperuser`
5. Iniciar: `python manage.py runserver`

Abrir `http://127.0.0.1:8000/`.

### Correo para presupuestos
La configuración SMTP usa las variables de entorno `EMAIL_HOST_USER` y `EMAIL_HOST_PASSWORD`. Si no se configuran, Django muestra los correos en la terminal del servidor; en ese modo, el enlace de recuperación de contraseña se puede copiar desde allí. Para enviar correos reales, configurá ambas variables con credenciales SMTP válidas.

### Base de datos
Se incluye la base SQLite del proyecto raíz como referencia. Antes de usar datos reales, hacer una copia de seguridad de `db.sqlite3` y ejecutar `python manage.py migrate`. No se incluye la carpeta `.git` de ninguno de los ZIP para evitar mezclar historiales de repositorios distintos.

### Esquema relacionado al DER
Las migraciones `0007` a `0011` agregan disponibilidad, vehículos, órdenes de
trabajo, trabajos realizados y repuestos. También vinculan los turnos
existentes con clientes, vehículos y horarios, y convierten los turnos que ya
estaban en reparación en órdenes de trabajo. Los campos anteriores del turno se
conservan para no interrumpir las pantallas y reportes actuales. El DNI del
cliente, los datos de contacto ausentes en cuentas antiguas y los vínculos con
cuentas son opcionales para mantener los registros existentes. El formulario
para solicitar turno sigue pidiendo correo y teléfono.

La migración `0012` nombra las columnas como en el DER (`id_disponibilidad`,
`id_mecanico`, `id_usuario`, `id_orden`, `id_vehiculo`, `id_cliente`,
`id_servicio`) y crea el perfil de usuario con teléfono y los roles cliente,
mecánico, jefe del taller y secretario. Los roles de jefe y secretario también
habilitan sus paneles respectivos. El identificador, la contraseña hasheada y
los datos de autenticación siguen perteneciendo a la tabla de autenticación de
Django; el perfil se vincula mediante `id_usuario` para no duplicar
credenciales ni perder cuentas.

Después de actualizar el código, aplicar el esquema con
`python manage.py migrate`.
