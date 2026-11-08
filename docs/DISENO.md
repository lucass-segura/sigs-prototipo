# SIGS · Decisiones de diseño y contrato de la API

Complementa `docs/PROTOTIPO_SIGS.md` (la fuente de verdad). Si algo de acá contradice esa especificación, gana la especificación y hay que reportarlo.
Todo en español: interfaz, mensajes, comentarios, docstrings y nombres del dominio. Las respuestas de error de la API usan `{"detalle": "<mensaje en español>"}`; los errores de validación usan `{"campo": ["mensaje"]}` (formato de DRF).

## 1. Estructura del repositorio

```
sigs/
  docker-compose.yml   nginx/nginx.conf   db/init/01-rol-aplicacion.sh   env.example
  backend/   Django 5.2 + DRF, una sola app `nucleo`
    config/settings.py (ya escrito)   config/urls.py   config/wsgi.py
    nucleo/models.py, autenticacion.py, permisos.py, auditoria.py, validadores.py,
           normalizacion.py, motor.py, coincidencias.py, resumen.py, correos.py,
           escenarios.py, demo.py, serializadores.py, vistas/*.py, urls.py,
           migrations/, management/commands/{seed_demo,seed_escenarios,evaluar_escenarios}.py
    tests/ (pytest + pytest-django, conftest.py, pytest.ini en backend/)
  frontend/  Next.js 15 App Router + TypeScript (Node 20), salida `standalone`
  docs/      PROTOTIPO_SIGS.md, DISENO.md, referencias/*.png
  scripts/empaquetar.sh
```

La base de PostgreSQL se usa con el rol `sigs_app` (NOSUPERUSER, CREATEDB). El superusuario solo existe dentro del contenedor `db`. Los tests corren con `docker compose run --rm backend pytest`.

## 2. Modelo de datos (tablas iguales al diagrama, `db_table` explícito)

Campos del diagrama más estos extras técnicos:

- `usuario`: modelo de usuario propio (`AbstractBaseUser`, `USERNAME_FIELD = "email"`, el email se guarda en minúsculas). Extras: `password`, `last_login`, `intentos_fallidos`, `bloqueado_en`, `creado_en`. `is_active` es una propiedad que devuelve `activo`. CheckConstraint: `espacio_id` es nulo si y solo si el rol es `superadministrador`. No se usa `PermissionsMixin` ni el admin de Django.
- `poliza`: se crea una por siniestro (la relación 1:N lo permite). `inicio_vigencia` y `primer_pago` son fechas que pueden ser nulas.
- `persona`: única por (`tipo_identificador`, `identificador`). Al guardar, el `identificador` se normaliza sin puntos ni espacios y en mayúsculas. Si ya existe, se reutiliza y no se pisa el nombre.
- `bien`: `identificador_norm` es único y se normaliza en mayúsculas, sin espacios, guiones ni puntos (`AB-123 CD` → `AB123CD`). Se reutiliza si ya existe.
- `siniestro`: `fecha_hecho` es DateTime y no puede ser nula. `fecha_denuncia` es Date y puede ser nula. `numero_expediente` es único (si no viene, se genera `EXP-AAAA-NNNN`). Extras: `motivo_anulacion`, `creado_en`, `actualizado_en`. Estados: `borrador`, `en_analisis`, `cerrado`, `archivado`, `anulado`.
- `participacion`: única por (siniestro, persona, rol). Una persona puede tener varios roles en el mismo caso, por ejemplo "asegurado y conductor".
- `bien_afectado`: único por (siniestro, bien).
- Índices en `participacion(persona_id)`, `participacion(siniestro_id)`, `bien_afectado(bien_id)`, `bien_afectado(siniestro_id)` y `siniestro(estado, confirmado_en)`.
- `documento`: extras `nombre_original`, `tipo_contenido`, `subido_por`. `estado` vale `recibido` al subir. El archivo va a `DOCUMENTOS_DIR/<siniestro_id>/<uuid>` y nunca tiene URL pública.
- `nota`: fecha, hora y autor.
- `tarea` con estados `pendiente`, `en_curso` y `hecha`, y la tabla extra `tarea_cambio` (tarea, estado_anterior, estado_nuevo, usuario, fecha).
- `cierre`: FK no única al siniestro (varios registros por siniestro). El vigente es el último por `creado_en` e `id`. `resultado_reclamo` ∈ `aprobado`, `rechazado`, `desistido`, `otra_finalizacion`. `valoracion` tiene un CheckConstraint de 1 a 10. `justificacion` es `CharField(500)` con un CheckConstraint de longitud mayor a 0. Extra `motivo_cambio`. `save()` sobre una fila existente y `delete()` lanzan error.
- `conjunto_reglas`: `version` única. `topes` = `{"grupos": {"Cobertura": 30, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10}, "total": 100, "prioridad": {"media": 25, "alta": 50}}`. Un solo `activo = true` (UniqueConstraint condicional). Extras: `creado_en`, `creado_por`, `basado_en`. Una vez creado solo puede cambiar `activo`.
- `regla`: única por (conjunto, codigo). No se edita.
- `evaluacion`: `prioridad` ∈ `baja`, `media`, `alta`. `creada_en` con default `timezone.now`, para que el seed pueda fijar la fecha. Extra `motivo` ∈ `confirmacion`, `recalculo`, `antecedente_confirmado`, `escenario`. Nunca se actualiza.
- `senal`: extras `texto_explicacion` y `dato` (JSON con el valor del caso y el umbral). Nunca se actualiza.
- `auditoria`: extras `espacio_id` (del usuario o del siniestro, para filtrar) y `detalle` (JSON). `fecha` la asigna el servidor (`auto_now_add`). El modelo bloquea `save()` sobre una fila existente, `delete()` y `QuerySet.update()` y `QuerySet.delete()` (manager propio).
- **Triggers en la base (migración RunSQL):** una función `sigs_bloquear_modificacion()` que hace `RAISE EXCEPTION` en BEFORE UPDATE OR DELETE FOR EACH ROW sobre `auditoria`, `cierre`, `evaluacion` y `senal`. Además, `REVOKE UPDATE, DELETE ON auditoria FROM PUBLIC`. Un test hace `UPDATE auditoria ...` y `DELETE FROM auditoria ...` con SQL directo (dentro de `transaction.atomic()`) y espera un error.
- Una migración de datos crea `RS-1.0` (vigente desde el 01/10/2026, activo) con las 8 reglas y estos `parametros`:
  - R01 `{"niveles": [{"max_dias": 30, "puntos": 25}, {"max_dias": 60, "puntos": 12}]}`, grupo Cobertura, puntos_max 25
  - R02 `{"min_dias": 0, "max_dias": 15, "puntos": 20}`, Cobertura, 20
  - R03 `{"ventana_meses": 12, "niveles": [{"min_antecedentes": 2, "puntos": 20}, {"min_antecedentes": 1, "puntos": 8}]}`, Persona, 20
  - R04 `{"max_dias": 90, "puntos": 15}`, Persona, 15
  - R05 `{"ventana_meses": 24, "puntos": 15}`, Persona, 15
  - R06 `{"ventana_meses": 24, "puntos": 25}`, Bien, 25
  - R07 `{"puntos": 30}`, Antecedente, 30
  - R08 `{"plazo_dias": 3, "puntos": 10}`, Denuncia, 10
  - Nombres: Cobertura reciente, Pago reciente, Persona recurrente, Siniestros cercanos, Rol cruzado, Bien repetido, Vínculo con irregularidad confirmada, Denuncia tardía.

