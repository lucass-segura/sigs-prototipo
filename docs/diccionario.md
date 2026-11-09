# SIGS · Diccionario de datos de la base final

Describe la base de datos PostgreSQL 16 tal como queda después de aplicar las migraciones `0001` a `0008` (consulta hecha sobre `information_schema`, `pg_constraint`, `pg_indexes` y `pg_trigger` de una base migrada). Sirve para actualizar el diccionario del Entregable 4 (líneas 1477 a 1670, tablas 37 a 42). Todo en español; los datos de la demo son ficticios.

Convenciones:

- **Tipo** es el tipo de PostgreSQL. `varchar(n)` es texto con longitud máxima `n`; `text` no tiene límite; `jsonb` guarda JSON; `timestamptz` es fecha y hora con zona (se guarda en UTC y la aplicación trabaja en `America/Argentina/Buenos_Aires`).
- **Nulo** es `sí` si la columna admite `NULL`. Las columnas de texto «no nulas» pueden estar vacías (`''`) cuando se indica «puede quedar vacío».
- Toda tabla tiene `id bigint` como clave primaria (identidad autoincremental). Las claves foráneas (FK) se crean `DEFERRABLE INITIALLY DEFERRED` y llevan un índice propio; no se listan una por una.
- Los nombres de tabla y de columna coinciden con los diagramas `docs/referencias/der-*.png`. Las columnas que no están en los diagramas se marcan con **(extra)**.

## 1. Mapa de tablas

| Tabla | Para qué sirve | Solo altas en la base |
|---|---|---|
| `espacio_trabajo` | Estudio pericial o perito independiente; agrupa usuarios | no |
| `usuario` | Cuentas de la plataforma | no |
| `poliza` | Póliza del siniestro | no |
| `persona` | Persona global de la red, única por tipo e identificador | no |
| `bien` | Bien global de la red, único por identificador normalizado | no |
| `siniestro` | Expediente (entidad central) | no |
| `participacion` | Persona en un siniestro, con su rol | no |
| `bien_afectado` | Bien en un siniestro, con el daño | no |
| `documento` | Documento privado del expediente (el archivo está en un volumen, no en la base) | no |
| `nota` | Nota privada del expediente | no |
| `tarea` | Tarea del tablero del expediente | no |
| `tarea_cambio` | Historial de cambios de estado de una tarea (extra) | no |
| `cierre` | Cierre del expediente con valoración | **sí** |
| `conjunto_reglas` | Versión del conjunto de reglas | solo cambia `activo` |
| `regla` | Regla de una versión | **sí** (inmutable) |
| `evaluacion` | Resultado del indicador para un siniestro | **sí** |
| `senal` | Resultado de cada regla en una evaluación | **sí** |
| `auditoria` | Registro de acciones y rechazos | **sí** |
| `django_session` | Sesiones de Django (cookie `HttpOnly`) | no |
| `django_migrations`, `django_content_type`, `auth_permission`, `auth_group`, `auth_group_permissions` | Tablas del framework. Las últimas cuatro las crea Django pero el sistema no las usa (los permisos son propios, por rol) | no |

## 2. Tablas

### 2.1 `espacio_trabajo`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador del espacio. Agrupa a los usuarios del mismo estudio |
| `nombre` | varchar(150) | no | único | Nombre del estudio pericial o del perito independiente |
| `creado_en` | timestamptz | no | | Fecha de creación del espacio **(extra)** |

