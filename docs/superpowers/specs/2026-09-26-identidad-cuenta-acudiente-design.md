# Cuenta del acudiente + refactor ADR-0019 de Identidad — diseño (sub-proyecto A)

> **Estado:** aprobado para escritura del spec (2026-09-26). Siguiente paso: plan de
> implementación (skill `writing-plans`), luego código bajo TDD.
>
> **Alcance:** el sub-proyecto **A** de la descomposición del sistema de cuentas de acudiente.
> A = refactor interno de Identidad a puertos-y-adaptadores (ADR-0019) **+** creación de cuenta
> con contraseña como primer paso de `/empezar` **+** hijos como apodos (Ley 1581) **+** el panel
> admin de acudientes por colegio con estado del trabajo por-padre.
>
> **Diferido explícitamente** (cada uno su propio spec → plan → código):
> **B** panel del padre para seguir su trabajo · **C** revisar→pagar (Wompi) + seguimiento de
> despacho · **D** historial/medios de pago/preferencias · broker/saga/observabilidad
> (ADR-0020–0025). El **cambio de kit** (`fijar_producto_en_linea` desde el padre) queda fuera.

---

## 0. Por qué existe este trabajo

El pipeline que construyeron los refactors de `comercio` y `operacion` ya sabe crear un colegio
(poller de Identidad) y un trabajo de 3 kits (poller de Inteligencia). Lo que **no** existe es un
acudiente **real** que sea dueño de ese trabajo, lo reciba y lo pague. Hoy la subida de una lista
acuña un usuario **invitado sin credencial** a mitad del flujo (`clave_hash="sin-credencial"`), y
ese id transitorio viaja como `contacto_referencia`. Es el "error más tonto" que este trabajo
corrige: **crear (o iniciar sesión de) un usuario real ANTES de armar el kit**, como primer paso de
`/empezar`, no como un contacto de relleno después de subir.

De ese cambio salen, casi gratis, las otras cosas pedidas: saber quiénes son los clientes (nombre,
correo, celular), a qué hijos les compran (por **apodo**, nunca el nombre del menor — Ley 1581), y
**trazabilidad de acudientes por colegio** en las dos direcciones (el padre ve el estado de su
trabajo; el admin ve, por colegio, qué familias hay y en qué estado va su kit).

---

## 1. Entendimiento compartido (lo que el usuario pidió, separado de lo asumido)

**Dicho por el usuario:**

- Crear/iniciar sesión de un usuario debe ser el **primer paso** de `/empezar`, no el segundo.
- Capturar identidad del acudiente: **nombre, correo, celular**.
- Capturar sus hijos y sus **apodos** "para no infringir la ley".
- Ver el **estado del pipeline de un trabajo solicitado**: desde notificación aprobada-por-humano →
  revisar los kits → elegir → pagar (Wompi) → crear la orden.
- **Contraseña en `/empezar`** (decisión tomada): cuentas reales con credencial desde el minuto
  uno; nada de "crear → redirigir a login → volver".
- **Nada más simple:** `REVISION_ARQUITECTURA.md` es el listón real (broker real, microservicios,
  resiliencia, observabilidad, saga), no aspiracional.
- En el **admin** se ven **ids en vez de nombres** (en trabajos, cola, etc.), y **no hay pestaña de
  acudientes** para revisar. Sugirió: "¿tal vez dentro de colegio?", con notas de estado (en
  espera, entregado).
- **Diferenciar** la primera corrida de un (colegio+grado) del trabajo de 3 kits de un padre
  específico.

**Asumido / derivado y confirmado en código (no dicho literal):**

- El motor de autorización con ámbito (ADR-0013) **ya existe** y el rol `acudiente` **ya está
  sembrado**; "solo mis hijos" ya está implementado como el vínculo directo de `matriculas_visibles`.
  Por tanto A **extiende** ese motor, no inventa uno.
- Catálogo **ya persiste** `contacto_referencia` en la fila `TAREA` y lo arrastra hasta la
  aprobación (`admin_http.py:1311-1339`): **no hace falta cambiar Catálogo** para tener el id real
  del padre en la aprobación.