## 3. Motor RS-1.0 (`nucleo/motor.py`, funciones puras)

- `construir_entradas(siniestro) -> dict` lee la base. `evaluar(entradas, conjunto_dict) -> dict` es pura y determinista y **no lee la base ni la hora**. `guardar_evaluacion(siniestro, motivo, conjunto=None) -> Evaluacion` usa el conjunto activo por defecto y crea la evaluación y sus señales.
- `entradas`:
  ```json
  {"siniestro": {"id": 1, "numero_expediente": "EXP-2026-0147", "fecha_hecho": "2026-08-12",
                 "fecha_denuncia": "2026-08-14", "inicio_vigencia": "2026-07-20", "primer_pago": "2026-08-04"},
   "personas": [{"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado", "conductor"]}],
   "bienes": [{"tipo": "vehiculo", "identificador_norm": "AB123CD"}],
   "antecedentes": [{"id": 9, "numero_expediente": "S-2025-0381", "fecha_hecho": "2025-07-10", "estado": "cerrado",
                     "irregularidad": false, "resultado_reclamo": "aprobado",
                     "personas": [{"tipo_identificador": "DNI", "identificador": "...", "roles": ["testigo"]}],
                     "bienes": ["AB123CD"]}]}
  ```
  `antecedentes` incluye solo los antecedentes válidos que comparten al menos una persona o un bien, y en cada uno solo las personas y los bienes compartidos. `H` = fecha local (America/Argentina/Buenos_Aires) de `fecha_hecho`. Se ordena por id para que sea determinista.