### 2.2 `usuario`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador del usuario |
| `espacio_id` | bigint | sí | FK → `espacio_trabajo` | Espacio al que pertenece. Nulo solo para el superadministrador |
| `nombre` | varchar(150) | no | | Nombre visible del usuario |
| `email` | varchar(254) | no | único | Correo de ingreso, único en todo el sistema y guardado en minúsculas |
| `rol` | varchar(20) | no | `perito`, `administrador` o `superadministrador` (validado por la aplicación) | Define el menú y las operaciones permitidas en la API |
| `activo` | boolean | no | | Falso cuando se da de baja: no puede ingresar y se conserva su historial |
| `contacto_email` | varchar(254) | no | puede quedar vacío | Correo que el perito decide mostrar a otros peritos; puede ser distinto del de ingreso |
| `contacto_visible` | boolean | no | | Si es verdadero, el correo de contacto aparece en el resumen de sus casos **cerrados o archivados** |
| `password` | varchar(128) | no | | Hash PBKDF2-SHA256 con sal **(extra)**. Un valor que empieza con `!` indica que todavía no definió contraseña |
| `last_login` | timestamptz | sí | | Último ingreso **(extra)** |
| `intentos_fallidos` | integer | no | `>= 0` | Ingresos fallidos seguidos; al 5.º se bloquea la cuenta **(extra)** |
| `bloqueado_en` | timestamptz | sí | | Momento del bloqueo (por intentos o por el administrador). Nulo = no bloqueada **(extra)** |
| `creado_en` | timestamptz | no | | Fecha de alta **(extra)** |

Restricción `usuario_espacio_nulo_solo_superadmin`: `espacio_id` es nulo si y solo si el rol es `superadministrador`.

### 2.3 `poliza`

Se crea una por siniestro.

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador de la póliza |
| `numero` | varchar(60) | no | | Número de póliza, por ejemplo `AUT-000123` |
| `compania` | varchar(150) | no | puede quedar vacío | Compañía aseguradora |
| `cobertura` | varchar(150) | no | puede quedar vacío | Cobertura, por ejemplo «Terceros completo con incendio total» |
| `inicio_vigencia` | date | sí | | Inicio de vigencia. La usa R01. Si hay valor, el hecho del siniestro no puede ser anterior |
| `primer_pago` | date | sí | | Fecha del primer pago. La usa R02 |

### 2.4 `persona`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador de la persona (global de la red) |
| `identificador` | varchar(40) | no | único junto con `tipo_identificador` | Número de documento sin puntos ni espacios y en mayúsculas. Se usa para la coincidencia exacta y no se muestra en el resumen |
| `tipo_identificador` | varchar(10) | no | `DNI`, `CUIT` o `PASAPORTE` (validado por la aplicación) | Dos personas coinciden solo si coincide también el tipo |
| `nombre` | varchar(150) | no | | Primer nombre con que se cargó la persona. **Nunca se devuelve a un cliente**: el nombre de cada caso está en `participacion.nombre` |

### 2.5 `bien`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador del bien (global de la red) |
| `tipo` | varchar(20) | no | `vehiculo`, `motocicleta`, `telefono`, `computadora` u `otro` (validado por la aplicación) | Tipo de bien. Solo `vehiculo` y `motocicleta` son identificables y cruzan entre casos |
| `identificador_norm` | varchar(60) | no | único | Identificador en mayúsculas y sin espacios, guiones ni puntos (`AB-123 CD` → `AB123CD`): la patente en los vehículos, el IMEI o el número de serie en otros bienes. **Es lo único por lo que dos bienes coinciden**: el motor y el chasis no son identificadores y nunca cruzan casos. Lo usa R06. Solo cruzan entre casos los bienes de tipo `vehiculo` y `motocicleta` (identificables por su patente); un teléfono, una computadora u otro bien se registra con su identificador, pero nunca coincide con el de otro caso |
| `descripcion` | varchar(250) | no | puede quedar vacío | Descripción global del bien. No se escribe ni se devuelve: la del caso está en `bien_afectado.descripcion` |
| `atributos` | jsonb | no | | Atributos globales del bien. Mismo criterio que `descripcion` |