- La consola de curaduría del admin es **deliberadamente libre de PII** hoy
  (`DecisionTrabajo.tsx:106`). Mostrar nombres es un **nuevo** acceso a dato personal y va detrás de
  permiso, no un simple cambio de UI.
- `nombre_cifrado` del `Usuario` **hoy siempre es NULL** (la creación de cuenta nunca pidió el
  nombre): por eso el admin ve ids. Cuenta-first es lo que hace que el nombre **exista**.

**Éxito se ve así:** un acudiente nuevo entra a `/empezar`, crea su cuenta con contraseña (queda
logueado), registra a sus hijos por apodo, y arma su kit — todo colgado de su `usuario_id` real. Un
acudiente que vuelve entra con correo+contraseña. El admin, dentro de un colegio, ve la lista de
acudientes con nombre + hijos(apodos) + estado de **su** trabajo, y en las pantallas de
trabajos/cola ve `colegio · grado` en vez de UUIDs crudos. Los 106 tests de Identidad siguen verdes
tras el refactor; la lógica nueva entra con TDD.

---

## 2. Dos objetos que NO se confunden — versión compartida vs trabajo del padre

Esta es la distinción que el usuario pidió marcar, y el esquema ya la impone.

| | **Versión (colegio+grado)** | **Trabajo de 3 kits del padre** |
|---|---|---|
| Qué es | La lista oficial curada de un (colegio, grado) | La corrida que produce los 3 kits para los hijos+preferencias de **este** padre |
| Dueño | El (colegio, grado) — todos lo comparten | Un `usuario_id` (`trabajo_pipeline.hijos`, `trabajo.py:72`) |
| Vive en | Catálogo — `lista_oficial` + `TAREA` | Inteligencia — `trabajo_pipeline` |
| Estados | `revisada_en` / `publicada_en`; `TAREA`: `pendiente→en_curso→completada` | `EstadoTrabajo`: `encolado→procesando→espera_revision→publicado` (+`fallido`) |
| Se cura | **Una vez** ("una vez revisada no se vuelve a abrir", `listas.py:104`) | Por padre |
| Pantalla admin | cola / onboarding | trabajos / consola de revisión |

**Acoplamiento (verificado):**

- **Primer padre de un (colegio, grado) nuevo:** subir → versión PENDIENTE → el admin la cura **una
  vez** en cola/onboarding → aprobar publica la lista *y* destraba el trabajo de ese padre
  (`espera_revision → publicado`, `trabajos.py:530-531`).
- **Padre posterior de un (colegio, grado) ya publicado:** **ruta rápida** — `aplicar-canonico`
  (`api.py:941`) aplica su nivel+personaje sobre la "caché bendita" **sin re-optimizar y sin
  re-curar**. Igual obtiene **su propio** trabajo; la lista compartida no se toca.

**Consecuencia para el panel admin (el bug que la intuición del usuario atrapó):** la columna de
estado del panel lee **el `EstadoTrabajo` del propio padre**, resuelto por **su** `usuario_id` —
**nunca** el estado de la versión compartida. Si leyera la versión, toda familia de un colegio
publicado se vería "en revisión" cuando lo que está en revisión es la **lista**, no su kit.

---

## 3. Arquitectura — un solo spec, dos fases ordenadas

### Fase 1 — refactor ADR-0019 de Identidad (sin cambio de comportamiento; 106 tests verdes)

Se copia **verbatim** la plantilla ya construida en `operacion`/`comercio` (ADR-0019 aplicada). No
se inventa forma nueva.