- **Antecedente válido:** otro siniestro, de cualquier espacio, con `confirmado_en` no nulo y `estado` ∈ `en_analisis`, `cerrado` o `archivado`. Los anulados y los borradores nunca cuentan.
- **Ventanas:** "en los N meses anteriores a H" quiere decir `H - N meses (relativedelta) <= H_ant < H` (estrictamente antes de H). R04 usa `0 < d(H_ant, H) <= 90`. R07 no tiene límite de tiempo.
- **Reglas:**
  - R01: si no hay inicio_vigencia, no es evaluable. `d = d(inicio_vigencia, H)`. El primer nivel con `d <= max_dias` da sus puntos (≤ 30 → 25, 31 a 60 → 12).
  - R02: si no hay primer_pago, no es evaluable. Se activa si `0 <= d(primer_pago, H) <= 15`. Un pago posterior al hecho no la activa (supuesto 1).
  - R03: cantidad de antecedentes distintos que comparten una persona del caso, **con cualquier rol** (supuesto 2), dentro de 12 meses. Con 2 o más → 20, con 1 → 8.
  - R04: algún antecedente con persona compartida y `0 < d <= 90` → 15.
  - R05: alguna persona compartida cuyo conjunto de roles en el antecedente tiene un rol que no tiene en el caso, dentro de 24 meses → 15.
  - R06: algún bien compartido (por identificador_norm) dentro de 24 meses → 25.
  - R07: algún antecedente con persona o bien compartido, con estado `cerrado` o `archivado` y cuyo **cierre vigente** tiene `irregularidad = true` → 30. Se incluye `archivado` porque un archivado ya pasó por el cierre y sigue contando como antecedente (HU-14). Un rechazo o un desistimiento sin irregularidad no la activan.
  - R08: si no hay fecha_denuncia, no es evaluable. Se activa si `d(H, fecha_denuncia) > 3` → 10.
- Cada regla devuelve `{codigo, nombre, grupo, estado: activada|no_activada|no_evaluable, puntos, antecedentes: [{id, numero_expediente, fecha_hecho, vinculo}], texto, dato}`. Cada regla se activa una sola vez, con el nivel más alto, y lista **todos** los antecedentes que la cumplen.
- Topes: se suma por grupo y se corta en el tope del grupo. Después se suman los grupos y se corta en `total` (100). Prioridad: `>= alta` → alta, `>= media` → media y si no, baja. El resultado incluye `grupos: {nombre: {bruto, tope, puntos}}`, `puntaje` y `prioridad`.
- Textos (desde la misma señal, en el lenguaje del perito):
  - R01: "El hecho ocurrió 23 días después del inicio de vigencia. Umbral 30 días." En el nivel de 12: "El hecho ocurrió 40 días después del inicio de vigencia. Umbral 60 días."
  - R02: "El primer pago se registró 8 días antes del hecho. Umbral 15 días."
  - R03: "P-17 no tiene otros siniestros válidos en los últimos 12 meses." / "P-17 figura en 2 siniestros válidos de los últimos 12 meses: S-…, S-…."
  - R04: "P-17 tiene el siniestro S-… de hace 45 días. Umbral 90 días."
  - R05: "P-17 figura como testigo en S-… de hace 10 meses. En este caso es asegurado."
  - R06: "El vehículo AB123CD figura en el antecedente S-2025-0381 de hace 13 meses."
  - R07: "AB123CD figura en el antecedente S-… cerrado con irregularidad confirmada."
  - R08: "La denuncia se hizo 2 días después del hecho. Plazo 3 días."
  - No evaluable: "No se pudo evaluar: falta la fecha de inicio de vigencia." (o "del primer pago", "de denuncia").
  - Los meses se cuentan con `relativedelta(H, H_ant)` en meses. Si dan 0, se usan días.
- **Recálculo:** se crea una evaluación nueva al confirmar (motivo `confirmacion`), al pulsar Recalcular (`recalculo`) y al confirmarse otro siniestro que comparte una persona o un bien con un caso `en_analisis`. En ese caso se recalcula cada uno de esos casos con motivo `antecedente_confirmado`, también entre espacios.
- **Versiones (HU-12):** `POST /api/reglas/versiones` (solo superadministrador) con `{"version": "RS-1.1", "vigente_desde": "AAAA-MM-DD", "reglas": {"R01": {"parametros": {...}, "puntos_max": 25}}, "topes": {...}}`. Copia la versión vigente, aplica los cambios, la marca activa y desactiva la anterior. La anterior queda sin edición y las evaluaciones viejas conservan su `conjunto_id`. Con la misma versión, `evaluar(evaluacion.entradas, conjunto)` reproduce exactamente las señales y el puntaje guardados.

## 4. Permisos y auditoría

- Autenticación con `SessionAuthentication` y CSRF obligatorio. La subclase `SesionAutenticacion` rechaza sesiones de usuarios con `activo = false` o con `bloqueado_en` no nulo.
- **Acceso a expedientes:**
  - Solo el rol `perito` accede a los expedientes, y solo a los de su espacio (`siniestro.espacio_id == usuario.espacio_id`).
  - Si el expediente es de otro espacio o no existe, se responde **404**.
  - Leer los datos, el análisis, las coincidencias y el resumen está permitido para cualquier perito del espacio (supuesto 4). El panel muestra solo los propios.
  - El **contenido privado** (documentos, notas, tareas) y todas las **escrituras** (editar, confirmar, recalcular, cierre, archivar, anular, subir y crear) son solo del perito responsable (`siniestro.perito_id == usuario.id`). A otro perito del mismo espacio se le responde **403**.
  - El administrador y el superadministrador no leen expedientes (403).