### 2.6 `siniestro`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador del siniestro |
| `espacio_id` | bigint | no | FK → `espacio_trabajo` | Espacio dueño del expediente |
| `perito_id` | bigint | no | FK → `usuario` | Perito asignado, quien lo creó. **Solo él accede al expediente** |
| `poliza_id` | bigint | sí | FK → `poliza` | Póliza del caso. Para confirmar es obligatoria |
| `numero_expediente` | varchar(40) | no | único | Código visible del caso, por ejemplo `EXP-2026-0147`; si no se indica se genera `EXP-AAAA-NNNN` |
| `tipo` | varchar(150) | no | puede quedar vacío | Tipo de siniestro, por ejemplo «Incendio total del vehículo» |
| `fecha_hecho` | timestamptz | no | | Momento declarado del hecho. La usan R01, R02, R04 y R08 (con su fecha local). Su fecha local no puede ser anterior a `poliza.inicio_vigencia` (lo valida la API) |
| `fecha_denuncia` | date | sí | | Día en que se hizo la denuncia. La usa R08 |
| `numero_denuncia` | varchar(60) | no | puede quedar vacío | Número de la denuncia, por ejemplo `DEN-2026-0147` (Anexo 1) **(extra)** |
| `hora_denuncia` | time | sí | | Hora de la denuncia, por ejemplo `10:20`. R08 no la usa: sigue contando por `fecha_denuncia` **(extra)** |
| `asesor` | varchar(100) | no | puede quedar vacío | Asesor que carga la denuncia, por ejemplo «Código PA-031» **(extra)** |
| `intervenciones` | varchar(250) | no | puede quedar vacío | Quién intervino en el hecho, por ejemplo «Bomberos y policía» **(extra)** |
| `documentacion_adjunta` | text | no | puede quedar vacío | Documentación que declara la denuncia, por ejemplo «DNI, cédula del vehículo, 6 fotografías y constancia de bomberos. Acta policial pendiente». Los archivos reales están en `documento` **(extra)** |
| `lugar` | varchar(250) | no | puede quedar vacío | Lugar del hecho |
| `relato` | text | no | puede quedar vacío | Relato del hecho. Privado del expediente |
| `estado` | varchar(15) | no | `borrador`, `en_analisis`, `cerrado`, `archivado` o `anulado` (validado por la aplicación) | Estado del caso |
| `confirmado_en` | timestamptz | sí | | Momento en que el perito confirmó el caso. Sin este dato no se analiza ni cuenta como antecedente |
| `motivo_anulacion` | text | no | puede quedar vacío | Motivo de la anulación por carga errónea **(extra)** |
| `creado_en` | timestamptz | no | | Fecha de creación **(extra)** |
| `actualizado_en` | timestamptz | no | | Última modificación **(extra)** |

Índice `siniestro_estado_confirmado (estado, confirmado_en)` para buscar antecedentes.

### 2.7 `participacion`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Siniestro |
| `persona_id` | bigint | no | FK → `persona` | Persona |
| `rol` | varchar(15) | no | `asegurado`, `conductor`, `tercero` o `testigo` (validado por la aplicación) | Rol de la persona en el caso. Es el que se muestra en el resumen y el que usa R05 |
| `nombre` | varchar(150) | no | puede quedar vacío | Nombre de la persona tal como lo declaró el perito en este caso **(extra)**. Es del caso: no se comparte con otros espacios |

Único `(siniestro_id, persona_id, rol)` (`participacion_unica`): una persona puede tener varios roles en el mismo caso. Índices por `persona_id` y por `siniestro_id`.

### 2.8 `bien_afectado`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Siniestro |
| `bien_id` | bigint | no | FK → `bien` | Bien |
| `detalle_dano` | text | no | puede quedar vacío | Daño o pérdida del bien en ese siniestro. Queda en el expediente y no forma parte del resumen |
| `descripcion` | varchar(250) | no | puede quedar vacío | Descripción que declaró el perito para este caso **(extra)**, por ejemplo «Sedán modelo 2015» |
| `atributos` | jsonb | no | | Datos que declaró el perito para este caso **(extra)**, como `{"motor": "MTR-55821", "chasis": "CHS-90311"}`. No intervienen en las reglas |

