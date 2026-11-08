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
2. **Abrir EXP-2026-0147 (Incendio total).** En la pestaña **Datos** están la póliza, las personas y el vehículo AB123CD.
3. **Ver el análisis.** En la pestaña **Análisis** el indicador da **55 / 100, prioridad alta**:
   - R01 Cobertura reciente: 25 (el hecho ocurrió 23 días después del inicio de vigencia).
   - R02 Pago reciente: 20 (el primer pago fue 8 días antes del hecho). La cobertura queda en 30 por el tope.
   - R06 Bien repetido: 25 (el vehículo figura en el antecedente S-2025-0381 de otro espacio).

   Debajo están las reglas que no se activaron, con su explicación, y la coincidencia en la red con la valoración promedio.
4. **Abrir el resumen.** Con **Ver resumen** en S-2025-0381 se ve solo lo compartido: tipo, fecha, vínculo, resultado, irregularidad, valoración, justificación, perito responsable y su correo (porque PE-15 lo habilitó). La pantalla aclara qué queda oculto. La consulta queda en la auditoría.
5. **Seguimiento y documentos.** En **Seguimiento** se mueven tareas entre columnas y se agregan notas privadas. En **Documentos** se sube y se descarga un archivo, solo por la API y con verificación de permiso.
6. **Cerrar con valoración.** En **Cierre** se carga el resultado, la irregularidad, la conclusión, una valoración de 1 a 10 y la justificación, que es obligatoria. Después se puede **cambiar la valoración** con un motivo: el registro anterior se conserva.
7. **Otros casos de la demo:**
   - **EXP-2026-0160**, robo de rueda de auxilio: el dominio se repite en varios antecedentes de los dos espacios.
   - **EXP-2026-0139**: activa R07 por un antecedente cerrado con irregularidad confirmada. El caso anulado EXP-2026-0120 comparte el vehículo y **no** aparece como antecedente.
   - **EXP-2026-0151**: no tiene coincidencias y muestra "No hay antecedentes accesibles en la red".
8. **Probar el bloqueo de cuenta.** Salí e intentá ingresar 5 veces con `perito11@sigs.test` y una contraseña incorrecta. El mensaje nunca dice qué dato falló. Al 5.º intento la cuenta queda bloqueada. En **Mailpit** (<http://localhost:8025>) llega el correo de aviso con el enlace para restablecer la contraseña. El enlace es de un solo uso, vence en 1 hora y desbloquea la cuenta.
9. **Ingresar como administrador.** Con `admin.norte@sigs.test`:
   - En **Auditoría** se ven los intentos fallidos, el bloqueo, las consultas de resúmenes y los rechazos, con filtros por usuario, acción y resultado. Ningún registro se puede editar ni borrar.
   - En **Usuarios** se da de alta a un perito (el enlace de primer ingreso llega a Mailpit), se lo da de baja o se lo bloquea cerrando sus sesiones.
10. **Ingresar como superadministrador.** Con `superadmin@sigs.test` se crean espacios de trabajo con su administrador y se publica una nueva versión de las reglas desde **Reglas del indicador**. Las evaluaciones anteriores conservan la versión con la que se calcularon.

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
- **Acceso:** 8 pruebas × 3 solicitudes directas a la API = 24 rechazos. Cada uno responde 403 o 404 sin filtrar datos y queda en la auditoría con `resultado = rechazado`.
- **Funcionales (F1 a F4) y seguridad:** bloqueo al 5.º intento con correo, mensaje genérico, enlace de 1 hora y de un solo uso, baja, y auditoría inmodificable incluso con SQL directo del usuario de la aplicación.
- Al menos un criterio de aceptación de cada historia de usuario (HU-01 a HU-17).

### Nota sobre los escenarios

En los escenarios R04 activa, R04 no activa, R04 límite y R05 activa, la regla R03 (persona recurrente) se activa siempre. Pasa por su propia definición: un antecedente de la misma persona dentro de los 90 días, o de los 10 meses, también está dentro de los 12 meses. Por eso esos escenarios documentan R03 como esperada, y el total esperado es de **36 activaciones** (16 por regla + 20 combinadas), con 0 falsos positivos y 0 falsos negativos.

## Estructura

```
backend/    Django 5 + Django REST Framework (API, permisos, auditoría y motor de reglas)
frontend/   Next.js (App Router) + TypeScript
nginx/      Proxy inverso: / → frontend, /api → backend
db/init/    Crea los roles de PostgreSQL (dueño y aplicación, ninguno superusuario)
docs/       Especificación del prototipo, decisiones de diseño y maquetas de referencia
scripts/    empaquetar.sh: genera el zip limpio para Drive
```

Arquitectura: `docs/referencias/arquitectura.png`. En local se usa HTTP. Las cookies seguras se activan con `SECURE_COOKIES=true` para producción.

## Generar el zip para Drive

```bash
./scripts/empaquetar.sh
```

Genera `dist/SIGS-prototipo-AAAAMMDD.zip` con los archivos versionados del repositorio, sin `node_modules`, `.venv`, `.next`, `.env` ni volúmenes de Docker.