- **Todo rechazo se audita:** el `EXCEPTION_HANDLER` de DRF (`nucleo.permisos.manejar_excepcion`) registra con `resultado = rechazado` toda respuesta 401, 403, 404 y 405. También lo hace el `handler404` de Django para rutas inexistentes bajo `/api/` (respuesta JSON) y la vista de CSRF fallido. Las excepciones propias (`Rechazo`) traen `accion`, `objeto` y `siniestro_origen`; las genéricas usan `accion = "<METODO> <ruta>"`. No usar `ATOMIC_REQUESTS`, porque haría rollback de la fila de auditoría.
- Acciones permitidas que se auditan: ingreso, ingreso fallido (rechazado), bloqueo de cuenta, restablecimiento, primer ingreso, salida, ver expediente, ver coincidencias, ver resumen (con `siniestro_origen`), descargar documento, crear y modificar siniestro, confirmar, recalcular, cierre, cambio de valoración, archivar, anular, nota, tarea, cambio de estado de tarea, documento subido, cambio de contacto en el perfil, alta, baja, bloqueo y reenvío de enlace de usuarios, creación de espacio y publicación de una versión de reglas.
- **No existe un buscador de personas.** `GET /api/personas`, `GET /api/personas/<algo>` y cualquier variante responden 403 "La búsqueda de personas solo se hace desde un expediente confirmado." y se auditan como rechazadas (A5).
- `/api/auditoria/<id>`: GET devuelve el registro (administrador de su espacio). PUT, PATCH y DELETE responden 403 "Los registros de auditoría no se pueden modificar ni borrar." y se auditan (A7).

## 5. Contrato de la API (todo bajo `/api`, JSON, fechas ISO)

Usuario serializado: `{"id", "nombre", "email", "rol", "espacio": {"id", "nombre"} | null, "activo", "contacto_email", "contacto_visible"}`.

### Autenticación y perfil
| Método y ruta | Quién | Cuerpo y respuesta |
|---|---|---|
| GET `/health` | público | `{"estado": "ok"}` |
| GET `/auth/sesion` | público | `{"autenticado": bool, "usuario": Usuario \| null}`. Siempre entrega la cookie `csrftoken` (`ensure_csrf_cookie`). Nunca responde 401. |
| POST `/auth/ingresar` | público | `{email, password}` → 200 `{"usuario": Usuario}`. El error es siempre 400 `{"detalle": "El correo o la contraseña no son correctos."}`, sea el correo inexistente, la contraseña incorrecta, la cuenta bloqueada o la baja. Al 5.º fallo seguido se bloquea, se manda el correo de aviso con el enlace de restablecimiento y se audita `bloqueo_cuenta`. Un ingreso correcto pone en cero los intentos. |
| POST `/auth/salir` | autenticado | 204 |
| POST `/auth/restablecer` | público | `{email}` → 200 siempre `{"detalle": "Si el correo está registrado, te enviamos un enlace para restablecer la contraseña."}` |
| GET `/auth/enlace?uid=&token=` | público | `{"valido": bool, "email": str \| null}` |
| POST `/auth/definir-contrasena` | público | `{uid, token, password}` → 200 `{"detalle": "Contraseña actualizada. Ya podés ingresar."}`. Valida la política (400 `{"password": [...]}`). El enlace vencido o usado da 400 `{"detalle": "El enlace no es válido o venció."}`. Desbloquea la cuenta y pone en cero los intentos. Sirve para el primer ingreso y para el restablecimiento. Usa `default_token_generator` (un solo uso, porque el hash depende de la contraseña, y vence a los 3600 s). |
| GET/PATCH `/perfil` | autenticado | `{contacto_email, contacto_visible}` → Usuario. Se audita `perfil_contacto`. |

Enlaces de los correos: `APP_URL/primer-ingreso?uid=…&token=…` y `APP_URL/restablecer?uid=…&token=…`.