Único `(siniestro_id, bien_id)` (`bien_afectado_unico`). Índices por `bien_id` y por `siniestro_id`.

### 2.9 `documento`

El archivo se guarda en el volumen privado `documentos` (`<siniestro_id>/<uuid>`) y solo se descarga por un endpoint que verifica el permiso.

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Expediente al que pertenece |
| `tipo` | varchar(60) | no | | Tipo indicado por el perito, por ejemplo «Fotografía» |
| `archivo_ref` | varchar(250) | no | | Ruta relativa del archivo dentro del volumen |
| `estado` | varchar(20) | no | | Estado del documento; vale `recibido` al subirlo |
| `recibido_en` | timestamptz | no | | Fecha y hora de carga |
| `nombre_original` | varchar(250) | no | puede quedar vacío | Nombre del archivo que subió el perito **(extra)** |
| `tipo_contenido` | varchar(120) | no | puede quedar vacío | Tipo MIME **(extra)** |
| `tamanio` | bigint | no | | Tamaño en bytes **(extra)** |
| `subido_por_id` | bigint | sí | FK → `usuario` | Quién lo subió **(extra)** |

### 2.10 `nota`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Expediente |
| `autor_id` | bigint | no | FK → `usuario` | Autor |
| `texto` | text | no | | Texto de la nota. Privada del perito asignado |
| `creada_en` | timestamptz | no | | Fecha y hora de la nota |

### 2.11 `tarea` y `tarea_cambio`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `tarea.id` | bigint | no | PK | Identificador |
| `tarea.siniestro_id` | bigint | no | FK → `siniestro` | Expediente |
| `tarea.titulo` | varchar(250) | no | | Título de la tarea |
| `tarea.estado` | varchar(10) | no | `pendiente`, `en_curso` o `hecha` (validado por la aplicación) | Columna del tablero |
| `tarea.vence_en` | date | sí | | Vencimiento opcional |
| `tarea.creada_en` | timestamptz | no | | Fecha de creación **(extra)** |
| `tarea_cambio.id` | bigint | no | PK | Identificador **(extra, tabla completa)** |
| `tarea_cambio.tarea_id` | bigint | no | FK → `tarea` | Tarea que cambió |
| `tarea_cambio.estado_anterior` | varchar(10) | no | puede quedar vacío | Estado antes del cambio |
| `tarea_cambio.estado_nuevo` | varchar(10) | no | | Estado después del cambio |
| `tarea_cambio.usuario_id` | bigint | no | FK → `usuario` | Quién hizo el cambio |
| `tarea_cambio.fecha` | timestamptz | no | | Cuándo |

### 2.12 `cierre` (solo altas)

Un siniestro puede tener varios cierres: el vigente es el último por `creado_en` e `id`. Cambiar la valoración crea un registro nuevo con su motivo.

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Expediente cerrado |
| `perito_id` | bigint | no | FK → `usuario` | Perito que cerró |
| `resultado_reclamo` | varchar(20) | no | `aprobado`, `rechazado`, `desistido` u `otra_finalizacion` (validado por la aplicación) | Resultado del reclamo informado por la compañía |
| `irregularidad` | boolean | no | | Hay una irregularidad confirmada **con respaldo**. Es el único dato que el sistema trata como fraude. Si es verdadera, la API exige un documento de respaldo o una observación |
| `conclusion` | text | no | la API la exige no vacía | Conclusión pericial |
| `valoracion` | smallint | no | `valoracion_1_a_10`: entre 1 y 10 | Valor de 1 a 10 sobre la veracidad del hecho, según la tabla 2 |
| `justificacion` | varchar(500) | no | no vacía (`~ '\S'`) | Fundamento obligatorio de la valoración |
| `creado_en` | timestamptz | no | | Fecha y hora del cierre |
| `motivo_cambio` | text | no | puede quedar vacío; la API lo exige al cambiar un cierre | Por qué se cambió la valoración **(extra)** |
| `documentos_respaldo` | jsonb | no | lista de ids de `documento` del mismo siniestro (la API lo valida) | Documentos que respaldan la irregularidad **(extra)**. No lo muestra el resumen |
| `observacion_respaldo` | varchar(500) | no | puede quedar vacío | Observación escrita que respalda la irregularidad **(extra)**. No la muestra el resumen |

