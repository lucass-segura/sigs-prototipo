# SIGS · Sistema Integral de Gestión de Siniestros y Prevención de Fraude

Especificación funcional del prototipo, tomada del TFG.

- **Autor del proyecto:** Lucas Agustín Segura (TFG, Licenciatura en Informática, UES 21).
- **Fuente:** el Trabajo Final de Graduación (Entregable 4). Este documento resume lo que el TFG afirma del prototipo, y el código tiene que cumplirlo.
- **Referencias visuales:** `referencias/` (pantallas, diagramas de entidad relación y arquitectura).
- **Idioma:** la interfaz, los mensajes y los nombres del dominio (modelos, campos y endpoints) van en español, como en el diagrama de entidad relación. El código auxiliar puede ir en inglés.

---

## 1. Objetivo

Construir el núcleo funcional de una plataforma web para peritos de seguros con estas funciones:

1. Gestionar expedientes de siniestros privados por espacio de trabajo: datos, documentos, notas, tareas y cierre.
2. Relacionar cada siniestro confirmado con sus antecedentes en la red mediante un grafo de personas, bienes y siniestros, a dos saltos.
3. Calcular un **indicador de prioridad de 0 a 100** con un conjunto **versionado de 8 reglas** (RS-1.0), explicable y reproducible.
4. Permitir consultar **resúmenes minimizados** de antecedentes, solo desde un siniestro confirmado, y registrar cada consulta en una **auditoría que nadie puede editar ni borrar**.

El entregable para la facultad es el **código fuente con un instructivo de puesta en marcha** (README), que se sube a la nube. No hay video ni despliegue online.

## 2. Alcance

### Dentro del alcance (HU-01 a HU-17, TT-01 a TT-03)

| Id | Historia o tarea | Prioridad |
|---|---|---|
| TT-01 | Entorno Docker, base de datos y repositorio | Alta |
| HU-01 | Inicio de sesión y roles | Alta |
| HU-02 | Administración de usuarios y espacios de trabajo | Alta |
| HU-03 | Registro de siniestro | Alta |
| HU-04 | Confirmación del siniestro | Alta |
| HU-05 | Documentos del perito | Media |
| HU-06 | Notas privadas del expediente | Media |
| HU-07 | Tablero de tareas del expediente | Media |
| HU-08 | Búsqueda de coincidencias | Alta |
| HU-09 | Cálculo del indicador de prioridad | Alta |
| HU-10 | Explicación de las reglas | Alta |
| HU-11 | Consulta del resumen de un antecedente | Alta |
| HU-12 | Administración de versiones de reglas | Media |
| HU-13 | Cierre del expediente con valoración | Alta |
| HU-14 | Archivo y anulación por carga errónea | Media |
| HU-15 | Registro de auditoría | Alta |
| HU-16 | Panel de expedientes del perito | Media |
| HU-17 | Perfil y correo de contacto | Media |
| TT-02 | Base de datos ficticia con escenarios de prueba | Alta |
| TT-03 | Pruebas de acceso directo a la API | Alta |

Los criterios de aceptación completos de cada historia están en el **Anexo A**.

### Fuera del alcance (no implementar)

- Mensajería interna entre peritos. El contacto se hace solo por el correo que el perito decide mostrar (HU-17).
- Integración con sistemas de compañías aseguradoras.
- Aprendizaje automático y comparación automática de testimonios.
- Datos reales. **Todo es ficticio.**
- Panel de monitoreo del superadministrador, alertas de denegación de servicio, respaldos automáticos a S3, HTTPS y Let's Encrypt. Son de la puesta en marcha, no del prototipo.
- Registro abierto de usuarios.

## 3. Restricciones técnicas

| Capa | Tecnología |
|---|---|
| Frontend | Next.js (App Router) + TypeScript, Node 20, puerto 3000 |
| Backend | Python 3.12, Django 5 + Django REST Framework, Gunicorn, puerto 8000 |
| Base de datos | PostgreSQL 16 (JSONB para `entradas`, `antecedentes`, `parametros`, `topes`, `atributos`) |
| Proxy | Nginx: `/` → frontend, `/api` → backend (mismo origen) |
| Correo | Mailpit en Docker Compose para ver los correos en local (bloqueo de cuenta, restablecimiento, primer ingreso) |
| Orquestación | Docker Compose: `nginx`, `frontend`, `backend`, `db`, `mailpit`, volumen `documentos` y volumen `datos` |

Arquitectura de referencia: `referencias/arquitectura.png`. En local se usa HTTP. Las opciones de cookie segura se activan por variable de entorno (`SECURE_COOKIES=true`) para producción.

**Autenticación:** sesión de Django con cookie `HttpOnly` y CSRF, sin JWT en `localStorage`. El frontend llama a `/api` en el mismo origen a través de Nginx.

## 4. Roles y permisos