### Expedientes (perito)
| Método y ruta | Notas |
|---|---|
| GET `/siniestros` | Panel HU-16: solo los propios (`perito_id = usuario`). Orden: prioridad de la última evaluación (alta > media > baja > sin evaluar), después `fecha_hecho` descendente. Cada ítem: `{id, numero_expediente, tipo, fecha_hecho, estado, bien_principal, prioridad, puntaje, tareas_pendientes}`. También devuelve `resumen: {en_analisis, prioridad_alta, tareas_vencen_semana, cerrados_mes}`. Respuesta `{"resultados": [...], "resumen": {...}}`. |
| POST `/siniestros` | `{numero_expediente?, poliza: {numero, compania, cobertura, inicio_vigencia, primer_pago}, tipo, fecha_hecho, fecha_denuncia, lugar, relato, personas: [{tipo_identificador, identificador, nombre, roles: [..]}], bienes: [{tipo, identificador, descripcion, detalle_dano, atributos}], confirmar?: bool}`. Sin `fecha_hecho` → 400 `{"fecha_hecho": ["La fecha del hecho es obligatoria."]}`. Queda en `borrador`. Con `confirmar: true` se confirma enseguida (con las mismas validaciones que `/confirmar`). → 201 Siniestro. |
| GET `/siniestros/<id>` | Siniestro: `{id, numero_expediente, tipo, fecha_hecho, fecha_denuncia, lugar, relato, estado, confirmado_en, motivo_anulacion, espacio: {id, nombre}, perito: {id, nombre}, es_responsable: bool, poliza: {...} \| null, personas: [{id, tipo_identificador, identificador, nombre, roles}], bienes: [{id, tipo, identificador_norm, descripcion, atributos, detalle_dano}], cierre_vigente: Cierre \| null}`. El relato y el daño se ven solo dentro del propio espacio. |
| PATCH `/siniestros/<id>` | Mismo cuerpo que POST, solo en `borrador`. Reemplaza las personas y los bienes. |
| POST `/siniestros/<id>/confirmar` | Requiere borrador, póliza, fecha del hecho y al menos una persona o un bien. Si falta algo → 400 `{"detalle": "Para confirmar hacen falta la póliza, la fecha del hecho y al menos una persona o un bien."}`. Pasa a `en_analisis`, guarda `confirmado_en`, evalúa y recalcula los casos vinculados. → Siniestro. |
| GET `/siniestros/<id>/evaluacion` | Última evaluación: `{id, version, creada_en, motivo, puntaje, prioridad, grupos, senales: [{codigo, nombre, grupo, estado, puntos, puntos_max, texto, dato, antecedentes}], entradas}`. Un siniestro no confirmado → 403 "Solo un siniestro confirmado se analiza." Si no hay evaluación → 404. |
| GET `/siniestros/<id>/evaluaciones` | Historial `[{id, version, creada_en, motivo, puntaje, prioridad}]`. |
| POST `/siniestros/<id>/recalcular` | Responsable y confirmado → nueva evaluación. |
| GET `/siniestros/<id>/coincidencias?pagina=1` | Solo confirmado (en_analisis, cerrado o archivado); si no → 403 (A1). `{"resultados": [{antecedente_id, numero_expediente, tipo, fecha_hecho, estado, resultado_reclamo \| null, vinculos: [{tipo: "persona"\|"bien", etiqueta, rol_en_antecedente, rol_en_caso}], descripcion_vinculo}], "total", "pagina", "paginas", "promedio_valoracion": {"promedio": 7.0 \| null, "cantidad": 1}, "mensaje_vacio": "No hay antecedentes accesibles en la red" \| null}`. Páginas de 20. El promedio se calcula sobre todos los vinculados que tienen valoración y no se guarda. |
| GET `/siniestros/<id>/antecedentes/<ant_id>/resumen` | Ver la sección 6. |
| GET/POST `/siniestros/<id>/documentos` | POST multipart `archivo`, `tipo`. GET `[{id, tipo, nombre_original, estado, recibido_en, tamanio}]`. Solo el responsable. |
| GET `/documentos/<id>/descargar` | Solo el responsable del siniestro. `FileResponse` con `Content-Disposition: attachment`. Los demás → 404 y se audita (A3). |
| GET/POST `/siniestros/<id>/notas` | `{texto}` → `{id, texto, creada_en, autor: {id, nombre}}`. Solo el responsable. |
| GET/POST `/siniestros/<id>/tareas` | `{titulo, vence_en?}` → `{id, titulo, estado, vence_en, creada_en, cambios: [{estado_anterior, estado_nuevo, fecha, usuario}]}`. Empieza en `pendiente`. |
| PATCH `/tareas/<id>` | `{estado}`. Registra un `tarea_cambio` y lo audita. Solo el responsable. |
| GET `/tareas` | Tareas no hechas de los expedientes propios: `[{..., siniestro: {id, numero_expediente, tipo}}]`. |
| GET `/siniestros/<id>/cierre` | `{"vigente": Cierre \| null, "historial": [Cierre...]}`. Cierre: `{id, resultado_reclamo, irregularidad, conclusion, valoracion, valoracion_texto, justificacion, motivo_cambio, creado_en, perito: {id, nombre}}`. |
| POST `/siniestros/<id>/cierre` | Primer cierre: estado `en_analisis` → `cerrado`. Cambio: estado `cerrado` o `archivado` y `motivo_cambio` obligatorio (400 si falta). `valoracion` fuera de 1 a 10 → 400 `{"valoracion": ["La valoración tiene que estar entre 1 y 10."]}`. Sin justificación → 400 `{"justificacion": ["La justificación es obligatoria."]}`. Máximo 500 caracteres. |
| POST `/siniestros/<id>/archivar` | `cerrado` → `archivado`. |
| POST `/siniestros/<id>/anular` | `{motivo}` obligatorio, desde cualquier estado menos `anulado`. No borra nada. |