Índice `cierre_siniestro_fecha_idx (siniestro_id, creado_en)`. Triggers `cierre_solo_altas` (UPDATE y DELETE) y `cierre_sin_truncate`.

### 2.13 `conjunto_reglas`

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `version` | varchar(20) | no | único | Nombre de la versión, por ejemplo `RS-1.0` |
| `vigente_desde` | date | no | | Fecha desde la que rige |
| `topes` | jsonb | no | | Topes por grupo, total y umbrales de prioridad: `{"grupos": {...}, "total": 100, "prioridad": {"media": 25, "alta": 50}}` |
| `activo` | boolean | no | índice único parcial `un_solo_conjunto_activo` | Solo una versión está activa. Es lo único que puede cambiar después de publicada |
| `creado_en` | timestamptz | no | | Fecha de publicación **(extra)** |
| `creado_por_id` | bigint | sí | FK → `usuario` | Superadministrador que la publicó **(extra)** |
| `basado_en_id` | bigint | sí | FK → `conjunto_reglas` | Versión de la que se copió **(extra)** |

Triggers `conjunto_reglas_sin_borrado` (DELETE) y `conjunto_reglas_solo_activo` (UPDATE: solo acepta el cambio de `activo`).

### 2.14 `regla` (inmutable)

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `conjunto_id` | bigint | no | FK → `conjunto_reglas` | Versión a la que pertenece |
| `codigo` | varchar(5) | no | único junto con `conjunto_id` | `R01` a `R08` |
| `nombre` | varchar(150) | no | | Nombre de la regla, por ejemplo «Cobertura reciente» |
| `grupo` | varchar(30) | no | | Grupo del tope: Cobertura, Persona, Bien, Antecedente o Denuncia |
| `parametros` | jsonb | no | | Umbrales y puntos de la regla (no están escritos en el código) |
| `puntos_max` | smallint | no | `>= 0` | Máximo de puntos que puede otorgar. La API no deja publicar un nivel que lo supere |

Trigger `regla_inmutable` (UPDATE y DELETE).

### 2.15 `evaluacion` (solo altas)

Cada recálculo crea una fila nueva; nunca se sobrescribe.

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `siniestro_id` | bigint | no | FK → `siniestro` | Siniestro evaluado |
| `conjunto_id` | bigint | no | FK → `conjunto_reglas` | Versión de reglas usada |
| `puntaje` | smallint | no | `>= 0` | Indicador de 0 a 100 después de aplicar los topes |
| `prioridad` | varchar(10) | no | `baja`, `media` o `alta` (validado por la aplicación) | Prioridad según el puntaje: 0–24 baja, 25–49 media, 50 o más alta |
| `entradas` | jsonb | no | | Fechas y datos del caso usados en el cálculo, para poder reproducirlo |
| `creada_en` | timestamptz | no | | Fecha y hora del cálculo |
| `motivo` | varchar(30) | no | `confirmacion`, `recalculo`, `antecedente_confirmado`, `antecedente_cerrado`, `antecedente_archivado`, `antecedente_anulado`, `nueva_version` o `escenario` (validado por la aplicación) | Qué disparó el cálculo **(extra)** |

Índice `evaluacion_siniestro_fecha_idx (siniestro_id, creada_en)`. Triggers `evaluacion_solo_altas` y `evaluacion_sin_truncate`.