| Perfil | Puede | No puede |
|---|---|---|
| Perito | Registrar y confirmar sus siniestros, cargar documentos, notas y tareas, consultar coincidencias y resúmenes desde un siniestro confirmado, cerrar el expediente con su valoración y configurar su correo de contacto. | Ver expedientes de otros espacios, abrir documentos o notas ajenas, buscar personas fuera de un expediente y modificar las reglas. |
| Administrador del espacio | Dar de alta y de baja a los usuarios de su espacio y revisar la auditoría de su espacio. | Modificar las reglas, ver otros espacios y borrar registros de auditoría. |
| Superadministrador | Crear espacios de trabajo y sus administradores, y publicar nuevas versiones del conjunto de reglas. | Leer el contenido de los expedientes (documentos y notas) y editar o borrar registros de auditoría. |

**Regla de oro:** los permisos se verifican **en cada solicitud a la API** (autorización por objeto). Ocultar un botón no alcanza. Cada endpoint compara `usuario.espacio_id` con el `espacio_id` del expediente pedido. Toda solicitud rechazada por permisos también se registra en la auditoría con `resultado = rechazado`.

## 5. Seguridad de acceso (sección Seguridad del TFG)

1. **Sin registro abierto.** El superadministrador crea el espacio y su administrador, y el administrador da de alta a los peritos. El correo es único en todo el sistema.
2. **Contraseña:** mínimo 8 caracteres, con al menos una mayúscula, una minúscula, un número y un carácter especial. Además se aplican `UserAttributeSimilarityValidator` y `CommonPasswordValidator` de Django.
3. **Primer ingreso:** el usuario recibe un enlace por correo y define su propia contraseña. Ni el administrador ni el superadministrador la conocen.
4. **Hash:** el de Django por defecto (PBKDF2 con SHA-256 y sal).
5. **Intentos fallidos:** a los **5 intentos fallidos** la **cuenta queda bloqueada** y solo se habilita cuando el usuario **restablece la contraseña** desde el enlace del correo. Al bloquearse, **el sistema envía un correo de aviso al usuario** (debe verse en Mailpit). El mensaje de error del login **no indica cuál de los dos datos falló**. Cada intento fallido y cada bloqueo quedan en la auditoría.
6. **Recuperación:** enlace de un solo uso que vence en **1 hora** (`PASSWORD_RESET_TIMEOUT = 3600`). Al restablecer se ponen en cero los intentos y se desbloquea la cuenta.
7. **Sesión:** se cierra tras **60 minutos sin actividad** (`SESSION_COOKIE_AGE = 3600` y `SESSION_SAVE_EVERY_REQUEST = True`).
8. **Baja:** el usuario queda `activo = false`, no puede ingresar y se conservan su historial y su auditoría.
9. **Cuenta comprometida:** el superadministrador o el administrador pueden **bloquear una cuenta y cerrar todas sus sesiones** (acción "Bloquear y cerrar sesiones", auditada).

## 6. Modelo de datos

Diagramas en `referencias/der-expediente.png` y `referencias/der-analisis-reglas.png`. Las tablas y los campos tienen que coincidir con esos diagramas. Se pueden agregar campos técnicos, que se listan en la columna Extra.

| Tabla | Campos | Extra necesario |
|---|---|---|
| espacio_trabajo | id, nombre, creado_en | |
| usuario | id, espacio_id (null para superadmin), nombre, email (único), rol (`perito`, `administrador`, `superadministrador`), activo, contacto_email, contacto_visible | intentos_fallidos, bloqueado_en |
| poliza | id, numero, compania, cobertura, inicio_vigencia, primer_pago | |
| persona | id, identificador, tipo_identificador (`DNI`, `CUIT`, `PASAPORTE`), nombre | único (tipo_identificador, identificador) |
| bien | id, tipo (`vehiculo`, `motocicleta`, `telefono`, `computadora`, `otro`), identificador_norm, descripcion, atributos (JSONB) | único (identificador_norm) |
| siniestro | id, espacio_id, perito_id, poliza_id, numero_expediente, tipo, fecha_hecho, fecha_denuncia, lugar, relato, estado, confirmado_en | |
| participacion | id, siniestro_id, persona_id, rol (`asegurado`, `conductor`, `tercero`, `testigo`) | |
| bien_afectado | id, siniestro_id, bien_id, detalle_dano | |
| documento | id, siniestro_id, tipo, archivo_ref, estado, recibido_en | |
| nota | id, siniestro_id, autor_id, texto, creada_en | |
| tarea | id, siniestro_id, titulo, estado (`pendiente`, `en_curso`, `hecha`), vence_en | historial de cambios de estado (tabla `tarea_cambio` o auditoría) |
| cierre | id, siniestro_id, perito_id, resultado_reclamo, irregularidad (bool), conclusion, valoracion (1..10), justificacion (máx. 500, obligatoria), creado_en | motivo_cambio. **Nunca se edita.** Cambiar la valoración crea un nuevo registro con motivo y el vigente es el último. |
| conjunto_reglas | id, version (`RS-1.0`), vigente_desde, topes (JSONB), activo | |
| regla | id, conjunto_id, codigo (`R01`…`R08`), nombre, grupo, parametros (JSONB), puntos_max | |
| evaluacion | id, siniestro_id, conjunto_id, puntaje, prioridad, entradas (JSONB), creada_en | **Nunca se sobrescribe.** Cada recálculo crea una fila nueva. |
| senal | id, evaluacion_id, regla_id, estado (`activada`, `no_activada`, `no_evaluable`), puntos, antecedentes (JSONB) | texto_explicacion o generación desde los datos |
| auditoria | id, usuario_id, siniestro_origen_id, accion, objeto, resultado (`permitido`, `rechazado`), fecha (la asigna el servidor) | **Solo altas.** Se bloquea UPDATE y DELETE **también en la base** (trigger o `REVOKE`) y en el modelo de Django. |