Escala de valoración (tabla 2 del TFG, `valoracion_texto`): 1–2 "No verificado, con elementos que lo contradicen", 3–4 "Inconsistencias relevantes", 5–6 "Dudas concretas", 7–8 "Verificado con observaciones menores", 9–10 "Verificado sin observaciones".

### Reglas
| GET `/reglas` | autenticado | `{"vigente": Conjunto, "versiones": [{id, version, vigente_desde, activo, creado_en}]}`. Conjunto: `{id, version, vigente_desde, activo, topes, reglas: [{codigo, nombre, grupo, parametros, puntos_max, umbral_texto}]}`. `umbral_texto` es como en la maqueta: "≤ 30 días: 25 · 31 a 60: 12". |
| GET `/reglas/versiones/<id>` | autenticado | Conjunto |
| POST `/reglas/versiones` | superadministrador | Ver la sección 3. Perito o administrador → 403 "Solo el superadministrador publica versiones de reglas." (A8). Si la versión está repetida → 400. |

### Administración
| GET/POST `/admin/usuarios` | administrador (su espacio) | POST `{nombre, email, rol: perito\|administrador}`. Con correo repetido → 400 `{"email": ["Ya existe un usuario con ese correo."]}`. Crea al usuario sin contraseña usable y le manda el correo de primer ingreso. GET lista los usuarios del espacio con `bloqueado_en` e `intentos_fallidos`. |
| POST `/admin/usuarios/<id>/baja` | administrador | `activo = false` y cierra sus sesiones. |
| POST `/admin/usuarios/<id>/bloquear` | administrador del espacio o superadministrador | "Bloquear y cerrar sesiones": `bloqueado_en = now` y se borran todas sus sesiones. Se audita. |
| POST `/admin/usuarios/<id>/reenviar-enlace` | administrador | Manda un enlace nuevo de primer ingreso o de restablecimiento. |
| GET/POST `/admin/espacios` | superadministrador | POST `{nombre, admin_nombre, admin_email}` crea el espacio y su administrador, y le manda el enlace de primer ingreso. GET lista los espacios con la cantidad de usuarios. |
| GET `/auditoria?usuario=&accion=&resultado=&pagina=` | administrador | Solo su espacio (`auditoria.espacio_id`). Páginas de 50, ordenadas por fecha descendente. `{"resultados": [{id, fecha, usuario: {id, nombre, email} \| null, accion, objeto, resultado, siniestro_origen: {id, numero_expediente} \| null}], "total", "pagina", "paginas", "acciones": [lista de acciones distintas]}`. |
| GET/PUT/PATCH/DELETE `/auditoria/<id>` | | Ver la sección 4. |

## 6. Resumen del antecedente (HU-11)

`GET /siniestros/<origen>/antecedentes/<ant>/resumen`:
- El origen tiene que ser del espacio del perito y estar confirmado (si no, 403). El antecedente tiene que estar entre las coincidencias válidas del origen (si no, **404** "El antecedente no coincide con el siniestro de origen.", y se audita con `siniestro_origen`) (A6).
- Respuesta, armada en el momento y **sin guardarse**: `{numero_expediente, tipo, fecha_hecho, estado, vinculos: [{tipo, etiqueta, rol_en_antecedente}], cerrado: bool, resultado_reclamo, irregularidad, valoracion, valoracion_texto, justificacion, perito_responsable: {nombre}, contacto_perito: {email} | null, origen: {id, numero_expediente}, no_se_muestra: "Fotografías, documentos, notas privadas, DNI, teléfono, relato, detalle del daño y datos de contacto del asegurado y de los terceros quedan en el expediente de origen."}`.
- Si el caso no está cerrado ni archivado: `estado_texto = "En análisis"` y todos los datos de cierre en null.
- Para un bien, `rol_en_antecedente` = "Bien afectado". Para una persona, la etiqueta es el **nombre de la persona del caso de origen** (el perito ya la conoce) y nunca su identificador.
- `contacto_perito` va solo si `contacto_visible` es verdadero y `contacto_email` no está vacío.
- Cada lectura se audita con `accion = "ver_resumen_antecedente"`, el usuario, `siniestro_origen`, `objeto = "siniestro:<ant_id>"` y `resultado`.

## 7. Escenarios (TT-02, `nucleo/escenarios.py`)

Hay un espacio propio "Escenarios de prueba (TT-02)" con el perito `perito.escenarios@sigs.test`. Cada escenario usa personas y bienes únicos (prefijo `ESC-<id>`) para no cruzarse con otros. `H = 2026-06-15 12:00`. Valores por defecto: vigencia H-400, primer pago H-400, denuncia H+1, una persona asegurada y un vehículo. Los antecedentes están confirmados, `en_analisis` o `cerrado` (aprobado, sin irregularidad), salvo que se indique otra cosa.