```
servicios/identidad/tukit_identidad/
  api.py            # SOLO ensamblador: crear_app + _arrancar/_apagar + include_router (comercio api.py = 66L)
  routers/
    __init__.py     # exporta `router`
    identidad.py    # los 16 handlers: parsear → llamar dominio → traducir a sobre de error
  dominio/
    __init__.py     # docstring "no hay Protocol"; funciones puras
    sesiones.py     # MOVER sesiones.py aquí tal cual (ya es puro: PBKDF2 + HMAC)
    autorizacion.py # partes puras: Ambito, puede(), campos_visibles() (el SQL se va al repo)
    directorio.py   # lookup de directorio_bogota (puro, en memoria)
  repositorios/
    __init__.py     # docstring "no hay Protocol de repositorio"
    identidad.py    # RepoIdentidad: TODO el SQL, Base.metadata.tables[...].c
  modelos/          # SIN CAMBIOS
  poller.py         # queda como entrypoint CLI (espejo del repartidor de operacion)
  cargador.py       # queda como CLI
  sembrar_acceso.py # queda como CLI (se le añaden filas en Fase 2)
```

**Reglas de capa (verificadas en los `__init__.py` de ambos hermanos):**

- **SIN `Protocol` de repositorio.** Una sola implementación de SQL contra la base propia, ejercida
  por las pruebas contra **SQLite real**, no un doble. Igual el dominio: un `Protocol` con una sola
  implementación sería indirección sin uso. (El único puerto `Protocol` que gana su sitio ya existe:
  `Cifrador` en `libs/`, con dos adaptadores Fernet/EnClaro — Identidad no necesita otro.)
- **`dominio/` puro:** solo dataclass/enum/typing/stdlib. Recibe datos **ya buscados** (dicts,
  listas), devuelve tipos planos o excepciones tipadas. Sin FastAPI / SQLAlchemy-execute / httpx.
- **`repositorios/`:** SQLAlchemy Core vía `Base.metadata.tables["..."]` con `.c`; el router abre la
  unidad de trabajo y construye el repo atado a la conexión:
  `async with request.app.state.motor.sesion() as db: repo = RepoIdentidad(await db.connection())`.
  Todo I/O remoto ocurre **antes** de abrir la sesión.
- **Sobre de error:** `ErrorDominio(razon, mensaje, *, estado, campo)` → `JSONResponse`
  `{error, mensaje, campo}` (patrón de `tukit_comun/http.py`); **nunca** hace echo del input.

**Normalización obligada en Fase 1 (única divergencia detectada):** `POST /v1/contactos` usa hoy
`app.state.motor.engine.begin()` directo (`api.py:286`) en vez del `motor.sesion()` unidad-de-trabajo
que usan los hermanos. Las **16 rutas** se migran al mismo scope; no se copia el handler tal cual.

**Orden TDD de la Fase 1 (por el ADR-0019, §B.1):** (a) escribir tests de dominio puro **fallando**
contra la API deseada de `dominio/` (sesiones y autorización ya son casi puros → cosecha directa);
(b) extraer dominio (verde); (c) extraer `repositorios/` (SQL fuera del handler, comportamiento
intacto); (d) adelgazar `routers/`; (e) **confirmar los 106 tests de integración verdes**. Si uno se
pone rojo, la extracción cambió comportamiento → revertir.

### Fase 2 — la cuenta del acudiente sobre las capas ya limpias

Todo lo de abajo entra en `routers/` + `dominio/` + `repositorios/`, **nunca** en el monolito.

---

## 4. Backend (Fase 2)

### 4.1 Endpoints nuevos de Identidad