**Estados del siniestro:** `borrador` → `en_analisis` (al confirmar) → `cerrado` → `archivado`. Desde cualquier estado se puede pasar a `anulado` (carga errónea). Archivar o anular **no borra nada**.

**Normalización:** `bien.identificador_norm` en mayúsculas y sin espacios, guiones ni puntos (`AB-123 CD` → `AB123CD`). `persona.identificador` sin puntos ni espacios. Dos personas coinciden solo si coinciden el tipo y el identificador. Un nombre parecido nunca une entidades.

**Persona y bien son entidades globales de la red.** Eso es lo que permite el grafo entre espacios. El expediente (documentos, notas, tareas, relato y detalle del daño) es privado del espacio.

## 7. Motor de reglas RS-1.0

### Antecedente válido

Es otro siniestro, de **cualquier espacio**, distinto del caso analizado, con `confirmado_en` no nulo y estado `en_analisis`, `cerrado` o `archivado`. **Los anulados nunca cuentan.** Solo se evalúan siniestros confirmados.

### Reglas

`d(a, b)` = días calendario de `a` a `b`. `H` = fecha del hecho (se usa la fecha, sin la hora).

| Id | Regla | Grupo | Condición | Puntos | No evaluable si falta |
|---|---|---|---|---|---|
| R01 | Cobertura reciente | Cobertura | `d(inicio_vigencia, H)` ≤ 30 → 25. Entre 31 y 60 → 12. | 25 / 12 | inicio_vigencia |
| R02 | Pago reciente | Cobertura | 0 ≤ `d(primer_pago, H)` ≤ 15 | 20 | primer_pago |
| R03 | Persona recurrente | Persona | Antecedentes válidos de alguna persona del caso con H del antecedente en los 12 meses anteriores a H. Con 2 o más → 20, con 1 → 8. | 20 / 8 | — |
| R04 | Siniestros cercanos | Persona | Antecedente válido de alguna persona del caso con 0 < `d(H_ant, H)` ≤ 90 | 15 | — |
| R05 | Rol cruzado | Persona | Alguna persona del caso figura con **otro rol** en un antecedente válido de los 24 meses anteriores | 15 | — |
| R06 | Bien repetido | Bien | Algún bien del caso (por identificador_norm) figura en un antecedente válido de los 24 meses anteriores | 25 | — |
| R07 | Vínculo con irregularidad confirmada | Antecedente | Alguna persona o bien del caso figura en un antecedente **cerrado con `irregularidad = true`**, sin límite de tiempo. Un rechazo o un desistimiento no la activan. | 30 | — |
| R08 | Denuncia tardía | Denuncia | `d(H, fecha_denuncia)` > 3 (art. 46, Ley 17.418) | 10 | fecha_denuncia |

Los umbrales y puntos se guardan en `regla.parametros`. **No se escriben fijos en el código.**

### Topes y prioridad

- Topes por grupo: **Cobertura 30, Persona 35, Bien 25, Antecedente 30 y Denuncia 10.** La suma total se corta en **100**.
- Prioridad: **0 a 24 baja, 25 a 49 media, 50 o más alta.**

### Criterios con coincidencias múltiples

1. Una regla se activa **una sola vez** por siniestro, con el nivel más alto que corresponda, y la explicación **lista todos** los antecedentes que la cumplieron (`senal.antecedentes`).
2. Las reglas distintas del mismo grupo se suman hasta el tope del grupo.
3. Un mismo antecedente puede activar reglas de grupos diferentes, por ejemplo R06 y R07.
4. El total se corta en 100.

### Reproducibilidad y versiones

- Cada evaluación guarda el siniestro, la versión, la fecha y hora, las `entradas` (fechas usadas e ids de antecedentes), las señales con sus puntos, el total y la prioridad.
- Con las mismas entradas y la misma versión **el resultado tiene que ser idéntico**. Esto se cubre con un test.
- Se recalcula y se crea una nueva evaluación cuando: (a) se confirma el siniestro, (b) se confirma otro siniestro que comparte una persona o un bien con un caso `en_analisis`, (c) el perito pulsa "Recalcular".
- **HU-12:** el superadministrador crea una versión nueva copiando la vigente y cambiando umbrales o pesos. La anterior queda sin edición y las evaluaciones viejas conservan su versión.