Por decisión del usuario (S12 del documento de tareas), R03 se cuenta como **esperada** donde la definición la activa siempre.

| Id | Caso | Esperado |
|---|---|---|
| R01-A | vigencia y pago H-20 | R01 25 → 25 media |
| R01-B | vigencia y pago H-75 | — → 0 baja |
| R01-C | vigencia y pago H-30 | R01 25 → 25 media |
| R02-A | pago H-10 | R02 20 → 20 baja |
| R02-B | pago H-40 | — → 0 baja |
| R02-C | sin primer pago | — (R02 no evaluable) → 0 baja |
| R03-A | 2 previos de la persona (H-120 d, H-200 d), mismo rol | R03 20 → 20 baja |
| R03-B | sin previos | — → 0 baja |
| R03-C | 1 previo (H-150 d) | R03 8 → 8 baja |
| R04-A | previo H-45 d | R03 8, R04 15 → 23 baja |
| R04-B | previo H-150 d | R03 8 → 8 baja |
| R04-C | previo H-90 d | R03 8, R04 15 → 23 baja |
| R05-A | testigo en un previo de H-10 meses | R03 8, R05 15 → 23 baja |
| R05-B | mismo rol en un previo de H-18 meses | — → 0 baja |
| R05-C | rol cruzado en un previo de H-25 meses | — → 0 baja |
| R06-A | mismo dominio H-8 meses, otra persona | R06 25 → 25 media |
| R06-B | antecedente con otro dominio y otra persona | — → 0 baja |
| R06-C | caso con `AB-123-CD` (con su prefijo único) y antecedente sin guiones, H-8 meses | R06 25 → 25 media |
| R07-A | antecedente de H-30 meses, misma persona, cerrado con irregularidad | R07 30 → 30 media |
| R07-B | ídem, cerrado rechazado sin irregularidad | — → 0 baja |
| R07-C | ídem, con irregularidad pero anulado | — → 0 baja |
| R08-A | denuncia H+5 | R08 10 → 10 baja |
| R08-B | denuncia H+1 | — → 0 baja |
| R08-C | denuncia H+3 | — → 0 baja |
| C1 | vigencia H-20, pago H-10, previo de la persona H-60 d, denuncia H+1 | R01 25, R02 20, R03 8, R04 15 → 53 alta |
| C2 | vigencia H-40, pago H-35, 2 robos previos de la misma persona y el mismo dominio (H-60 d y H-8 meses), siempre asegurado | R01 12, R03 20, R04 15, R06 25 → 72 alta |
| C3 | antecedente H-10 meses que comparte solo el bien, cerrado con irregularidad | R06 25, R07 30 → 55 alta |
| C4 | 3 previos de la persona (H-100 d, H-200 d, H-300 d como tercero) | R03 20, R05 15 → 35 media |
| C5 | vigencia H-10, pago H-5, denuncia H+10. A1 H-30 d misma persona. A2 H-200 d persona como testigo y mismo dominio. A3 H-400 d mismo dominio, cerrado con irregularidad | las 8 → 160 en bruto, 130 con los topes por grupo, total 100 alta |
| C6 | vigencia H-200, sin primer pago, denuncia H+1, sin coincidencias | — (R02 no evaluable) → 0 baja |

Esperado: 16 activaciones por regla + 20 combinadas = **36**, con 0 falsos positivos y 0 falsos negativos. La unidad de evaluación es cada combinación (escenario, regla): un verdadero positivo es una regla esperada que se activa, un falso positivo es una activación no prevista y un falso negativo es una regla esperada que no se activa. Además se compara el puntaje de cada regla, el total y la prioridad.

`seed_escenarios [--si-vacia]` crea los datos y una evaluación por caso (motivo `escenario`). `evaluar_escenarios` recorre los casos desde la base con el pipeline real (`construir_entradas` + `evaluar` con RS-1.0, sin guardar nada), imprime una tabla por escenario, una tabla por regla (esperadas y obtenidas) y las métricas (VP, FP, FN, precisión y sensibilidad), y sale con código 1 si algo no coincide. Los tests usan los mismos datos.

## 8. Datos de demo (`seed_demo [--si-vacia]`)

Todos los usuarios tienen la contraseña `Demo.Sigs#2026` (cumple la política y se valida en el seed).

| Usuario | Rol | Espacio | Contacto |
|---|---|---|---|
| superadmin@sigs.test (Superadministrador) | superadministrador | — | |
| admin.norte@sigs.test (Admin Norte) | administrador | Estudio Pericial Norte | |
| admin.sur@sigs.test (Admin Sur) | administrador | Perito Independiente Sur | |
| perito08@sigs.test (PE-08) | perito | Norte | visible, pe08@correo.test |
| perito11@sigs.test (PE-11) | perito | Norte | no visible |
| perito15@sigs.test (PE-15) | perito | Sur | visible, pe15@correo.test |

