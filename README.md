# SIGS · Sistema Integral de Gestión de Siniestros y Prevención de Fraude

Prototipo del Trabajo Final de Graduación de **Lucas Agustín Segura** (Licenciatura en Informática, Universidad Siglo 21).

SIGS es una plataforma web para peritos de seguros. Permite:

- Gestionar expedientes de siniestros privados de cada espacio de trabajo: datos, documentos, notas, tareas y cierre.
- Relacionar cada siniestro confirmado con sus antecedentes en la red mediante un grafo de personas, bienes y siniestros, a dos saltos.
- Calcular un **indicador de prioridad de 0 a 100** con un conjunto versionado de 8 reglas (RS-1.0) que es explicable y reproducible.
- Consultar **resúmenes minimizados** de antecedentes, solo desde un siniestro confirmado. Cada consulta queda en una **auditoría que nadie puede editar ni borrar**.

> **Todos los datos son ficticios.** Las personas, los vehículos, las pólizas, los correos y los expedientes se inventaron para la demo y las pruebas.

## Requisitos

- [Docker](https://docs.docker.com/get-docker/) con Docker Compose v2 (Docker Desktop en Windows y macOS ya lo trae).
- Los puertos **80** (aplicación) y **8025** (Mailpit) libres. Si están ocupados, se pueden cambiar en `.env` con `APP_PORT` y `MAILPIT_PORT`.
- No hace falta instalar Python, Node ni PostgreSQL.

## Puesta en marcha

```bash
# 1. Descomprimir el zip y entrar a la carpeta
cd SIGS-prototipo

# 2. (Opcional) Copiar la configuración de ejemplo. Sin .env se usan los mismos valores.
cp env.example .env

# 3. Construir y levantar todo
docker compose up --build
```

La primera vez tarda unos minutos porque construye las imágenes. Al arrancar, el backend:

1. aplica las migraciones con el rol dueño de la base (tablas, restricciones, triggers de la auditoría, permisos del rol de la aplicación y el conjunto de reglas RS-1.0);
2. carga los datos de demo (`seed_demo`) y los 30 escenarios de prueba (`seed_escenarios`), solo si la base está vacía.

No hacen falta pasos manuales. Cuando en la consola aparece `nginx` iniciado, la aplicación está lista.

La base usa dos roles sin superusuario (`DB_OWNER_USER` migra y carga la demo; `DB_APP_USER` es el que usa el servidor y en la auditoría solo puede leer e insertar). Los roles se crean al inicializar el volumen `datos`: si quedó uno de una versión anterior, empezá de cero con `docker compose down -v`.

| Servicio | URL |
|---|---|
| Aplicación | <http://localhost> |
| Mailpit (correos enviados por el sistema) | <http://localhost:8025> |
| Estado de la API | <http://localhost/api/health> |

Para detenerlo: `Ctrl+C` o `docker compose down`. Para empezar de cero, borrando la base y los documentos: `docker compose down -v`.

## Usuarios de demo

Todos usan la contraseña **`Demo.Sigs#2026`**.

| Correo | Rol | Espacio de trabajo | Contacto visible |
|---|---|---|---|
| `perito08@sigs.test` | Perito (PE-08) | Estudio Pericial Norte | Sí |
| `perito11@sigs.test` | Perito (PE-11) | Estudio Pericial Norte | No |
| `perito15@sigs.test` | Perito (PE-15) | Perito Independiente Sur | Sí |
| `admin.norte@sigs.test` | Administrador | Estudio Pericial Norte | |
| `admin.sur@sigs.test` | Administrador | Perito Independiente Sur | |
| `superadmin@sigs.test` | Superadministrador | (toda la plataforma) | |
| `perito.escenarios@sigs.test` | Perito | Escenarios de prueba (TT-02) | |

## Recorrido sugerido

1. **Ingresar como perito.** Abrí <http://localhost> y entrá con `perito08@sigs.test`. El panel **Mis expedientes** muestra los casos ordenados por prioridad.
2. **Abrir EXP-2026-0147 (Incendio total del vehículo).** En la pestaña **Datos** están la póliza (cobertura «Terceros completo con incendio total»), el relato, las personas y el vehículo AB123CD (sedán modelo 2015, motor MTR-55821, chasis CHS-90311), como en el Anexo 1 del Entregable 4, junto con el número de denuncia (DEN-2026-0147), la hora de la denuncia (10:20), el asesor (Código PA-031), las intervenciones (bomberos y policía) y la documentación adjunta. Cada perito ve **solo sus propios expedientes**: si ingresás con `perito11@sigs.test` (mismo espacio) y pedís ese expediente por la API, responde 404 y queda como rechazo en la auditoría.
3. **Ver el análisis.** En la pestaña **Análisis** el indicador da **55 / 100, prioridad alta**:
   - R01 Cobertura reciente: 25 (el hecho ocurrió 23 días después del inicio de vigencia).
   - R02 Pago reciente: 20 (el primer pago fue 8 días antes del hecho). La cobertura queda en 30 por el tope.
   - R06 Bien repetido: 25 (el vehículo figura en el antecedente S-2025-0381 de otro espacio).

   Debajo están las reglas que no se activaron, con su explicación, y la coincidencia en la red con la valoración promedio.
4. **Abrir el resumen.** Con **Ver resumen** en S-2025-0381 se ve solo lo compartido: tipo, fecha, vínculo, resultado, irregularidad, valoración, justificación, perito responsable y su correo (porque PE-15 lo habilitó y el antecedente está cerrado; en un antecedente en análisis el correo no se muestra). Un antecedente solo cuenta si su fecha del hecho es anterior a la del caso analizado. La pantalla aclara qué queda oculto. La consulta queda en la auditoría.
5. **Seguimiento y documentos.** En **Seguimiento** se mueven tareas entre columnas (arrastrando o con los botones), se agregan tareas con vencimiento y notas privadas; la página **Tareas** las agrupa por vencimiento y se filtra por texto, expediente, estado y vencimiento (los filtros quedan en la URL). En **Documentos** se sube, se **previsualiza** (imágenes, PDF y texto, sin salir de la página) y se descarga un archivo, solo por la API y con verificación de permiso; el HTML y el SVG nunca se muestran en línea. **Nuevo croquis** abre un editor para representar el siniestro (calles, vehículos, personas, flechas, impacto, texto y lápiz): se guarda como documento de tipo «Croquis» (imagen PNG) y se puede reabrir y editar, y cada edición guardada crea un documento nuevo. En el panel y en las coincidencias, la fila completa es clicable.
6. **Cerrar con valoración.** En **Cierre** se carga el resultado, la irregularidad, la **conclusión (obligatoria)**, una valoración de 1 a 10 (con el texto completo de la escala) y la justificación, que también es obligatoria. Si marcás «Irregularidad confirmada = Sí» hace falta un **respaldo**: elegir un documento del expediente (subilo antes en **Documentos**) o escribir una observación. Después se puede **cambiar la valoración** con un motivo: el registro anterior se conserva. Al cerrar, archivar o anular un caso, los casos en análisis que lo tienen como antecedente se **recalculan solos** (se crea una evaluación nueva, la anterior se conserva). El botón **Recalcular** sigue disponible.
7. **Otros casos de la demo:**
   - **EXP-2026-0160**, robo de rueda de auxilio: el dominio se repite en varios antecedentes de los dos espacios.
   - **EXP-2026-0139**: activa R07 por un antecedente cerrado con irregularidad confirmada. El caso anulado EXP-2026-0120 comparte el vehículo y **no** aparece como antecedente.
   - **EXP-2026-0151**: no tiene coincidencias y muestra "No hay antecedentes accesibles en la red".
8. **Probar el bloqueo de cuenta.** Salí e intentá ingresar 5 veces con `perito11@sigs.test` y una contraseña incorrecta. El mensaje nunca dice qué dato falló. Al 5.º intento la cuenta queda bloqueada. En **Mailpit** (<http://localhost:8025>) llega el correo de aviso con el enlace para restablecer la contraseña. El enlace es de un solo uso, vence en 1 hora y desbloquea la cuenta.
9. **Ingresar como administrador.** Con `admin.norte@sigs.test`:
   - En **Auditoría** se ven los intentos fallidos, el bloqueo, las consultas de resúmenes y los rechazos, con filtros por usuario, acción y resultado. Ningún registro se puede editar ni borrar.
   - En **Usuarios** se da de alta a un perito (el enlace de primer ingreso llega a Mailpit), se lo da de baja o se lo bloquea cerrando sus sesiones.
10. **Ingresar como superadministrador.** Con `superadmin@sigs.test` se crean espacios de trabajo con su administrador y se publica una nueva versión de las reglas desde **Reglas del indicador**. Todos los casos en análisis se recalculan con la versión nueva y las evaluaciones anteriores conservan la versión con la que se calcularon.

Al registrar un siniestro, la fecha del hecho no puede ser anterior al inicio de vigencia de la póliza: el formulario muestra el error junto al campo.

## Pruebas

Con los contenedores construidos:

```bash
# Todas las pruebas del backend (reglas, accesos, funcionales y seguridad)
docker compose run --rm backend pytest

# Tabla de los 30 escenarios con precisión y sensibilidad
docker compose run --rm backend sh -c "python manage.py migrate -v0 && python manage.py seed_escenarios --si-vacia && python manage.py evaluar_escenarios"
```

Las pruebas cubren:

- **Reglas:** los 30 escenarios con su resultado exacto (reglas activadas, puntos, topes, total y prioridad), la reproducibilidad (mismas entradas y misma versión dan el mismo resultado) y el versionado.
- **Acceso:** 8 pruebas × 3 solicitudes directas a la API = 24 rechazos. Cada uno responde 403 o 404 sin filtrar datos y queda en la auditoría con `resultado = rechazado`. Solo el perito asignado accede a un expediente: otro perito, incluso del mismo espacio, recibe 404.
- **Bienes identificables:** solo los vehículos y las motos se cruzan con otros casos por su patente; un teléfono, una computadora u otro bien se registra en el caso pero nunca cruza.
- **Reglas del Entregable 4:** antecedentes solo anteriores al hecho, R03 por persona, recálculo automático, respaldo de la irregularidad, conclusión obligatoria y hecho dentro de la vigencia.
- **Funcionales (F1 a F4) y seguridad:** bloqueo al 5.º intento con correo, mensaje genérico, enlace de 1 hora y de un solo uso, baja, y auditoría inmodificable incluso con SQL directo del usuario de la aplicación.
- Al menos un criterio de aceptación de cada historia de usuario (HU-01 a HU-17).

### Nota sobre los escenarios

En los escenarios R04 activa, R04 no activa, R04 límite y R05 activa, la regla R03 (persona recurrente) se activa siempre. Pasa por su propia definición: un antecedente de la misma persona dentro de los 90 días, o de los 10 meses, también está dentro de los 12 meses. Por eso esos escenarios documentan R03 como esperada, y el total esperado es de **36 activaciones** (16 por regla + 20 combinadas), con 0 falsos positivos y 0 falsos negativos.

## Base de datos por SQL

Además del arranque normal (la aplicación migra y carga la demo sola), la base se puede armar con dos scripts SQL de `db/sql/`. Sirven para **ver el esquema completo en un solo archivo**, **crear la base en un PostgreSQL propio** (sin Django) o **probar la aplicación con datos cargados desde SQL**:

| Archivo | Qué hace |
|---|---|
| `db/sql/01_crear_base.sql` | Crea los roles `sigs_owner` y `sigs_app` (si no existen), la base, todas las tablas, restricciones, índices, funciones, triggers de solo altas y permisos, las reglas RS-1.0 y las filas de `django_migrations` (Django ve la base como migrada). |
| `db/sql/02_cargar_datos_demo.sql` | Solo datos: usuarios, espacios, los casos de la demo (EXP-2026-0147 = 55, alta) y los 30 escenarios, con las secuencias ajustadas. Todos los usuarios usan la contraseña ficticia `Demo.Sigs#2026`. |
| `db/sql/documentos/` | Los archivos de los documentos de la demo, que `cargar_sql.sh` copia al volumen `documentos`. |
| `db/sql/compose.sin-seeds.yml` | Archivo extra de Compose: arranca la aplicación sin que corran `seed_demo` ni `seed_escenarios`. |

Los scripts **no se escriben a mano**: salen de una base real, migrada y sembrada con el mismo código de la aplicación, así que no se desfasan.

**Cargarlos en el contenedor `db` y probar la aplicación con esos datos:**

```bash
docker compose down -v                      # empezar de cero
docker compose up -d --wait db              # solo la base
./scripts/cargar_sql.sh                     # 01 y 02, y copia los documentos de la demo
docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build   # la aplicación, sin seeds
```

Después, <http://localhost> funciona igual que con el arranque normal: `perito08@sigs.test` / `Demo.Sigs#2026`. Para cargarlos en una base nueva con otro nombre, sin tocar la actual: `./scripts/cargar_sql.sh sigs_prueba` y, para usarla, `DB_NAME=sigs_prueba docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build`. Si la base ya tiene el esquema o los usuarios, los scripts lo avisan y no cargan nada (se pueden correr más de una vez).

**Cargarlos a mano con `psql`** (como superusuario de PostgreSQL; el nombre de la base se cambia con `-v base=...`):

```bash
psql -U postgres -f db/sql/01_crear_base.sql
psql -U postgres -f db/sql/02_cargar_datos_demo.sql
```

**Regenerarlos** cuando cambie una migración o los datos de demo (levanta una base descartable en un proyecto de Compose aparte, `sigs_generar`, que borra al terminar; no toca tu base):

```bash
./scripts/generar_sql.sh
```

La prueba `backend/tests/test_s25_scripts_sql.py` compara los scripts con la base migrada y falla si se desfasan. Dentro del contenedor la carpeta `db/` no está, así que se corre montándola:

```bash
docker compose run --rm -v "$PWD/db:/db:ro" backend pytest tests/test_s25_scripts_sql.py
```

## Estructura

```
backend/    Django 5 + Django REST Framework (API, permisos, auditoría y motor de reglas)
frontend/   Next.js (App Router) + TypeScript
nginx/      Proxy inverso: / → frontend, /api → backend
db/init/    Crea los roles de PostgreSQL (dueño y aplicación, ninguno superusuario)
db/sql/     Scripts SQL de creación de la base y de carga de los datos de demo (ver «Base de datos por SQL»)
docs/       Especificación del prototipo, decisiones de diseño y maquetas de referencia
scripts/    empaquetar.sh (zip limpio para Drive), generar_sql.sh y cargar_sql.sh (scripts SQL de la base)
```

Arquitectura: `docs/referencias/arquitectura.png`. En local se usa HTTP. Las cookies seguras se activan con `SECURE_COOKIES=true` para producción.

## Generar el zip para Drive

```bash
./scripts/empaquetar.sh
```

Genera `dist/SIGS-prototipo-AAAAMMDD.zip` con los archivos versionados del repositorio, sin `node_modules`, `.venv`, `.next`, `.env` ni volúmenes de Docker.