### Explicación (HU-10)

Cada señal se muestra en el lenguaje del perito, con el dato del caso y el umbral. Ejemplos: "El hecho ocurrió 23 días después del inicio de vigencia. Umbral 30 días." y "El vehículo AB123CD figura en el antecedente S-2025-0381 de hace 13 meses." Una regla no evaluable indica qué dato faltó. El texto se genera **desde la misma señal** que produjo el puntaje.

### Ejemplo de control (tabla 9 del TFG)

R01 25 (20 días) + R02 20 (pago 10 días antes) → Cobertura 30 con el tope. R03 8 (1 previo hace 60 días) + R04 15 → Persona 23. R08 0. **Total 53, prioridad alta.**

## 8. Coincidencias y resumen compartido

- **Coincidencias (HU-08):** solo desde un siniestro **confirmado** del espacio del usuario. Se buscan antecedentes válidos que comparten una persona (tipo + identificador) o un bien (identificador_norm), a dos saltos. Los resultados se paginan y hay índices sobre las tablas de relación.
- **Sin coincidencias:** el mensaje es "No hay antecedentes accesibles en la red". Nunca se afirma que la persona no tenga antecedentes.
- **Promedio de valoración:** el promedio y la cantidad de casos con valoración entre los antecedentes vinculados. Se calcula en el momento, **no se guarda** y solo se muestra dentro del análisis.
- **No hay buscador general de personas.** Ningún endpoint permite buscar por DNI o nombre fuera de un expediente.
- **Resumen de un antecedente (HU-11):** se arma en el momento y **no se guarda**. Muestra tipo, fecha del hecho, vínculo (qué persona o bien coincide y con qué rol), resultado del reclamo, irregularidad, valoración, justificación, nombre del perito responsable y su correo **solo si `contacto_visible = true`**. Si el caso no está cerrado, muestra "En análisis" sin datos de cierre.
- **El resumen nunca muestra** documentos, fotos, notas, DNI, teléfono, relato ni detalle del daño. La pantalla aclara qué queda oculto.
- **Solo se puede pedir** el resumen de un antecedente que **coincide** con el siniestro de origen indicado. Cada lectura se registra en la auditoría (usuario, siniestro de origen, acción, objeto, resultado y fecha).

## 9. Funciones del expediente

- **HU-03 Registro:** formulario con póliza, hecho (tipo, fecha y hora, fecha de denuncia, lugar y relato), personas con su rol y bienes con su tipo, identificador y detalle del daño. `fecha_hecho` es obligatoria. Al guardar queda en `borrador` y no se analiza.
- **HU-04 Confirmación:** requiere póliza, fecha del hecho y al menos una persona o un bien. Pasa a `en_analisis`, guarda `confirmado_en` y dispara las coincidencias y la evaluación.
- **HU-05 Documentos:** subida al volumen privado `documentos`, con tipo y fecha de carga. La descarga se hace por un endpoint de Django que verifica el permiso. **Nunca se sirven por URL estática pública.**
- **HU-06 Notas:** quedan con fecha, hora y autor. Son privadas.
- **HU-07 Tablero:** columnas pendiente, en curso y hecha, con vencimiento opcional. Cada cambio de estado queda registrado.
- **HU-13 Cierre:** resultado del reclamo (aprobado, rechazado, desistido u otra finalización), irregularidad confirmada (sí o no), conclusión, valoración de 1 a 10 y justificación obligatoria. Rechaza valores fuera de rango y cierres sin justificación. Mostrar la escala de la tabla 2 del TFG: 1–2 no verificado con elementos que lo contradicen, 3–4 inconsistencias relevantes, 5–6 dudas concretas, 7–8 verificado con observaciones menores, 9–10 verificado sin observaciones.
- **HU-14 Archivo y anulación:** archivar conserva todo y el caso sigue contando como antecedente. Anular por carga errónea requiere un motivo, conserva el registro y la auditoría, y **el caso deja de contar como antecedente**.
- **HU-16 Panel:** lista los expedientes del perito (`perito_id = usuario`), ordenados por prioridad de la última evaluación y luego por fecha, con estado y tareas pendientes.
- **HU-17 Perfil:** correo de contacto y opción de mostrarlo. El cambio se audita.
- **HU-02 Administración:** el administrador da de alta (envía el enlace de primer ingreso), da de baja y bloquea usuarios de su espacio, y ve la auditoría de su espacio con filtros por usuario, acción y resultado. El superadministrador crea espacios con su administrador.

## 10. Pantallas

Se replican las maquetas de `referencias/` (barra lateral verde oscuro, nombre **SIGS**, contenido claro y responsive para teléfono).