Casos (nombres de personas ficticios tipo "P-17" con DNI ficticio):
- **EXP-2026-0147**, Incendio total (Norte, PE-08). Hecho el 12/08/2026 a las 23:40, denuncia el 14/08/2026, lugar "Vía pública, Neuquén", póliza AUT-000123 de "Aseguradora Ejemplo S. A." con vigencia desde el 20/07/2026 y primer pago el 04/08/2026. P-17 es asegurado y conductor. Vehículo AB123CD con atributos de motor y chasis. Confirmado el 18/08/2026 a las 10:42. **Tiene que dar R01 25, R02 20, R06 25 → 55, alta.** Tiene las tareas y las notas de la maqueta 06 y un documento de texto ficticio.
- **S-2025-0381**, Robo parcial de vehículo (Sur, PE-15). Hecho el 10/07/2025, vehículo AB123CD, persona P-52 asegurada (distinta de P-17). Cerrado como aprobado, sin irregularidad, valoración 7 y justificación "Faltó la denuncia policial original. El resto de la documentación coincide."
- **Robo de rueda de auxilio**, EXP-2026-0160 (Norte, PE-08, confirmado). Dominio AD555RR, repetido en S-2025-0410 (Sur), S-2026-0030 (Sur) y EXP-2026-0098 (Norte, PE-11), todos robos de rueda, algunos cerrados con valoración.
- **R07**, EXP-2026-0139 Choque en calle (Norte, PE-08). La persona P-31 figura en S-2024-0207 (Sur), cerrado como rechazado con irregularidad confirmada.
- **Anulado**, EXP-2026-0120 (Norte, PE-11), anulado por carga errónea con motivo. Comparte el vehículo AC904KL con EXP-2026-0139 y **no tiene que aparecer** como antecedente.
- **Sin coincidencias**: EXP-2026-0151 Robo de celular (confirmado) y EXP-2026-0122 Daño por granizo (cerrado). Hay además un borrador, EXP-2026-0158 Robo en comercio.
- Cada caso confirmado se evalúa con `guardar_evaluacion` después de cargar todos los datos, para que las evaluaciones vean la red completa.

## 9. Frontend

- Next.js 15 (App Router, TypeScript, `output: "standalone"`), todo en componentes de cliente que llaman a `/api` con `credentials: "same-origin"` y el header `X-CSRFToken` leído de la cookie `csrftoken` en los métodos que no son GET. Antes del primer POST se llama a `GET /api/auth/sesion` para obtener la cookie. Sin librerías de UI: CSS propio (globals.css o CSS modules) que replica las maquetas de `docs/referencias/pantallas-*.png`.
- Estilo: barra lateral verde oscuro (`#1f3a35`) con "SIGS" y "Gestión de siniestros", ítem activo resaltado, fondo de contenido `#f3f2ee`, tarjetas blancas con borde `#dcdcd6`, botón principal `#2f6f62`, etiquetas de estado (En análisis verde claro, Borrador o Cerrado gris), prioridad (Alta rojo `#f6dede`/`#9b2226`, Media ámbar, Baja gris), aviso ámbar claro para "La prioridad ordena qué revisar primero. No indica que haya fraude.", e identificadores en monoespaciada. Responsive: en el teléfono la barra lateral pasa a menú superior y las grillas a una columna.
- La barra lateral muestra al pie el usuario y el espacio, y "Salir".
  - Perito: Expedientes, Nuevo siniestro, Tareas, Reglas del indicador y Perfil.
  - Administrador: Usuarios, Auditoría, Reglas del indicador y Perfil.
  - Superadministrador: Espacios, Reglas del indicador (con "Nueva versión") y Perfil.
- Rutas: `/ingresar`, `/primer-ingreso`, `/restablecer` (pedir el enlace y definir la contraseña con uid y token), `/expedientes`, `/expedientes/nuevo`, `/expedientes/[id]` con las pestañas Datos, Análisis, Seguimiento, Documentos y Cierre (`?tab=`), `/expedientes/[id]/antecedentes/[antId]`, `/tareas`, `/reglas`, `/perfil`, `/admin/usuarios`, `/admin/auditoria` y `/admin/espacios`. `/` redirige según la sesión y el rol.
- Textos clave: "Usá el correo con el que te dieron de alta.", "Si olvidaste la contraseña pedí el blanqueo al administrador del espacio." (además de un enlace "Restablecer contraseña"), "Los datos quedan en borrador hasta que confirmes. Solo un siniestro confirmado se analiza.", "Antes de confirmar", "Al confirmar, el sistema busca coincidencias y calcula el indicador con las reglas vigentes.", "Consulta hecha desde EXP-…. Queda registrada en la auditoría.", "Qué no se muestra", "Un valor bajo no equivale a fraude confirmado.", "El indicador ordena qué revisar primero. No es una probabilidad de fraude.", "Prototipo académico. Datos ficticios."
