# SIGS · Gestión de siniestros y prevención de fraude

Prototipo de mi Trabajo Final de Graduación (Licenciatura en Informática, Universidad Siglo 21).
Autor: Lucas Agustín Segura.

SIGS es una aplicación web para peritos de seguros. Cada perito lleva sus expedientes (datos del siniestro, documentos, notas, tareas y cierre) y el sistema cruza cada caso confirmado con los antecedentes de la red por persona o por vehículo. Con eso calcula un indicador de prioridad de 0 a 100 a partir de 8 reglas versionadas (RS-1.0), que muestra qué regla se activó y con qué dato. Los antecedentes de otros peritos solo se ven como un resumen reducido, y cada consulta queda en una auditoría que no se puede modificar.

Todos los datos del repositorio son ficticios.

## Qué se necesita

- Docker con Docker Compose v2. En Windows y macOS alcanza con Docker Desktop.
- Los puertos 80 y 8025 libres. Si alguno está ocupado, se cambia en `.env` con `APP_PORT` o `MAILPIT_PORT`.

No hace falta instalar Python, Node ni PostgreSQL: todo corre en contenedores.

## Cómo levantarlo

```bash
git clone https://github.com/lucass-segura/sigs-prototipo.git
cd sigs-prototipo
cp env.example .env        # opcional: sin .env se usan estos mismos valores
docker compose up --build
```

La primera vez tarda unos minutos porque se construyen las imágenes. Al arrancar, el backend crea las tablas y carga los datos de prueba si la base está vacía. Cuando termina:

- Aplicación: <http://localhost>
- Correos que envía el sistema (Mailpit): <http://localhost:8025>

Para apagarlo, `docker compose down`. Para volver a la demo original, borrando todo lo que se haya cargado, `docker compose down -v` y de nuevo `docker compose up`.

## Usuarios de prueba

La contraseña es la misma para todos: `Demo.Sigs#2026`

| Usuario | Rol | Espacio |
|---|---|---|
| perito08@sigs.test | Perito | Estudio Pericial Norte |
| perito11@sigs.test | Perito | Estudio Pericial Norte |
| perito15@sigs.test | Perito | Perito Independiente Sur |
| admin.norte@sigs.test | Administrador | Estudio Pericial Norte |
| admin.sur@sigs.test | Administrador | Perito Independiente Sur |
| superadmin@sigs.test | Superadministrador | Toda la plataforma |
| perito.escenarios@sigs.test | Perito | Escenarios de prueba |

## Un recorrido para probarlo

1. Entrar con `perito08@sigs.test`. El panel lista los expedientes ordenados por prioridad.
2. Abrir **EXP-2026-0147** (incendio total del vehículo AB123CD). Es el caso del Anexo 1 del TFG.
3. En la pestaña **Análisis** el indicador da 55, prioridad alta: cobertura reciente (25), pago reciente (20) y el mismo vehículo en el antecedente S-2025-0381 de otro estudio (25). Debajo están las reglas que no se activaron, con su explicación.
4. **Ver resumen** en S-2025-0381 muestra lo que se comparte de ese antecedente (resultado, valoración y justificación del perito) y aclara qué queda oculto. La consulta queda en la auditoría.
5. En **Seguimiento** están el tablero de tareas y las notas privadas. En **Documentos** se pueden subir y previsualizar archivos, y con **Nuevo croquis** dibujar cómo fue el siniestro.
6. En **Cierre** se registra el resultado, la conclusión y una valoración de 1 a 10 con su justificación. Si se marca una irregularidad, pide un respaldo: un documento o una observación.
7. **Nuevo siniestro** abre el registro en cinco pasos. Se puede ir y volver entre pasos sin perder lo cargado.
8. Para ver el bloqueo de cuenta: salir y fallar cinco veces el ingreso con `perito11@sigs.test`. La cuenta se bloquea y el aviso con el enlace para restablecer la contraseña llega a Mailpit.
9. Entrar con `admin.norte@sigs.test` y abrir **Auditoría**: aparecen los intentos fallidos, el bloqueo y la consulta del resumen. Desde **Usuarios** se dan de alta peritos; el enlace de primer ingreso también llega a Mailpit.
10. Con `superadmin@sigs.test` se crean espacios de trabajo y se publica una versión nueva de las reglas en **Reglas del indicador**.

Otros casos de la demo: EXP-2026-0160 (robo de rueda de auxilio, con el mismo dominio en varios antecedentes), EXP-2026-0139 (vinculado a un antecedente cerrado con irregularidad confirmada) y EXP-2026-0151 (sin antecedentes en la red).

## Pruebas

```bash
# Pruebas del backend: reglas, permisos, auditoría y seguridad
docker compose run --rm backend pytest

# Tabla de los 30 escenarios de las reglas, con precisión y sensibilidad
docker compose run --rm backend sh -c "python manage.py migrate -v0 && python manage.py seed_escenarios --si-vacia && python manage.py evaluar_escenarios"

# Pruebas de los scripts SQL (necesitan la carpeta db/ montada)
docker compose run --rm -v "$PWD/db:/db:ro" backend pytest tests/test_s25_scripts_sql.py
```

Los 30 escenarios esperan 36 activaciones de reglas y dan 100 % de precisión y de sensibilidad. Las pruebas de acceso hacen 24 pedidos directos a la API sin permiso, y cada uno se rechaza y queda registrado en la auditoría.

## Base de datos en SQL

En `db/sql/` están los scripts para crear la base desde cero y cargar los datos de prueba sin pasar por Django:

- `01_crear_base.sql`: roles, tablas, restricciones, triggers de la auditoría, permisos y las reglas RS-1.0.
- `02_cargar_datos_demo.sql`: usuarios, expedientes de la demo y los 30 escenarios.

Para usarlos con los contenedores:

```bash
docker compose down -v
docker compose up -d --wait db
./scripts/cargar_sql.sh
docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build
```

`cargar_sql.sh` también copia los archivos de la demo y ajusta los vencimientos de las tareas al día de la carga. Para cargarlos en un PostgreSQL propio, alcanza con correr los dos archivos con `psql` como superusuario. Si cambia el modelo de datos, se regeneran con `./scripts/generar_sql.sh`.

## Cómo está armado

```
backend/    API en Django 5 y Django REST Framework: permisos, auditoría y motor de reglas
frontend/   Interfaz en Next.js y TypeScript
nginx/      Proxy: / va al frontend y /api al backend
db/         Inicialización de PostgreSQL y scripts SQL
docs/       Especificación, decisiones de diseño, diccionario de datos y maquetas
scripts/    Scripts para la base en SQL y para armar un zip del repositorio
```

La base usa dos roles: uno es dueño de las tablas y solo aplica las migraciones; la aplicación usa otro que en la auditoría solo puede leer y agregar registros. Así la auditoría no se puede modificar ni siquiera con SQL directo.

En local todo funciona por HTTP. Para producción se activan las cookies seguras con `SECURE_COOKIES=true` detrás de HTTPS.