| Pantalla | Referencia | Historias |
|---|---|---|
| Inicio de sesión | pantallas-01 | HU-01 |
| Mis expedientes | pantallas-02 | HU-16 |
| Registrar siniestro | pantallas-03 | HU-03, HU-04 |
| Análisis del expediente (indicador, reglas evaluadas, coincidencias y promedio) | pantallas-04 | HU-08, HU-09, HU-10 |
| Resumen del antecedente | pantallas-05 | HU-11, HU-15 |
| Seguimiento (tablero y notas) | pantallas-06 | HU-06, HU-07 |
| Cierre del expediente | pantallas-07 | HU-13 |
| Reglas del indicador (lectura para el perito, nueva versión para el superadmin) | pantallas-08 | HU-12 |
| Documentos (pestaña del expediente) | sin maqueta, mismo estilo | HU-05 |
| Perfil, administración de usuarios y auditoría | sin maqueta, mismo estilo | HU-02, HU-15, HU-17 |

El recorrido entre pantallas está en `pantallas-00-encadenamiento.png`. La pantalla de análisis lleva siempre la leyenda "La prioridad ordena qué revisar primero. No indica que haya fraude."

## 11. Datos ficticios y escenarios (TT-02)

Hay dos comandos:

- `python manage.py seed_demo`: datos para recorrer la demo, que se describen abajo.
- `python manage.py seed_escenarios`: los 30 escenarios de prueba con su resultado esperado documentado (también como fixture de tests).

### Datos de demo

- Espacios: **Estudio Pericial Norte** y **Perito Independiente Sur**.
- Usuarios (contraseñas que cumplan la política, listadas en el README): 1 superadmin, 1 administrador por espacio, 2 peritos en el Norte y 1 en el Sur. Al menos un perito con `contacto_visible = true` y otro con `false`.
- Casos de la narrativa del TFG:
  - **Incendio total EXP-2026-0147**, vehículo AB123CD, vigencia de 23 días y pago 8 días antes, con un antecedente S-2025-0381 del mismo vehículo en el **otro espacio** (aprobado, valoración 7). El resultado tiene que ser 55, prioridad alta, como en la maqueta.
  - **Robo de rueda de auxilio** con el mismo dominio repetido en varios antecedentes de los dos espacios.
  - Un antecedente cerrado **con irregularidad confirmada** para mostrar R07.
  - Un caso **anulado por carga errónea** que no tiene que aparecer como antecedente.
  - Casos sin coincidencias.

### Escenarios por regla (24, tres por regla)

Cada escenario se arma para que **solo** se active la regla probada.

| Regla | Activa | No activa | Límite o sin datos | Activaciones esperadas |
|---|---|---|---|---|
| R01 | Hecho a 20 días de la vigencia, 25 | Hecho a 75 días, 0 | Hecho a 30 días, 25 | 2 |
| R02 | Pago 10 días antes del hecho | Pago 40 días antes | Sin fecha de primer pago, no evaluable | 1 |
| R03 | 2 previos en 12 meses, 20 | Sin previos | 1 previo, 8 | 2 |
| R04 | Previo hace 45 días | Previo hace 150 días | Previo hace 90 días, se activa | 2 |
| R05 | Testigo en otro siniestro hace 10 meses | Mismo rol en el otro siniestro | Rol cruzado hace 25 meses, no se activa | 1 |
| R06 | Mismo dominio hace 8 meses | Dominio distinto | Dominio escrito `AB-123-CD`, se activa por la normalización | 2 |
| R07 | Antecedente con irregularidad confirmada | Antecedente rechazado sin irregularidad | Antecedente anulado con irregularidad, no se activa | 1 |
| R08 | Denuncia a los 5 días | Denuncia al día siguiente | Denuncia a los 3 días, no se activa | 1 |
| **Total** | | | | **12** |

### Escenarios combinados (6)

| Id | Caso | Reglas esperadas | Resultado esperado |
|---|---|---|---|
| C1 | Tabla 9: vigencia de 20 días, pago 10 días antes, un previo de la persona hace 60 días, denuncia al día siguiente | R01, R02, R03, R04 | 53, alta |
| C2 | Robo de rueda a los 40 días de la vigencia (pago 35 días antes), dos robos previos de la misma persona y el mismo dominio, uno hace 60 días y otro hace 8 meses, siempre como asegurado | R01 (12), R03, R04, R06 | 72, alta |
| C3 | El mismo antecedente coincide por el bien y está cerrado con irregularidad confirmada (persona distinta, cobertura y pago viejos) | R06, R07 | 55, alta |
| C4 | Tres previos de la persona, todos entre 91 días y 12 meses, y un rol cruzado como tercero. R03 se activa una vez y lista los 3 | R03, R05 | 35, media |
| C5 | Cumple las 8 reglas, 130 antes de los topes | R01 a R08 | 100, alta |
| C6 | Hecho a 200 días de la vigencia, sin coincidencias, sin primer pago y con denuncia en plazo | Ninguna (R02 no evaluable) | 0, baja |
| **Total** | | **20 activaciones** | |