### 2.16 `senal` (solo altas)

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `evaluacion_id` | bigint | no | FK → `evaluacion` | Evaluación |
| `regla_id` | bigint | no | FK → `regla` | Regla evaluada |
| `estado` | varchar(15) | no | `activada`, `no_activada` o `no_evaluable` (validado por la aplicación) | Resultado de la regla |
| `puntos` | smallint | no | `>= 0` | Puntos que aportó la regla antes de los topes de grupo (nunca más que `regla.puntos_max`) |
| `antecedentes` | jsonb | no | | Antecedentes que activaron la regla: `[{id, numero_expediente, fecha_hecho, vinculo}]` |
| `texto_explicacion` | text | no | puede quedar vacío | Explicación en el lenguaje del perito, generada desde la misma señal **(extra)** |
| `dato` | jsonb | no | | Valor del caso y umbral usados **(extra)** |

Triggers `senal_solo_altas` y `senal_sin_truncate`.

### 2.17 `auditoria` (solo altas)

| Columna | Tipo | Nulo | Restricciones | Significado |
|---|---|---|---|---|
| `id` | bigint | no | PK | Identificador |
| `usuario_id` | bigint | sí | FK → `usuario` | Usuario que realizó la acción. Nulo si no había sesión (por ejemplo un 401) |
| `siniestro_origen_id` | bigint | sí | FK → `siniestro` | Expediente desde el que se hizo la consulta (en los resúmenes es el origen) |
| `accion` | varchar(120) | no | | Operación, por ejemplo `ver_resumen_antecedente`, `cierre` o `GET /api/...` en los rechazos genéricos |
| `objeto` | varchar(250) | no | puede quedar vacío | Tipo e identificador del registro consultado o modificado, por ejemplo `siniestro:12` |
| `resultado` | varchar(10) | no | `permitido` o `rechazado` | Las solicitudes rechazadas por falta de permiso también se registran |
| `fecha` | timestamptz | no | la asigna el servidor (`auto_now_add`) | Momento de la acción, no el del navegador |
| `espacio_id` | bigint | sí | FK → `espacio_trabajo` | Espacio del usuario o del siniestro, para filtrar la auditoría **(extra)** |
| `detalle` | jsonb | no | | Datos de la acción, por ejemplo `{"estado": 404}` o `casos_recalculados` **(extra)** |

Índice `auditoria_espacio_fecha_idx (espacio_id, fecha)`. Triggers `auditoria_solo_altas` y `auditoria_sin_truncate`.

### 2.18 Tablas del framework

- `django_session (session_key varchar(40) PK, session_data text, expire_date timestamptz)`: sesiones de la cookie `HttpOnly`; vencen a los 60 minutos sin actividad.
- `django_migrations`, `django_content_type`, `auth_permission`, `auth_group` y `auth_group_permissions`: las crea Django. El sistema no usa grupos ni permisos de Django.

## 3. Reglas que protegen los datos

- **Solo altas.** Una función `sigs_bloquear_modificacion()` hace `RAISE EXCEPTION` en los triggers `BEFORE UPDATE OR DELETE FOR EACH ROW` de `auditoria`, `cierre`, `evaluacion` y `senal`, y en los `BEFORE TRUNCATE` de las mismas tablas. `regla` bloquea UPDATE y DELETE; `conjunto_reglas` bloquea DELETE y solo acepta cambiar `activo`.
- **Los triggers también valen para SQL directo**: el rol de la aplicación no es dueño de las tablas, por lo que no puede hacer `ALTER TABLE ... DISABLE TRIGGER` ni borrarlos.
- **Aplicación**: además, el modelo de Django impide `save()` sobre una fila existente, `delete()`, `QuerySet.update()` y `QuerySet.delete()` en las tablas de solo altas.

## 4. Roles de la base de datos

Se crean al inicializar el volumen (`db/init/01-rol-aplicacion.sh`). Ninguno es superusuario; el superusuario `postgres` existe solo dentro del contenedor `db`.