- **`POST /v1/cuenta`** (crear cuenta): recibe `nombre`, `correo`, `celular`, `clave`. Hashea la
  clave con `hashear_clave` (credencial **real**, no el centinela), cifra y guarda `nombre_cifrado`,
  asigna el rol `acudiente` con ámbito `COLEGIO` (ver §4.4), y **emite sesión** devolviendo
  `{sesion, token}` — **la misma forma** que `POST /v1/sesiones`. Idempotencia por correo: si ya
  existe una cuenta **con credencial real**, responde **409 `correo_ya_registrado`** ("inicia
  sesión"). Si existe como **invitado** (`sin-credencial`, nacido de una subida vieja), **la
  promueve** poniéndole clave+nombre — no crea una segunda.
- **`POST /v1/cuenta/hijos`** (registrar un hijo): recibe `apodo`, `colegio_id`, `grado`, y
  **`consentimiento_menor` (aceptación explícita)**. En **una transacción** crea la cadena
  `Estudiante`(nombre_cifrado NULL) + `Matricula`(colegio, grado) + `AcudienteMatricula`(vínculo al
  padre + `apodo_cifrado`) + `Consentimiento`(regimen=`registro_menor`, matricula_id). El CHECK
  `consentimiento_menor_coherente` (`privacidad.py:108`) hace que **sin consentimiento la BD
  rechace** la matrícula: la casilla no es opcional, es invariante de esquema.
- **`GET /v1/cuenta/hijos`** (mis hijos): lectura **acotada al padre** vía `matriculas_visibles`
  (vínculo directo `AcudienteMatricula.usuario_id == token.sub`) + `campos_visibles` (descifra
  `apodo` solo si pasa `estudiante:leer:apodo`). Devuelve `apodo + grado + colegio`. Es la
  superficie de **trazabilidad del lado del padre**.

### 4.2 Migración de esquema (Identidad)

- Columna **`apodo_cifrado`** (`LargeBinary`, nullable) en `acudiente_matricula`. Se cifra con el
  mismo `cifrador_desde_entorno()` que `nombre_cifrado` (migración `claro:`→Fernet segura).
- Filas nuevas en la siembra de acceso (§4.4) — no es DDL, es data, va idempotente.

### 4.3 Cambio en el pipeline (el defecto original)

Hoy `POST /v1/listas/subir` acuña un **invitado transitorio** a mitad de la subida
(`inteligencia/api.py` → `identidad.registrar_contacto`). Tras Fase 2:

1. **`POST /v1/listas/subir` exige `Authorization: Bearer`.** Inteligencia toma el `usuario_id` del
   claim `sub` del JWT en vez de crear un contacto.
2. `registrar_contacto` pasa a ser **solo-resuelve** (no crea) para usuarios autenticados; la ruta
   de creación-por-subida queda como camino del invitado legacy, no la forma normal de nacer.
3. Se pasa `usuario_id` explícito a `trabajos.crear` (ya lo acepta y salta Identidad si viene).
4. Catálogo **ya** guarda ese `usuario_id` en `TAREA.contacto_referencia` y lo arrastra a la
   aprobación: **sin cambios en Catálogo**. Al aprobar la versión, el trabajo se crea con el
   `usuario_id` real del padre → dueño de versión → trabajo → (luego, sub-proyecto C) orden.

> Efecto: un usuario **real y con credencial** es dueño de toda la cadena antes de comprar.

### 4.4 Autorización (extiende ADR-0013 — NO es un motor nuevo)

El motor con ámbito ya existe; A añade cuatro cosas concretas en `sembrar_acceso.py` +
`autorizacion.py`:

1. **Permiso `estudiante:leer:apodo`**, clasificación **`menor`**, otorgado a `acudiente`. Es lo que
   `campos_visibles` evalúa para descifrar el apodo del propio hijo.
2. **Permiso `usuario:leer:nombre`**, clasificación **`personal`** (un adulto, **no** `menor`),
   otorgado a `admin` y `operador`. Es lo que habilita el panel admin a mostrar el nombre del
   acudiente (§5.2). La consola de curaduría **no** recibe este permiso: sigue libre de PII.
3. Al **crear cuenta** se inserta `AsignacionRol(acudiente, ámbito=COLEGIO del primer hijo)`,
   espejando exactamente lo que `usuarios_demo` ya siembra.
4. "Solo mis hijos" **no se programa**: es el conjunto `directas` de `matriculas_visibles`
   (`autorizacion.py:221`), que ya resuelve el vínculo directo padre→matrícula. Las reglas
   asimétricas leer/escribir ya están.

> El plan del recon decía "no existe rol acudiente ni concepto propio-vs-cualquiera". **Falso,
> verificado:** `acudiente` está sembrado (`sembrar_acceso.py:46`) y `matriculas_visibles` ya
> implementa "lo mío". A **reutiliza** el motor completo.

### 4.5 Allowlist de privacidad (OpenAPI)

`test_api_identidad.py::test_el_esquema_publicado_no_anuncia_ninguna` se extiende con
`/v1/cuenta/hijos` y `/v1/cuenta/hijos/...`: devuelven **apodos del propio padre** (clasificados
menor, tras permiso), **nunca** nombres de menor. La prueba sigue siendo el guardián Ley-1581 y hay
que ampliar la lista **a propósito**, no de refilón.

---

## 5. Frontend (Fase 2)

### 5.1 `/empezar` — descomposición §B.6 de `FormularioEmpezar.tsx` (835L)

Objetivo: shell servidor + `maquina-empezar.ts` (reducer de unión discriminada) + islas por paso +
`enviar-solicitud.ts` **puro**.

- **`maquina-empezar.ts` (nuevo, reducer puro):** unión discriminada por `paso`
  (`"cuenta" | "hijos" | "preferencias" | "resumen"`); `reducir(estado, accion)` sin efectos;
  `puedeAvanzar(estado)`. Testeable con `node --test`.
- **Nuevo primer estado `paso:"cuenta"`:** campos `nombre / correo / celular / clave` + toggle **"Ya
  tengo cuenta"**.
  - Toggle **OFF** (nuevo): validar → `crearCuenta` → auto-login (cookie) → avanza a `hijos`.
  - Toggle **ON** (retornador): `correo + clave` → `iniciarSesion` → cookie → avanza a `hijos` (o
    enruta por rol si no es acudiente).
- **Paso "contacto" ELIMINADO:** el correo+celular vivían en el viejo paso 2; ahora son de la cuenta
  = **una sola fuente de verdad**. La máquina baja a `cuenta → hijos → preferencias → resumen`.
- **Islas "use client":** `IslaCuenta`, `IslaHijos` (reusa SelectorColegio/BuscadorDirectorio/
  SelectorGrado/SelectorPersonaje + campo apodo + casilla de consentimiento), `IslaPreferencias`,
  `BarraProgreso`.
- **`enviar-solicitud.ts` (nuevo, puro + envío):** las 3 ramas existentes con nombre —
  `aplicarCanonico` (ruta rápida) / `crearTrabajo` / `subirListas` — envueltas desde
  `api-navegador.ts`. Ahora todas mandan el `Authorization: Bearer` de la sesión creada.
- **Ruta nueva `POST /empezar/api/cuenta`:** un route handler que hace `crearCuenta` + set-cookie
  (decisión tomada: opción C). `/ingresar` queda como **fallback** para enlaces directos; **no** se
  duplica el formulario de login dentro de la isla.
- **Puerto nuevo `OrigenDatos.crearCuenta(datos): Promise<{ sesion; token }>`** (espeja
  `iniciarSesion`) en `libs/ts/tukit-contrato/src/origen.ts` + su doble de test. **No** existe hoy
  (verificado: solo `iniciarSesion`).

### 5.2 Admin — dos dolores distintos, dos arreglos

**Dolor 1 — UUIDs crudos donde va una etiqueta humana (cero PII).** Lo que se ve en trabajos/cola/
onboarding **no** es el id del padre (el admin ni lo renderiza): es el **`trabajo_id`** y, cuando el
nombre del colegio es null, el **`colegio_id`** (`onboarding/page.tsx:100`). `colegio + grado` es
dato público. Se reemplaza el UUID por **"San Pedro · Cuarto"**: puro UX, sin costo de cumplimiento.

**Dolor 2 — no hay vista de acudientes, y hasta hoy no había nombre que mostrar.** Cuenta-first crea
el nombre; A añade el panel:

- **Panel de acudientes dentro de `colegios/[colegio]`** (la intuición del usuario, correcta): lista
  de familias del colegio con **nombre del acudiente + hijos(apodos) + estado del trabajo por-padre**.
- **Nombre detrás de permiso:** el nombre del acudiente se muestra solo si el usuario admin pasa
  `usuario:leer:nombre` (clasificación personal), resuelto por `campos_visibles`, y el acceso queda
  logueable (Ley 1581 Art. 15). La consola de curaduría **sigue libre de PII**: el operador que
  valida un cuaderno no necesita saber la familia. Los nombres viven **solo** en este panel.
- **Columna de estado = `EstadoTrabajo` del propio padre** (§2), resuelto por su `usuario_id`;
  **nunca** el estado de la versión compartida.

**Caveat de alcance (honesto):** "en espera / procesando / en revisión / publicado" se lee del
`EstadoTrabajo` de Inteligencia → **A lo muestra**. Pero **"despachado / entregado"** vive en la
orden+envío de **Comercio**, que es territorio del sub-proyecto **C**. En A el panel muestra
*nombre · hijos(apodos) · colegio · estado-de-trabajo*; la columna de **despacho** se llena cuando
aterrice C. No se pinta una columna "entregado" respaldada por nada.

---

## 6. Manejo de errores y pruebas

- **Sobre de error:** `ErrorDominio(razon, mensaje, *, estado, campo)` → `{error, mensaje, campo}`,
  patrón hermano verbatim. Razones nuevas: `correo_ya_registrado` (409), `clave_debil` (422),
  `hijo_sin_colegio` (422), `consentimiento_requerido` (422).
- **TDD, RED→GREEN→suite completa.** Pago de la Fase 1 (§B.7): reglas que hoy exigen FastAPI+Postgres
  (sesión/token, ámbito de autorización) pasan a tests `assert` puros sobre `dominio/`.
- **Lógica nueva de Fase 2 con test primero:** validación de `crearCuenta` (correo duplicado,
  promoción de invitado, clave débil), round-trip de cifrado del apodo, lectura acotada al padre vía
  `matriculas_visibles`, el CHECK de consentimiento (registrar hijo sin consentimiento → rechazo),
  `maquina-empezar` (reducer, `node --test`), `enviar-solicitud` (3 ramas), y la resolución de
  etiqueta `colegio·grado` del admin.
- **Red de regresión:** los 106 tests de Identidad verdes tras cada extracción; cualquier rojo =
  revertir. Suite completa del monorepo verde al cerrar cada fase.

---

## 7. Unidades y sus fronteras (diseño para aislamiento)

| Unidad | Qué hace | Cómo se usa | De qué depende |
|---|---|---|---|
| `dominio/sesiones.py` | hash/verify clave, emitir/leer token | funciones puras | stdlib |
| `dominio/autorizacion.py` | `puede`, `campos_visibles`, `Ambito` | funciones puras sobre datos ya buscados | stdlib |
| `dominio/cuenta.py` (nuevo) | validar creación de cuenta, decidir crear-vs-promover-vs-409 | recibe fila de usuario (o None), devuelve decisión tipada | stdlib |
| `repositorios/identidad.py` | todo el SQL de Identidad | construido con la conexión dentro de `motor.sesion()` | SQLAlchemy Core + modelos |
| `routers/identidad.py` | HTTP: parsear → llamar dominio → sobre de error | FastAPI | dominio + repositorios |
| `maquina-empezar.ts` (nuevo) | estado del flujo `/empezar` | `reducir(estado, accion)` | ninguna (puro) |
| `enviar-solicitud.ts` (nuevo) | elegir rama de envío + enviar | `enviar(estado)` → una de 3 rutas | api-navegador |

---

## 8. Riesgos y decisiones abiertas

- **Contraseña en el paso 1** puede subir la fricción del alta. Mitigado: es un solo paso, y el
  retornador entra directo por el toggle. (Decisión tomada por el usuario: cuentas reales desde el
  inicio.)
- **Promoción de invitado→credencial:** un correo que subió una lista antes (invitado
  `sin-credencial`) al crear cuenta se **promueve**, no se duplica. Cubierto por test.
- **`OTEL`/broker/saga** quedan para sus ADR (0020–0025); A no los toca, pero no cierra la puerta:
  el drenado del poller y los sobres de evento siguen como están.

---

## 9. Fuera de alcance (recordatorio)

Cambio de kit por el padre (`fijar_producto_en_linea`) · panel del padre (B) · revisar→pagar/Wompi y
seguimiento de despacho (C) · historial/medios de pago/preferencias (D) · broker/saga/observabilidad
(ADR-0020–0025). Cada uno es su propio ciclo spec → plan → código.