**Esperado global: 32 activaciones, 0 falsos positivos y 0 falsos negativos, es decir 100 % de precisión y de sensibilidad.** El comando `python manage.py evaluar_escenarios` imprime esta tabla y las métricas.

## 12. Pruebas obligatorias (deben pasar y reproducir el Anexo 8 del TFG)

`pytest` (o `manage.py test`) en el backend.

### Reglas

- Los 30 escenarios con el resultado exacto de las tablas anteriores (reglas activadas, puntos, topes, total y prioridad).
- Reproducibilidad: recalcular con las mismas entradas y la misma versión da un resultado idéntico.
- Versionado: una nueva versión no altera las evaluaciones viejas.

### Acceso: 8 pruebas × 3 solicitudes directas a la API = 24 rechazos

Cada solicitud **tiene que ser rechazada** (403 o 404, sin filtrar datos) y **tiene que quedar en la auditoría con `resultado = rechazado`**.

| Id | Solicitud no autorizada |
|---|---|
| A1 | Pedir coincidencias de un siniestro que no fue confirmado |
| A2 | Abrir por su id un expediente de otro espacio de trabajo |
| A3 | Descargar por URL directa un documento privado de otro perito o espacio |
| A4 | Leer notas y tareas de un expediente ajeno |
| A5 | Buscar una persona por DNI sin un expediente de origen |
| A6 | Pedir el resumen de un antecedente que no coincide con el siniestro de origen |
| A7 | Editar o borrar un registro de auditoría con perfil administrador |
| A8 | Publicar una versión de reglas con perfil perito o administrador |

### Funcionales

| Id | Verificación |
|---|---|
| F1 | Archivar un expediente conserva su auditoría |
| F2 | Una carga errónea no aparece como antecedente |
| F3 | La valoración rechaza valores fuera de 1 a 10 |
| F4 | El cierre no se guarda sin justificación |

### Seguridad

- Bloqueo al 5.º intento, envío del correo y desbloqueo al restablecer.
- Mensaje de error genérico en el login.
- Enlace de restablecimiento vencido a la hora y de un solo uso.
- Usuario dado de baja no puede ingresar.
- La auditoría no se puede modificar ni siquiera con SQL directo del usuario de la aplicación.

Además, cada historia (Anexo A) tiene al menos un test de su criterio de aceptación.

## 13. Instructivo y entrega (lo que se sube a Drive)

El repositorio tiene que incluir:

1. `README.md` en español con: qué es el prototipo, requisitos (Docker y Docker Compose), pasos de puesta en marcha (`cp .env.example .env`, `docker compose up --build`, migraciones, `seed_demo`), URLs (app en `http://localhost`, Mailpit en `http://localhost:8025`), **usuarios de demo con su contraseña y rol**, un **recorrido sugerido** paso a paso (ingresar como perito, abrir EXP-2026-0147, ver el análisis, abrir el resumen, cerrar con valoración, probar el bloqueo de cuenta y ver el correo en Mailpit, ingresar como administrador y ver la auditoría), cómo correr las pruebas y `evaluar_escenarios`, y la aclaración de que **todos los datos son ficticios**.
2. `.env.example` sin secretos reales.
3. `docker-compose.yml` que levante todo con un solo comando, sin pasos manuales extra.
4. Un script o comando para generar un `.zip` del repositorio limpio (sin `node_modules`, `.venv` ni volúmenes) para subir a Drive.

## 14. Orden sugerido de tareas

| Id | Tarea | Depende de | Check de aceptación |
|---|---|---|---|
| T01 | Monorepo `backend/`, `frontend/`, `nginx/`, `docker-compose.yml` y Mailpit | — | `docker compose up` levanta los 5 servicios y `/api/health` responde |
| T02 | Modelos, migraciones y constraints (únicos, normalización, auditoría solo altas en la base) | T01 | Las migraciones aplican y un UPDATE o DELETE sobre auditoría falla |
| T03 | Auth: login con sesión, roles, política de contraseña, primer ingreso, bloqueo a los 5 intentos con correo, restablecimiento de 1 h y sesión de 60 min | T02 | Tests de seguridad en verde |
| T04 | Permisos por objeto y middleware o helper de auditoría (permitido y rechazado) | T03 | A2, A4 y A7 en verde |
| T05 | CRUD de siniestro con personas, bienes, póliza y confirmación | T04 | Tests de HU-03 y HU-04 |
| T06 | Documentos (volumen privado y descarga con permiso), notas y tareas | T05 | A3, A4, HU-05, HU-06 y HU-07 |
| T07 | Grafo y coincidencias con índices y paginación, mensaje vacío y promedio de valoración | T05 | HU-08, A1 y A5 |
| T08 | Motor de reglas RS-1.0 versionado, evaluaciones y señales | T07 | 30 escenarios, 32 activaciones y reproducibilidad |
| T09 | Resumen del antecedente minimizado y auditado | T07 | HU-11 y A6 |
| T10 | Cierre con historial de valoración, archivo y anulación | T05 | HU-13, HU-14, F1 a F4 |
| T11 | Versionado de reglas por el superadmin | T08 | HU-12 y A8 |
| T12 | Administración de usuarios y espacios, auditoría del espacio y perfil de contacto | T04 | HU-02, HU-15 y HU-17 |
| T13 | Frontend: layout SIGS y las pantallas de la sección 10 | T05–T12 | Recorrido completo en el navegador |
| T14 | `seed_demo`, `seed_escenarios` y `evaluar_escenarios` | T08 | EXP-2026-0147 da 55, alta, y las métricas dan 100 % |
| T15 | README, `.env.example` y script de zip | T13, T14 | Se levanta desde cero en una máquina limpia siguiendo solo el README |