| Rol | Atributos | Qué hace |
|---|---|---|
| `sigs_owner` (`DB_OWNER_USER`) | `LOGIN NOSUPERUSER CREATEDB NOCREATEROLE`; dueño de la base `sigs` y de todas las tablas; es miembro de `sigs_app` | Aplica las migraciones, carga la demo (`seed_demo`, `seed_escenarios`), corre los comandos de `manage.py` y las pruebas |
| `sigs_app` (`DB_APP_USER`) | `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE`; no es dueño de nada; `CONNECT` sobre la base | Es el que usa el servidor web (Gunicorn) |

Permisos de `sigs_app` (migración `0004`):

| Objeto | Permisos |
|---|---|
| Esquema `public` | `USAGE` |
| Todas las tablas comunes (`espacio_trabajo`, `usuario`, `poliza`, `persona`, `bien`, `siniestro`, `participacion`, `bien_afectado`, `documento`, `nota`, `tarea`, `tarea_cambio`, `conjunto_reglas`, `regla`, `django_session`, etc.) | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `auditoria`, `cierre`, `evaluacion`, `senal` | **solo `SELECT` e `INSERT`** (sin `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES` ni `TRIGGER`) |
| Secuencias | `USAGE`, `SELECT` |
| Tablas futuras (`ALTER DEFAULT PRIVILEGES`) | `SELECT`, `INSERT`, `UPDATE`, `DELETE`; si una migración futura crea otra tabla de solo altas tiene que revocar el resto |

`conjunto_reglas` y `regla` quedan con permisos comunes, pero sus triggers impiden editar o borrar lo que no sea `activo`. `PUBLIC` no tiene `UPDATE`, `DELETE` ni `TRUNCATE` sobre las tablas de solo altas.

## 5. Diferencias con el diccionario del Entregable 4

Valores del E4 (línea del campo; la longitud está dos líneas más abajo) contra la base final.