## 15. Supuestos de implementación

Son decisiones que el TFG no fija y se tomaron al implementar.

1. R02 solo se activa si el pago es **anterior o del mismo día** que el hecho (`0 ≤ días ≤ 15`). Un pago posterior al hecho no la activa.
2. R03, R04 y R07 cuentan a la persona **con cualquier rol**. R05 es la única que mira el cambio de rol.
3. Las ventanas de 12 y 24 meses se cuentan hacia atrás desde la fecha del hecho del caso analizado.
4. Cada perito accede solo a los expedientes que tiene asignados. De los casos de otros peritos ve únicamente el resumen de los antecedentes que coinciden con un siniestro suyo confirmado.

---

## Anexo A · Historias de usuario con criterios de aceptación (copiadas del TFG)

**HU-01 Inicio de sesión y roles.** Como perito quiero ingresar con mi correo y contraseña para trabajar solo con los expedientes de mi espacio.
1. Dado un correo y una contraseña válidos, cuando ingreso, entonces el sistema muestra mi panel de expedientes.
2. Dada una contraseña incorrecta, cuando intento ingresar, entonces el sistema muestra un aviso sin indicar cuál de los dos datos falló.
3. Dado un usuario con rol perito, cuando intenta abrir la administración de reglas, entonces el sistema le niega el acceso.

**HU-02 Administración de usuarios y espacios de trabajo.** Como administrador quiero dar de alta y de baja usuarios en mi espacio para controlar quién accede a los expedientes.
1. Dado un correo que no existe en el espacio, cuando lo doy de alta con un rol, entonces el usuario puede ingresar con ese rol.
2. Dado un usuario dado de baja, cuando intenta ingresar, entonces el sistema le niega el acceso y conserva su historial.

**HU-03 Registro de siniestro.** Como perito quiero registrar un siniestro con su póliza, personas y bienes para tener el caso completo en un solo lugar.
1. Dado un formulario sin fecha del hecho, cuando intento guardar, entonces el sistema indica que el dato es obligatorio.
2. Dado un bien con identificador escrito con espacios o guiones, cuando lo guardo, entonces el sistema lo normaliza.
3. Dado un siniestro guardado, cuando no lo confirmo, entonces queda como borrador y no se analiza.

**HU-04 Confirmación del siniestro.** Como perito quiero confirmar el siniestro para que el sistema lo analice y lo use como antecedente.
1. Dado un borrador con póliza, fecha del hecho y al menos una persona o un bien, cuando lo confirmo, entonces pasa a estado en análisis.
2. Dado un siniestro confirmado, cuando se confirma, entonces el sistema dispara la búsqueda de coincidencias y el cálculo del indicador.

**HU-05 Documentos del perito.** Como perito quiero guardar en el expediente mis propios documentos, como las fotos de la inspección, para tenerlos junto al caso sin depender del sistema de cada compañía.
1. Dado un documento cargado, cuando indico su tipo, entonces aparece en la lista del expediente con su fecha de carga.
2. Dado un documento privado, cuando otro perito consulta el resumen del caso, entonces el documento no se muestra ni se puede descargar.

**HU-06 Notas privadas del expediente.** Como perito quiero escribir notas en el expediente para registrar lo que hago y no depender de papeles sueltos.
1. Dada una nota nueva, cuando la guardo, entonces queda con fecha, hora y autor.
2. Dada una nota de un expediente, cuando otro perito consulta el resumen, entonces la nota no se muestra.

**HU-07 Tablero de tareas del expediente.** Como perito quiero ordenar mis pendientes en un tablero para ver qué falta hacer en cada caso.
1. Dada una tarea nueva, cuando la creo con fecha de vencimiento, entonces aparece en la columna pendiente.
2. Dada una tarea, cuando la muevo a otra columna, entonces cambia su estado y queda registrado el cambio.

**HU-08 Búsqueda de coincidencias.** Como perito quiero ver los antecedentes que comparten una persona o un bien con mi caso para no depender de contactos personales.
1. Dado un siniestro confirmado, cuando existe otro siniestro válido con el mismo identificador de persona o de bien, entonces aparece en la lista de coincidencias.
2. Dado un antecedente anulado por carga errónea, cuando se buscan coincidencias, entonces no se incluye.
3. Dado un caso sin coincidencias, cuando termina la búsqueda, entonces el sistema informa que no hay antecedentes accesibles en la red.
4. Dados antecedentes vinculados con valoración pericial, cuando abro el análisis, entonces veo el promedio y la cantidad de casos, sin que ese valor quede guardado como nota de la persona.

**HU-09 Cálculo del indicador de prioridad.** Como perito quiero un indicador de 0 a 100 para decidir qué caso revisar primero.
1. Dado un caso con reglas activadas, cuando se calcula el indicador, entonces se aplican los topes por grupo y el total no supera 100.
2. Dado un caso al que le falta una fecha, cuando se calcula, entonces la regla que la necesita queda como no evaluable y suma cero.
3. Dados los mismos datos y la misma versión de reglas, cuando se recalcula, entonces el resultado es idéntico.

**HU-10 Explicación de las reglas.** Como perito quiero ver qué regla se activó y con qué datos para entender el indicador y contrastarlo con mi expediente.
1. Dado un indicador calculado, cuando abro el análisis, entonces veo cada regla con sus puntos, su umbral y el dato del caso.
2. Dada una regla no evaluable, cuando abro el análisis, entonces el sistema indica qué dato faltó.

**HU-11 Consulta del resumen de un antecedente.** Como perito quiero leer el resumen de un antecedente para conocer su resultado sin pedir acceso al expediente ajeno.
1. Dada una coincidencia, cuando abro su resumen, entonces veo tipo, fecha, vínculo, resultado, irregularidad, valoración, justificación y perito responsable.
2. Dado un resumen, cuando lo abro, entonces no veo documentos, fotos, notas ni datos de contacto.
3. Dado un perito responsable que habilitó su contacto, cuando abro el resumen, entonces veo su correo. Si no lo habilitó, no se muestra.
4. Dado un perito sin un siniestro confirmado que lo vincule, cuando pide el resumen por la API, entonces el sistema lo rechaza.

> Nota: en el criterio 2, "datos de contacto" se refiere a los del asegurado y los terceros. El correo del perito responsable sigue la regla del criterio 3.

**HU-12 Administración de versiones de reglas.** Como superadministrador de la plataforma quiero crear una nueva versión del conjunto de reglas para ajustar umbrales sin alterar las evaluaciones anteriores.
1. Dado el conjunto vigente, cuando cambio un umbral o un peso, entonces se crea una versión nueva y la anterior queda guardada sin edición.
2. Dada una evaluación anterior, cuando cambia la versión vigente, entonces conserva la versión con la que se calculó.

**HU-13 Cierre del expediente con valoración.** Como perito quiero cerrar el expediente con mi conclusión y una valoración de 1 a 10 para dejar un resumen útil a otros peritos.
1. Dado un cierre sin justificación, cuando intento guardarlo, entonces el sistema indica que es obligatoria.
2. Dado un cierre, cuando lo guardo, entonces el resultado del reclamo y la irregularidad confirmada quedan como datos separados.
3. Dado un cierre guardado, cuando cambio la valoración, entonces se registra un nuevo valor con el motivo y se conserva el anterior.

**HU-14 Archivo y anulación por carga errónea.** Como perito quiero archivar un expediente o anularlo por carga errónea para ordenar mi trabajo sin perder el registro.
1. Dado un expediente archivado, cuando se consulta la auditoría, entonces sus consultas siguen disponibles.
2. Dado un expediente anulado por carga errónea, cuando otro caso busca coincidencias, entonces no aparece como antecedente.

**HU-15 Registro de auditoría.** Como administrador quiero que cada consulta y cambio quede registrado para poder revisar accesos indebidos.
1. Dada una consulta de resumen, cuando se realiza, entonces se guarda usuario, expediente de origen, acción, fecha y resultado.
2. Dado un registro de auditoría, cuando cualquier usuario intenta editarlo o borrarlo, entonces el sistema no lo permite.

**HU-16 Panel de expedientes del perito.** Como perito quiero ver mis expedientes ordenados por prioridad para organizar el día.
1. Dados varios expedientes, cuando abro el panel, entonces aparecen ordenados por prioridad y luego por fecha.
2. Dado un expediente de otro perito, cuando abro mi panel, entonces no aparece.

**HU-17 Perfil y correo de contacto.** Como perito quiero mostrar un correo de contacto en mi perfil para que otros peritos puedan consultarme sobre un caso que traté.
1. Dado mi perfil, cuando cargo un correo y activo la opción de mostrarlo, entonces aparece en los resúmenes de mis casos cerrados.
2. Dado un contacto desactivado, cuando otro perito abre el resumen de mi caso, entonces el correo no se muestra.
3. Dado un cambio en la opción de contacto, cuando lo guardo, entonces queda registrado en la auditoría.