| Campo | E4 | Base final |
|---|---|---|
| `siniestro.numero_expediente` (E4:1484) | Texto, longitud 20 | `varchar(40)` |
| `siniestro.tipo` (E4:1488) | Texto, longitud 40 | `varchar(150)` |
| `siniestro.estado` (E4:1500) | Texto, longitud 20 | `varchar(15)` |
| `siniestro.fecha_hecho` (E4:1492) | «Momento declarado del hecho» | Además su fecha local no puede ser anterior a `poliza.inicio_vigencia` (la API lo rechaza) |
| `evaluacion.entradas` (E4:1523) y `senal.antecedentes` (E4:1535) | Sin detalle | Las entradas solo incluyen antecedentes con fecha del hecho anterior a la del caso; `senal.antecedentes` lista `{id, numero_expediente, fecha_hecho, vinculo}` |
| `evaluacion.motivo` | No figura | Columna nueva, `varchar(30)`, con 8 valores |
| `senal.texto_explicacion`, `senal.dato` | No figuran | Columnas nuevas (`text` y `jsonb`) |
| `senal.puntos` (E4:1531) | «Puntos que aportó la regla antes de los topes» | Igual; además nunca supera `regla.puntos_max` |
| `cierre.resultado_reclamo` (E4:1546) | Texto, longitud 30; «Aprobado, rechazado u otra finalización» | `varchar(20)`; cuatro valores: `aprobado`, `rechazado`, `desistido`, `otra_finalizacion` |
| `cierre.irregularidad` (E4:1550) | «Indica si hay una irregularidad confirmada con respaldo» | Igual, pero ahora la API exige el respaldo: columnas nuevas `documentos_respaldo` (`jsonb`) y `observacion_respaldo` (`varchar(500)`) |
| `cierre.conclusion` | No figura en la tabla 39 | `text`, obligatoria en la API |
| `cierre.motivo_cambio` | No figura | Columna nueva `text` |
| `cierre.valoracion` (E4:1554) | Entero, valor de 1 a 10 | `smallint` con restricción `valoracion_1_a_10` en la base |
| `cierre.justificacion` (E4:1558) | Texto, 500 | `varchar(500)` con restricción de no vacía en la base |
| `espacio_trabajo.nombre` (E4:1573) | Texto, longitud 80 | `varchar(150)` |
| `espacio_trabajo.id` (E4:1569) | Entero | `bigint` |
| `usuario.espacio_id` (E4:1577) | «Espacio al que pertenece el usuario» | Nulo solo para el superadministrador (restricción en la base) |
| `usuario.email` (E4:1581) | Texto, longitud 120 | `varchar(254)` |
| `usuario.rol` (E4:1585) | Texto, 20 | Igual (`varchar(20)`) |
| `usuario.contacto_email` (E4:1593) | Texto, longitud 120 | `varchar(254)` |
| `usuario.contacto_visible` (E4:1597) | «aparece en el resumen de los antecedentes en los que intervino» | Aparece solo en los resúmenes de casos **cerrados o archivados** (HU-17, criterio 1) |
| `usuario` | Solo 6 campos descritos | Además `password`, `last_login`, `intentos_fallidos`, `bloqueado_en` y `creado_en` |
| `auditoria.accion` (E4:1616) | Texto, longitud 40 | `varchar(120)` |
| `auditoria.objeto` (E4:1620) | Texto, longitud 60 | `varchar(250)` |
| `auditoria.resultado` (E4:1624) | Texto, longitud 15 | `varchar(10)` |
| `auditoria.siniestro_origen_id` (E4:1612) | «Es obligatorio para consultar antecedentes» | Admite nulo (los rechazos y las acciones sin expediente no lo tienen); lo completa la aplicación en las consultas de antecedentes |
| `auditoria` | Solo 6 campos descritos | Además `espacio_id` y `detalle` |
| `persona.identificador` (E4:1640) | Texto, longitud 20 | `varchar(40)` |
| `persona.nombre` | No figura | `varchar(150)`; nunca se devuelve a un cliente (el nombre del caso está en `participacion.nombre`) |
| `participacion.rol` (E4:1648) | Texto, longitud 20 | `varchar(15)` |
| `participacion.nombre` | No figura | Columna nueva `varchar(150)` |
| `bien.identificador_norm` (E4:1656) | Texto, longitud 40; «Dominio, número de motor, chasis, IMEI o número de serie» | `varchar(60)`; el motor y el chasis **no** son identificadores: solo coincide la patente, y solo en los bienes `vehiculo` y `motocicleta` (el IMEI o el número de serie se registran pero no cruzan) |
| `bien.atributos` (E4:1660) | «Datos que dependen del tipo de bien, como marca o modelo» | Igual en `bien`, pero la API no lo escribe ni lo devuelve: los atributos del caso (motor, chasis, etc.) están en `bien_afectado.atributos` |
| `bien_afectado.detalle_dano` (E4:1664) | Texto, longitud 255 | `text`, sin límite |
| `bien_afectado.descripcion`, `bien_afectado.atributos` | No figuran | Columnas nuevas (`varchar(250)` y `jsonb`) |
| `siniestro.numero_denuncia`, `hora_denuncia`, `asesor`, `intervenciones`, `documentacion_adjunta` | No figuran (están en el Anexo 1 pero no en el diccionario) | Columnas nuevas (`varchar(60)`, `time`, `varchar(100)`, `varchar(250)` y `text`); la fecha de la denuncia sigue siendo `date` |
| `bien.tipo` (E4:1652) | «Vehículo, motocicleta, teléfono, computadora u otro bien» | Igual, pero solo `vehiculo` y `motocicleta` cruzan entre casos; los demás tipos se registran sin cruzar |
| Tablas `tarea_cambio` y `conjunto_reglas.creado_por_id` / `basado_en_id`, `siniestro.motivo_anulacion` / `creado_en` / `actualizado_en`, `documento.nombre_original` / `tipo_contenido` / `tamanio` / `subido_por_id`, `tarea.creada_en` | No figuran | Extras técnicos nuevos |
