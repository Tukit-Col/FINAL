# Correcciones de trazabilidad — códigos de requisito mal citados

- **Tipo:** corrección de trazabilidad. **Este documento no edita nada.** Produce las
  correcciones para que otra persona las aplique.
- **Fecha:** 2026-09-22. **Revisión 3**, tras cerrar los tres cambios abiertos.
- **Línea base normativa:** **`Arquitectura/SRS_ISIS2610G19_v5.docx`**, que incorpora los 28
  cambios de `ENMIENDA_SRS.md`, los 12 de `ADENDA_REQUISITOS_SRS.md` y el cierre de los tres que
  el v4 dejó abiertos (`tukit/docs/CIERRE_V5.md`). El PDF `v2` de la raíz y los `.docx` `v3` y
  `v4` son historia y no se citan como fuente de requisitos.
- **Qué cambió en la revisión 2.** La primera versión traía **dos** columnas de destino, una para
  la línea base vigente y otra para después de aplicar las enmiendas, porque en ese momento había
  tres documentos que había que leer juntos. Ya no: **hay un solo destino** y la tabla está
  simplificada. Se añadieron además las dos correcciones que el encargo pidió explícitamente
  —`AD-01` y la cita falsa de `OP-03`—.
- **Qué cambió en la revisión 3.** Solo la línea base a la que apuntan las correcciones: v4 → v5.
  **Ninguna corrección de esta tabla cambió de destino**, porque el v5 no renumeró ni redefinió
  ningún requisito: cerró `DP-04`, corrigió la norma de §2.4.1, completó la Tabla 4 y arregló dos
  defectos de aplicación del v4. `OP-03` **no** se tocó, de modo que C-02 sigue vigente tal cual.

> **Sobre las menciones a «el v4» en el cuerpo de esta tabla.** Se conservan a propósito y son
> correctas. Cuando una fila dice *"en el v4, `FU-06` existe y significa otra cosa"*, está fechando
> **cuándo nació** ese código, que es el dato que hace falta para entender por qué la cita parece
> correcta. Todo lo que el v4 creó sigue existiendo igual en el v5; no hay que leer «v4» como «línea
> base vigente» sino como «desde esa versión».

> **Cómo se ancla cada corrección.** `tukit/arquitectura/CONTRATO_API.md` lo está extendiendo
> otro agente, así que **los números de línea se mueven**. Cada fila trae por eso la sección y el
> **texto citado literal**, que es lo que permite encontrar el sitio cuando la línea ya no
> coincida. Si el texto citado desapareció, la corrección hay que re-evaluarla y no aplicarla a
> ciegas.

> **Re-validado contra la v1.1 del contrato, a las 12:25 del 2026-09-22.** El agente de backend
> cerró la v1.1 mientras se escribía esto, y sirvió de prueba del anclaje: **los seis textos
> citados que sostienen las correcciones del contrato siguen presentes, palabra por palabra**, y
> las nueve citas de código siguen siendo las mismas. Lo que cambió son los **números de línea**,
> que se corrieron unas 42 posiciones: `GET /v1/admin/cola` pasó de la 441 a la **483**. Los
> números de esta tabla son los de la v1.0 y se conservan por trazabilidad; **guiarse por el texto
> citado, no por la línea.**
>
> Dos comprobaciones concretas sobre la v1.1: **`AD-01` sigue sin aparecer ni una vez**, así que
> C-03 sigue vigente entero; y `GET /v1/admin/cola` aparece ahora **dos** veces, pero la segunda
> (línea 1155) es una tabla de resumen sin códigos de requisito, de modo que **la corrección sigue
> teniendo un solo sitio de aplicación**.

---

## 0. Resumen para quien va a aplicar esto

**Ocho códigos confirmados inexistentes en el v2 y en el v3, cuatro reclasificados como reales, y
tres defectos que el encargo no pedía. Con el v4 aplicado, siete de los ocho pasan a existir.**

| | Cuántos | Cuáles |
|---|---:|---|
| Inexistentes en el v2 y en el v3 | **8** | `AD-04`, `AD-05`, `AD-06`, `AD-07`, `AD-25`, `AD-26`, `AD-33`, `FU-06` |
| De esos ocho, **ya existen en el v4** y la cita queda correcta o casi | **5** | `AD-04`, `AD-05`, `AD-06`, `AD-07`, `FU-06` — pero `AD-04` y `FU-06` existen con **otro significado** del que la cita les da, y hay que corregirlos igual |
| De esos ocho, **siguen sin existir** y hay que remapear a un requisito real | **3** | `AD-25`, `AD-26`, `AD-33` |
| Reales ya en el v3, marcados falsos por error del análisis previo | **4** | `FU-04`, `PR-08`, `UM-03`, `AM-01` — y `AM-01` **se retira** en el v4 |
| Defectos nuevos, no pedidos | **3** | `AD-01` no se cita en ninguna parte (§1.3); la cola trazada a `AD-02` en vez de a `AD-01` (§1.3); una cita textual de `OP-03` que ninguna versión del SRS contiene (§1.2) |

**El efecto de la consolidación sobre esta tabla es grande y conviene verlo antes de aplicar
nada:** de 46 correcciones, **19 dejan de ser necesarias** porque el v4 creó el requisito que la
cita presuponía. Lo que queda son 27, y de ellas las dos peligrosas son `FU-06` y `AD-04`: **las
dos van a parecer correctas** contra el v4 y no lo son, porque el código existe con otro
significado. Esas dos primero.

**Ámbitos afectados y quién los puede tocar:**

| Ámbito | Sitios | ¿Se puede editar hoy? |
|---|---:|---|
| `tukit/arquitectura/CONTRATO_API.md` | 14 | **No.** Lo posee el agente de backend |
| `tukit/apps/admin/**` y `tukit/libs/ts/tukit-contrato/**` | 34 sitios en 17 archivos | **No.** Lo posee el agente de frontend |
| `.cursor/plans/pipeline_end-to-end_monorepo_4a4ee99a.plan.md` | 11 | Sí |
| `Arquitectura/ARQUITECTURA.md` | 1 | Sí |
| `tukit/docs/FLUJO_EXTREMO_A_EXTREMO.md` | 5 | Sí |

---

## 1. Las cuatro correcciones que hay que hacer primero

### 1.1 C-01 — `FU-06` existe en el v4 con otro significado. Es la más urgente de todas

| | |
|---|---|
| **Archivo** | `tukit/arquitectura/CONTRATO_API.md` |
| **Sección** | §5.1.1 *Líneas informativas* y §9 *Pago*, invariante 2 |
| **Línea (v1.0)** | 387 y 496 |
| **Texto citado** | *"`FU-06` congela el precio al confirmar, así que una línea que Tukit no controla no puede entrar al total."* — y — *"**El precio no se mueve después de confirmar** (`FU-06`)."* |
| **Código actual** | `FU-06` |
| **Código correcto** | **`FU-08`** |
| **Justificación** | En el v4, `FU-06` existe y dice *"La confirmación del pago se resuelve por notificación entrante idempotente"*. El congelamiento de precio es **`FU-08`**: *"El precio se congela en la reserva y se revalida al confirmar"*. La cita no está vacía: apunta a un requisito real que trata de otra cosa. **Por eso es la más urgente:** contra el v4 la cita pasa la comprobación automática de códigos inexistentes, de modo que nadie la volverá a mirar, y el error queda instalado en la ruta del dinero. Corrección: sustituir `FU-06` por `FU-08` en los dos sitios |

### 1.2 C-02 — Una cita textual que ninguna versión del SRS contiene, y que dice lo contrario

| | |
|---|---|
| **Archivo** | `tukit/arquitectura/CONTRATO_API.md` |
| **Sección** | §0 *Por qué la API es asíncrona*, primer párrafo |
| **Línea (v1.0)** | 17–19 |
| **Texto citado** | *"`OP-03` del SRS dice que el sistema 'debe priorizar la precisión del emparejamiento y la mejor relación calidad-precio del kit **por encima de la velocidad de generación**'"* |
| **Código actual** | `OP-03` — el código es correcto, **la cita no** |
| **Código correcto** | `OP-03`, con su texto real |
| **Justificación** | Se buscaron "por encima de la velocidad", "velocidad de generación" y "priorizar la precisión" en el v2, en el v3 y en el v4: **no aparecen en ninguno**. El `OP-03` real del v4 dice *"El motor debe generar los 3 kits en un tiempo razonable que no afecte negativamente la experiencia del padre"*, con criterio *"Tope máximo de 5 minutos de extremo a extremo (peor caso), con progreso visible por etapa mientras dura el procesamiento"*. O sea que el contrato no solo inventa la cita: le atribuye al SRS **lo contrario** de lo que dice, porque el SRS **acota** el tiempo en vez de subordinarlo a la precisión. Es el defecto más fácil de verificar de esta lista —se comprueba abriendo el SRS— y el más caro si lo encuentra un jurado, porque una cita textual falsa no es un error de trazabilidad sino de método |
| **Reemplazo listo para pegar** | *"El pipeline tarda minutos, no segundos. `OP-03` del SRS lo acota en cinco minutos de extremo a extremo en el peor caso, y exige **progreso visible por etapa** mientras dura el procesamiento. Una API síncrona no puede ofrecer ese progreso, y por eso el recurso central no es el kit sino el trabajo."* Dice lo que el contrato necesita decir en ese punto y es cierto |

### 1.3 C-03 — `AD-01` no se cita en ningún sitio, y la cola está trazada a otro requisito

Es el defecto que el encargo pidió arreglar, y tiene dos mitades.

**Primera mitad: el trazado equivocado.**

| | |
|---|---|
| **Archivo** | `tukit/arquitectura/CONTRATO_API.md` |
| **Sección** | §7 *Revisión humana*, tabla de endpoints, primera fila |
| **Línea (v1.0)** | 441 |
| **Texto citado** | `` | `GET /v1/admin/cola` | `AD-02`, `AD-03` | `` |
| **Código actual** | `AD-02`, `AD-03` |
| **Código correcto** | **`AD-01`**, `AD-03`, y `PE-04` como lo que la alimenta |
| **Justificación** | `AD-01` es el único requisito del SRS que exige esta cola, y su texto en el v4 es literal: *"El Panel Admin debe mostrar los mapeos de útiles pendientes de validación: lista de origen, grado, e ítems con estado COINCIDENCIA_PARCIAL o SIN_COINCIDENCIA"*. `AD-02` es la **corrección** del mapeo, que es lo que pasa *después* de leer la cola, y `AD-03` es la autenticación. La cola estaba trazada a todo menos al requisito que la pide |

**Segunda mitad: la ausencia.** `AD-01` **no aparecía ni una vez** en `CONTRATO_API.md`, ni en el
plan, ni en `tukit/apps/**`, ni en `tukit/libs/**` — verificado por búsqueda sobre los cuatro
ámbitos, que devolvía vacío. El requisito que manda construir la pantalla central del admin no
estaba citado en ningún sitio donde esa pantalla se diseña. Ninguna búsqueda de códigos
inexistentes lo encuentra, porque los dos códigos que ocupaban su lugar existen.

**Los seis sitios donde hay que introducir `AD-01`**, que son los que hoy nombran la cola:

| # | Archivo | Línea | Qué dice | Qué debe decir |
|---|---|---:|---|---|
| C-03.a | `CONTRATO_API.md` | 441 | `` `AD-02`, `AD-03` `` | `` `AD-01`, `AD-03` `` |
| C-03.b | plan, tarea de `apps/admin` | 93 | *"cola de revisión de los 3 kits (`AD-02`, `AD-03`, `PE-04`)"* | *"cola de revisión de los 3 kits (`AD-01`, `AD-03`, `PE-04`)"* |
| C-03.c | `apps/admin/src/app/page.tsx` | 1 | `` // `/` — la cola de revision (AD-02, AD-03). `` | `` // `/` — la cola de revision (AD-01, AD-03). `` |
| C-03.d | `apps/admin/src/components/CabeceraAdmin.tsx` | 18 | `AD-02 · AD-03 · AD-04 · AD-05 · AD-06 · AD-07` | **`AD-01 · AD-02 · AD-03 · AD-04 · AD-05 · AD-06 · AD-07`** |
| C-03.e | `apps/admin/src/app/layout.tsx` | 9 | *"(AD-02 a AD-07)"* | *"(AD-01 a AD-07)"* |
| C-03.f | `libs/ts/tukit-contrato/src/simulado/origen-simulado.ts` | 231 | *"que es lo que `AD-02` quiere priorizar"* | *"que es lo que `AD-01` quiere priorizar"* — priorizar la cola es de `AD-01` |

La cabecera del panel (C-03.d) es el sitio más visible del defecto: la pantalla enumera los
requisitos que implementa y omite el suyo.

### 1.4 C-04 — `AD-04` existe en el v4, pero significa la consola y no la acción por línea

| | |
|---|---|
| **Archivo** | `CONTRATO_API.md` §7 (líneas 443 y 444) y siete sitios de `apps/admin` y `libs` |
| **Texto citado** | `` | `POST …/lineas/{item_id}/validar` | `AD-04` | `` y `` | `POST …/lineas/{item_id}/sin-coincidencia` | `AD-04` | `` |
| **Código actual** | `AD-04` |
| **Código correcto** | **`AD-02`** |
| **Justificación** | En el v4, `AD-04` es la **consola de revisión con comparación de tres paneles**: la pantalla, no la acción. Validar una línea o marcarla sin coincidencia es `AD-02`, literal: *"seleccionar un producto diferente del catálogo o marcar el ítem como no disponible"*, con el criterio *"Cada corrección queda registrada con autor y marca de tiempo"* que cubre el motivo obligatorio del endpoint. Es la segunda cita que **parece** correcta contra el v4 y no lo es |

---

## 2. `tukit/arquitectura/CONTRATO_API.md` — las 10 correcciones restantes

Leído en la **v1.0** a las 11:20 del 2026-09-22. **No editar hasta que el agente de backend
cierre la v1.1.** Las cuatro de §1 ya están arriba y no se repiten.

| # | Sección / línea | Texto citado | Actual | Correcto | Justificación |
|---|---|---|---|---|---|
| C-05 | §0, 22–23 | *"los kits pasan por revisión de Admin Tukit (`AD-03`, `AD-04`) antes de llegar al acudiente (`AD-06`)"* | `AD-03`, `AD-04`, `AD-06` | `AD-01`, `AD-02`, `AD-03` para la revisión; **`AD-06`** para la publicación, que **ya es correcto** | La revisión son tres requisitos y ninguno es `AD-04` en el sentido que aquí se le da. `AD-06` sí queda correcto: en el v4 es el visto bueno que publica al acudiente |
| C-06 | §2, 138 | `// (a) El colegio ya publicó la lista: AD-06` | `AD-06` | **`CO-01`**, y añadir `NR-07` + `NR-08` | Aquí `AD-06` no significa lo que significa en §7. Aquí es "el colegio ya publicó la lista", que es `CO-01`. **Un código de administración no puede trazar una capacidad del colegio.** Y en el v4 una lista disponible para seleccionar puede venir de `CO-01` o de un artefacto reconstruido (`NR-07`), con `NR-08` obligando a distinguirlas ante el acudiente |
| C-07 | §4, 275 | *"esa es la razón de ser de `espera_revision` y de `AD-06`"* | `AD-06` | `AD-06` — **correcto** | En el v4, `AD-06` es exactamente la decisión que saca al trabajo del estado de espera humana. No cambiar |
| C-08 | §7, 442 | `` | `GET /v1/admin/trabajos/{id}` | `AD-03` | `` | `AD-03` | **`AD-04`** | `AD-03` es solo autenticación. El detalle de un trabajo en revisión es la consola de `AD-04` |
| C-09 | §7, 445 | `` | `POST /v1/admin/productos` | `AD-07` — alta manual con precio e imagen | `` | `AD-07` | `AD-07` — **correcto** | En el v4, `AD-07` es el alta manual de producto con sus tres fuentes. La cita queda correcta tal como está |
| C-10 | §7, 446 | `` | `POST /v1/admin/productos/{sku}/no-disponible` | `AD-05` | `` | `AD-05` | `AD-05` — **correcto**, con un matiz | En el v4, `AD-05` cubre las dos marcas. El endpoint solo implementa la de stock; falta el de "aún no provisto", cuyo alcance es por colegio y no global. No es una corrección de código sino una superficie que falta |
| C-11 | §7, 447 | `` | `POST /v1/admin/trabajos/{id}/revision` | `AD-06` — publica al acudiente | `` | `AD-06` | `AD-06` — **correcto** | Sin cambio |
| C-12 | §7, 451 | *"que es lo que `AD-25` y `AD-26` exigen"* | `AD-25`, `AD-26` | Criterio de `AD-02` + **`ML-06`** + **`SG-02`**, y ahora también el criterio de `AD-06` | Ni `AD-25` ni `AD-26` existieron nunca, ni existen en el v4, y los números son implausibles: administración llega a `AD-07`. La obligación de auditoría sí existe, repartida en tres sitios que cubren cosas distintas: `AD-02` exige el registro de la corrección, `ML-06` la trazabilidad del kit a sus ítems y `SG-02` el control de acceso que hace fiable el registro |
| C-13 | §9, 489 | `` | `GET /v1/ordenes/{id}` | `AD-33`, seguimiento | `` | `AD-33` | **`FU-01`** + **`UM-03`** | `AD-33` no existió nunca y sigue sin existir. El seguimiento está partido en dos: `FU-01` registra la orden y su historial consultable, y `UM-03` cubre los estados de entrega y su notificación al padre |
| C-14 | §9, 490 | `` | `POST /v1/ordenes/{id}/retracto` | `FU-04` | `` | `FU-04` | `FU-04` — **correcto** | `FU-04` existe desde el v3: retracto y reversión, Ley 1480 de 2011. El análisis previo lo marcó falso por leer el v2. **No cambiar nada** |

### 2.1 Dos notas del contrato que el v4 ya resolvió

| # | Sección / línea | Texto citado | Qué hacer |
|---|---|---|---|
| C-15 | §9, 504–508 | *"**Nota de trazabilidad:** `FU-03` dice hoy 'PSE y ePayco' y la implementación usa **Wompi**… El cambio va con ADR y con la actualización de `FU-03` en el SRS."* | **Sustituir la nota entera por una referencia.** En el v4, `FU-03` ya dice Wompi, la palabra `ePayco` no aparece en el documento, y `[D4]` ya dejó de ser bloqueante del Módulo 8. La nota describe un trabajo que está hecho |
| C-16 | §10, 520–521 | *"El SRS difiere a v2+ 'la integración con WhatsApp Business para notificaciones **proactivas** y no solo reactivas'"* | **Correcto, y es cita textual verificada** contra el v4 §2.7. Es la única cita textual del contrato que resistió la verificación palabra por palabra. Conviene además añadir `FU-10`, que es el requisito que en el v4 gobierna el puerto `Notificador`, y `FU-11`, que gobierna el número de solicitud en el enlace y la caducidad del aviso |

---

## 3. El plan `pipeline_end-to-end_monorepo_4a4ee99a.plan.md` — 11 correcciones

Ruta completa: `/Users/mariapaula.rodriguez/.cursor/plans/pipeline_end-to-end_monorepo_4a4ee99a.plan.md`.
Editable hoy.

| # | Línea | Texto citado | Actual | Correcto | Justificación |
|---|---:|---|---|---|---|
| P-01 | 90 | *"elegir colegio y grado (lista oficial precargada, `AD-06`)"* | `AD-06` | **`CO-01`** + `NR-07` + `NR-08` | Mismo error que C-06: la lista precargada la publica el colegio. Y en el v4 la mitad del valor de esa entrada es que la lista pudo reconstruirse de un PDF validado (`NR-07`), con `NR-08` obligando a decirle al padre de dónde vino |
| P-02 | 93 | *"cola de revisión de los 3 kits (`AD-02`, `AD-03`, `PE-04`)"* | falta `AD-01` | **`AD-01`**, `AD-03`, `PE-04` | Ver C-03.b |
| P-03 | 93 | *"validar o marcar sin coincidencia (`AD-04`)"* | `AD-04` | **`AD-02`** | Ver C-04 |
| P-04 | 93 | *"edición manual de precio/imagen/producto **para libros** (`AD-07`)"* | `AD-07` | `AD-07` — correcto, **corregir el alcance** | El código queda bien. Lo que está mal es *"para libros"*: `AD-07` cubre **útiles y libros**, porque `descubrir.py` tiene los dos caminos (`--crear-util` y `--crear-libro`) |
| P-05 | 93 | *"marcar no disponible o no provisto para uniformes (`AD-05`)"* | `AD-05` | `AD-05` — **correcto** | El plan ya nombraba las dos marcas por separado, lo que confirma que `AD-05` recoge una intención que existía y no tenía requisito |
| P-06 | 93 | *"y publicar al papá (`AD-06`)"* | `AD-06` | `AD-06` — **correcto** | Sin cambio |
| P-07 | 102 | *"facturación electrónica DIAN vía Siigo — hueco del SRS, no existe requisito para el padre (solo `PR-08` del proveedor); **levantar requisito nuevo antes de implementar**"* | `PR-08` | **`FU-09`** + **`[D5]`** | **El plan tenía razón y el análisis previo lo desmintió por error:** `PR-08` existe desde el v3 y es del proveedor. Lo que hay que corregir no es la cita sino la **conclusión**: en el v4 el requisito ya está levantado como `FU-09`, con la dependencia `[D5]` que declara que la emisión válida exige NIT y habilitación ante la DIAN. La instrucción "levantar requisito nuevo antes de implementar" está cumplida |
| P-08 | 105 | *"re-verificación de precio y disponibilidad antes de cerrar (`UI-05`, `SC-05`, `FU-06`)"* | `FU-06` | **`FU-08`** | Ver C-01 |
| P-09 | 368 | *"la app nativa (`AM-01` queda cubierta por la PWA en v1)"* | `AM-01` | **ADR 0009** y §3.13 del v4 | Doble hallazgo. `AM-01` **existía** en el v3 —el análisis previo lo marcó falso por leer el v2— y la afirmación del plan era **falsa en su contenido**, porque `AM-01` exigía publicación en App Store y Google Play, que una PWA no satisface. En el v4 el requisito **ya no existe**: E-01 retiró el Módulo 9 completo, y §3.13 quedó como nota de retiro con el ADR 0009 como respaldo. Citar el ADR y la sección retirada |
| P-10 | 229, 241 | *"`OP-01` y `UI-02` del SRS piden 'exactamente 3 kits diferenciados'… **recomendar uno es escalarizar el frente con los pesos de ese papá**"* | `OP-01`, `UI-02` | Correctos; **añadir `OP-07`** | Las dos citas son textuales y correctas. Lo que falta es el código de la recomendación: en el v4 existe `OP-07`, *"Recomendación de kit según el perfil"*, exactamente para esto. El plan describía una capacidad correcta sin citar el requisito que ahora la enuncia |
| P-11 | 281 | *"Correo con factura + link de seguimiento (`UM-03`)"* | `UM-03` | Partir: **`UM-03`** para el seguimiento, **`FU-09`** para la factura, **`FU-10`/`FU-11`** para el aviso | `UM-03` es correcto para el estado de entrega y no cubre la factura |

**Y un hallazgo de gobierno que el plan sigue arrastrando**, ahora más grande: el plan no menciona
`apps/colegio`, ni los diecinueve requisitos de proveedores y editorial, seis de los cuales el v4
**ya trajo a v1**. Están inventariados en `tukit/docs/REQUISITOS_DIFERIDOS.md`.

---

## 4. `Arquitectura/ARQUITECTURA.md` — 1 corrección, y un defecto abierto

Editable hoy. Es el **único** documento del barrido cuyas citas de código están casi todas bien,
lo que es coherente con ser el lock.

| # | Línea | Texto citado | Actual | Correcto | Justificación |
|---|---:|---|---|---|---|
| A-01 | 257 | *"Resuelve **RF-03** (RLS). Se denormaliza la clave de ámbito…"* | `RF-03` | **`MoSCoW RF-03`** | El código es real, pero no es del SRS: es un identificador del inventario de faltantes de `MOSCOW_REQUISITOS.md`, que usa `RF-02` a `RF-18`. El problema es la colisión: en las tablas del SRS `RF` es el **tipo** de requisito, frente a `RNF` y `RML`, así que un lector razonable lee `RF-03` como un requisito funcional del SRS y no lo encuentra. Basta calificarlo. Y conviene saber que `RF-03` sigue **bloqueado**: la Parte VI.A de la enmienda explica que no se puede redactar con criterio honesto hasta resolver dónde se evalúan las políticas de fila cuando el ancla de tenencia vive en otra base. El v4 **no** lo resuelve |

**Defecto abierto que no es de códigos y sigue sin corregir.** `ARQUITECTURA.md` §8.2 declara el
`subgraph clientes` del C4 nivel 2 con `web` y `adminapp` y omite `colegio`, mientras su propia §1
dice que son tres aplicaciones y que `apps/colegio/` está pendiente de portar. Es una
inconsistencia interna del documento que manda, y los diagramas de ese bloque son la fuente
versionada que se exporta al SAD y a la memoria, así que se propaga a documentos calificables. El
v4 la agrava un poco, porque `CO-05` añade una capacidad que vive en ese panel.

---

## 5. `tukit/apps/admin/**` y `tukit/libs/ts/tukit-contrato/**` — 34 sitios en 17 archivos

**No editar.** Lo posee el agente de frontend. **Esta es la sección que más se benefició de la
consolidación:** de 22 sitios que antes había que revisar, **quedan 9 ediciones reales**, porque el
v4 creó `AD-05`, `AD-06` y `AD-07` con el significado que el código ya les daba.

### 5.1 Los 9 sitios que hay que editar

| # | Archivo | Línea | Texto citado | Actual | Correcto |
|---|---|---:|---|---|---|
| F-01 | `apps/admin/src/lib/api-navegador.ts` | 55 | `/** AD-04. Sin `sku` se lee como "confirmo el producto que el sistema eligio". */` | `AD-04` | `AD-02` |
| F-02 | `apps/admin/src/lib/api-navegador.ts` | 64 | `/** AD-04. El motivo es obligatorio… */` | `AD-04` | `AD-02` |
| F-03 | `libs/ts/tukit-contrato/src/contrato.ts` | 340 | `// INFERIDO (AD-04): validar es fijar el producto de la linea.` | `AD-04` | `AD-02`, y quitar `INFERIDO`: ya no se infiere, está en el v4 |
| F-04 | `libs/ts/tukit-contrato/src/contrato.ts` | 347 | `// INFERIDO (AD-04): una marca de "sin coincidencia"…` | `AD-04` | `AD-02`, ídem |
| F-05 | `apps/admin/src/components/LineaRevision.tsx` | 3–4 | `// … para decidirla (AD-04, AD-05, AD-07).` | `AD-04` | `AD-02`. `AD-05` y `AD-07` quedan correctos |
| F-06 | `apps/admin/src/components/LineaRevision.tsx` | 350 | `{/* acciones AD-04 */}` | `AD-04` | `AD-02` |
| F-07 | `apps/admin/src/app/api/…/validar/route.ts` | 1 | `` // `POST …/validar` — AD-04. `` | `AD-04` | `AD-02` |
| F-08 | `apps/admin/src/app/api/…/sin-coincidencia/route.ts` | 1 | `` // `POST …/sin-coincidencia` — AD-04. `` | `AD-04` | `AD-02` |
| F-09 | `apps/admin/src/components/ConsolaRevision.tsx` | 4 | `// sus lineas (AD-03, AD-04).` | `AD-03`, `AD-04` | `AD-01` + `AD-04` para la consola y `AD-02` para las acciones sobre las líneas. Conviene partir la frase: es el **único** sitio donde `AD-04` queda correcto, porque el archivo **es** la consola |

Más los tres de `AD-01` ya listados en C-03.c, C-03.d y C-03.e, y el de C-03.f.

### 5.2 Los 13 sitios que quedan correctos contra el v4, sin editarse

Se listan para que nadie los "corrija" de más y para que quien aplique pueda verificar en lugar de
suponer.

| Archivo | Línea | Cita | Estado |
|---|---:|---|---|
| `apps/admin/src/lib/api-navegador.ts` | 73 | `/** AD-07. Alta manual con precio e imagen, sobre todo para libros. */` | ✅ Correcto. Quitar *"sobre todo para libros"*: `AD-07` cubre útiles y libros |
| `apps/admin/src/lib/api-navegador.ts` | 78 | `/** AD-05. Apaga la oferta en catalogo, o sea para todos los trabajos. */` | ✅ Correcto, y describe con exactitud la marca de stock. Le falta la segunda marca de `AD-05`, la de "aún no provisto", cuyo alcance es por colegio |
| `apps/admin/src/lib/api-navegador.ts` | 83 | `/** AD-06. Aprobar publica y avisa; devolver reabre en silencio. */` | ✅ Correcto, y describe literalmente las dos resoluciones de `AD-06` |
| `libs/ts/tukit-contrato/src/contrato.ts` | 313 | `// INFERIDO (AD-02/AD-03): la cola necesita…` | Añadir `AD-01` y quitar `INFERIDO` |
| `libs/ts/tukit-contrato/src/contrato.ts` | 330 | `// INFERIDO (AD-03): el detalle del trabajo en admin…` | `AD-04`, y quitar `INFERIDO` |
| `libs/ts/tukit-contrato/src/contrato.ts` | 353 | `// INFERIDO (AD-07): alta manual de producto…` | ✅ Correcto; quitar `INFERIDO` |
| `libs/ts/tukit-contrato/src/contrato.ts` | 374 | `// INFERIDO (AD-05).` | ✅ Correcto; quitar `INFERIDO` |
| `apps/admin/src/components/DecisionTrabajo.tsx` | 3 | `// AD-06 — la decision sobre el trabajo entero.` | ✅ Correcto |
| `apps/admin/src/components/AltaProducto.tsx` | 3, 121 | `// AD-07 — alta manual…` y `<h4>Alta manual del producto (AD-07)</h4>` | ✅ Correcto |
| `apps/admin/src/components/ConsolaRevision.tsx` | 30 | `hueco: "…Da de alta un producto (AD-07)…"` | ✅ Correcto |
| `apps/admin/src/app/api/productos/route.ts` | 1 | `// `POST /api/productos` — AD-07…` | ✅ Correcto |
| `apps/admin/src/app/api/productos/[sku]/no-disponible/route.ts` | 1 | `// `POST …/no-disponible` — AD-05.` | ✅ Correcto |
| `apps/admin/src/app/api/trabajos/[trabajo_id]/revision/route.ts` | 1 | `// `POST …/revision` — AD-06…` | ✅ Correcto |
| `apps/admin/src/components/Revision.module.css` | 437 | `/* Bajo el umbral tau del PE-04… */` | ✅ Correcto, y es la única cita de `PE-04` en todo `apps/**`. Conviene añadir `PE-07`, que es lo que hará que esa línea se pueda juzgar |
| `apps/admin/src/app/trabajos/[trabajo_id]/page.tsx` | 1 | `// `/trabajos/{id}` — el detalle y la revision (AD-03 a AD-07).` | Preciso: `AD-02` a `AD-07`, porque el rango incluye las acciones por línea |

La palabra `INFERIDO` que el agente de frontend puso en `contrato.ts` merece una nota, porque fue
buena práctica y **ya se puede retirar**: marcaba los sitios donde el tipo se dedujo de un
requisito en vez de copiarse de uno escrito. Con el v4, los cuatro requisitos que se inferían
existen con su texto, así que la marca deja de describir el estado del código. Retirarla es parte
de la corrección, no un detalle cosmético: dejarla sugiere que el contrato sigue adivinando.

---

## 6. `tukit/docs/FLUJO_EXTREMO_A_EXTREMO.md` — 5 correcciones al análisis previo

Editable hoy. Es el documento que fundamenta este encargo y acertó en lo esencial: los ocho
códigos inexistentes son reales como hallazgo, el diagnóstico del artefacto reutilizable es
correcto y su inventario de huecos se sostiene. Lo que falla es la línea base que leyó y tres
medidas del código.

| # | Sección | Texto citado | Corrección |
|---|---|---|---|
| L-01 | §0 hallazgo 1; §5.1 T1–T2; §3 hallazgo 4 | *"el contrato de la API cita nueve requisitos del SRS que no existen… El plan vigente agrega otros tres inexistentes: `PR-08`, `UM-03` y `AM-01`"* | Son **ocho** y no doce. `FU-04`, `PR-08`, `UM-03` y `AM-01` existían en el `.docx` v3, que era la línea base. El origen del error está declarado sin saberlo en su §8: enumeró los prefijos del **PDF v2** —donde no hay `PR`, `UM` ni `AM`— y lo dio por completo |
| L-02 | §3 hallazgo 4 | *"la palabra factura **no aparece en ninguna parte del SRS**, y `PR` no es un prefijo que el documento use"* | **El plan tenía razón.** `PR-08` existe, es del proveedor y habla de facturación. El hueco era del tamaño que el plan decía, y en el v4 está cerrado por `FU-09` con la dependencia `[D5]` |
| L-03 | §2.5; §5.3 hueco R5 | *"la **ventana** `vigente_hasta` es tarea pendiente del plan"* y 1,5 jornadas de esfuerzo | La columna **ya existe**: `servicios/catalogo/tukit_catalogo/modelos/oferta.py:174`, con la restricción `precio_vigencia_coherente`, el índice único parcial `uq_precio_vigente_por_oferta` y el comentario que documenta la restricción de exclusión de rangos. Lo que faltaba era la **política**, que el v4 fija en `SC-06`. El hueco es real y más pequeño de lo estimado |
| L-04 | §1, tabla de estado del código | *"**No hay ninguna API HTTP de dominio en todo `tukit/servicios/**`.**"* | Hoy existe `servicios/catalogo/tukit_catalogo/api.py`. Es obra del agente de backend y confirma la advertencia de concurrencia del propio documento |
| L-05 | §8 *Lo que no verifiqué* | *"El conteo por prefijo fue: `AD` 01–03, `BD` 01–05… `FU` 01–03, `LI` 02, `ML` 01–09…"* | Es el conteo del **v2**, 75 identificadores. El v3 tenía 101 y el v4 tiene 131 requisitos declarados. Conviene sustituirlo y no solo anotarlo, porque es la tabla de la que salieron los cuatro falsos positivos |

**Lo que el análisis previo acertó y conviene no tocar al corregirlo**: que `AD-01` a `AD-03` eran
todo lo que había en administración; que los ocho códigos restantes no existían; que el artefacto
reutilizable es la resolución validada de la lista y no el trabajo; que la frontera de
reutilización cae sobre las etapas del ADR 0018; que `revisada_en` sola no alcanza porque `CO-02`
exige una segunda firma; y que la persistencia del PDF y de la salida del modelo es prerrequisito
de la pantalla de comparación. Los seis diagnósticos se verificaron contra el código, se sostienen
y los seis están ahora en el v4 como requisitos.

---

## 7. Contradicciones entre el SRS, el lock, el contrato y el plan

Las cinco de la revisión anterior, actualizadas con lo que la consolidación resolvió y lo que no.

**1. El contrato le atribuye al SRS lo contrario de lo que dice sobre el tiempo. — ABIERTA.** Es
C-02, y merece figurar también aquí porque no es solo una cita mal copiada: el contrato construye
su argumento central —por qué la API es asíncrona— sobre la idea de que `OP-03` subordina la
velocidad a la precisión. El v4 hace lo opuesto, le pone un **tope de cinco minutos** y exige
progreso visible por etapa. La conclusión del contrato sigue siendo correcta, pero la premisa hay
que invertirla. Es la misma figura que el análisis previo encontró en el plan con `PR-08`:
conclusión buena, argumento falso.

**2. `OP-03` y `NR-07` no pueden convivir con una sola estimación de tiempo. — ABIERTA, y ahora
dentro de un solo documento.** `OP-03` acota en cinco minutos, el contrato §2 anuncia un
`estimado_segundos` único, y `NR-07` crea un camino corto que debería medirse en segundos. Antes
de consolidar, esta tensión vivía entre dos documentos y era fácil no verla; ahora `OP-03` y
`NR-07` están en el mismo §3 del mismo archivo y se leen seguidos. Hay que decidir si `OP-03` se
parte en dos criterios por camino o si la estimación pasa a depender del camino resuelto. Lo
segundo es más barato y no toca el requisito.

**3. `PE-07` y el régimen de datos de menores. — RESUELTA por decisión, con su caso de borde
escrito.** La revisión anterior la reportaba como tensión abierta: persistir la salida cruda de un
modelo que leyó una lista escolar parecía chocar con `PE-06` y `PV-03`. La decisión tomada es
persistir **en crudo**, y el argumento está sostenido en `ADENDA_REQUISITOS_SRS.md` E-33: la lista
de útiles es un inventario de productos por grado y su sujeto es el grado, que es un colectivo, no
una persona. La tensión no se resuelve relajando `PE-06` sino constatando que su objeto —el nombre
del menor— no está en el artefacto. Lo que queda escrito, y es la parte que hace la decisión
auditable, es el **caso residual**: el PDF que sube un acudiente puede traer el nombre impreso, y
ahí `PE-07` no depura el artefacto sino que **corta la propagación** hacia los cuatro destinos que
`PE-06` y `PV-03` protegen. Lo que sigue pendiente es la entrada en
`ANEXO_M_DATOS_PERSONALES.md`, que debe registrar el artefacto **aunque se declare no personal**,
porque un artefacto ausente del registro es indistinguible de uno que nadie clasificó.

**4. El plan planifica dos actores para una arquitectura de tres, y para un SRS que ahora exige
más. — ABIERTA y agravada.** `ARQUITECTURA.md` §1 declara tres aplicaciones; el plan nombra
`apps/web` y `apps/admin`. La consolidación lo agrava: el v4 trae a v1 seis requisitos editoriales
que operan sobre el Panel Colegio, y añade `CO-04` y `CO-05`. No es que falte una aplicación:
falta el actor que opera ocho requisitos de v1. Inventariado en `tukit/docs/REQUISITOS_DIFERIDOS.md`.

**5. Tres ADR en estado de propuesta sostienen la línea base consolidada. — ABIERTA y más urgente
que antes.** Los ADR 0012, 0013 y 0014 siguen en **propuesta**, y de ellos dependen ahora
requisitos **normativos del v4**: `CF-02a` y `CF-02b` (asimetría de recuperación, ADR 0012),
`CO-04` (matrícula como ancla, ADR 0013), `MT-03` y `BD-01` (fronteras y maestro único, ADR 0014),
`NR-07` y `NR-09`. Antes esto era una observación sobre una enmienda sin aplicar; ahora la línea
base **vigente** cuelga de tres decisiones que el registro dice que no se han tomado. Es un cambio
de una línea en cada archivo y elimina la pregunta entera.

**6. Nueva, y solo visible al consolidar: `SG-05` cambia de prioridad y de contenido a la vez.** La
enmienda no tiene un cambio numerado para `SG-05`, pero `MOSCOW_REQUISITOS.md` §2.13 dice que es
`Should` *"y debe partirse"*, porque no distingue entre el personal interno, para quien el segundo
factor es indispensable, y el acudiente, para quien es fricción sobre un flujo anual. Al tabular
§3.11.3 hubo que escribirle una sola celda de prioridad, y quedó `Should` con la distinción
metida en la descripción. **Eso es una solución de compromiso, no la partición que el insumo
pide.** El faltante `RF-13` del catálogo es justamente partirlo en dos requisitos, y sigue
pendiente. Se registra aquí porque es la clase de cosa que solo se ve cuando dos documentos se
funden en uno.

---

## 8. Orden de aplicación

1. **Hoy, sin esperar a nadie:** §3 (el plan, 11 correcciones), §4 (`ARQUITECTURA.md`, 1) y §6
   (`FLUJO_EXTREMO_A_EXTREMO.md`, 5). Son diecisiete correcciones sobre archivos que nadie más
   está tocando.
2. **Cuando el agente de backend cierre `CONTRATO_API.md` v1.1:** §1 y §2. Empezar por **C-01**
   (`FU-06` → `FU-08`) y **C-02** (la cita falsa de `OP-03`), que son las dos que no pueden
   esperar otra ronda, y seguir por **C-03.a** y **C-04**. Verificar antes que el texto citado
   siga existiendo: la v1.1 añade una superficie de lectura de catálogo y puede haber reescrito §5
   y §8.
3. **Cuando el agente de frontend cierre `apps/**`:** §5, que son nueve ediciones, cuatro
   inserciones de `AD-01` y catorce verificaciones.

### 8.1 Comprobación final

Con el v4 como línea base, ningún código citado en el monorepo debería faltar del SRS. La
comprobación es un barrido de códigos citados contra códigos definidos:

```bash
# codigos citados en la superficie compartida y en el codigo.
# --no-filename es obligatorio: sin el, cada linea sale como "archivo:CODIGO" y `comm` no compara nada.
rg -o --no-filename \
   '\b(AD|CO|FU|NR|OP|PE|SC|UI|UM|PR|AM|ED|PV|SG|ML|BD|CF|DI|DP|MT|PT|RD|PS|DE)-[0-9]{2}\b' \
   tukit/arquitectura/CONTRATO_API.md tukit/apps tukit/libs Arquitectura/ARQUITECTURA.md \
   | sort -u > /tmp/citados.txt

# codigos definidos en la linea base v4
textutil -convert txt -stdout Arquitectura/SRS_ISIS2610G19_v5.docx \
   | rg -o '\b[A-Z]{2}-[0-9]{2}\b' | sort -u > /tmp/definidos.txt

comm -23 /tmp/citados.txt /tmp/definidos.txt
```

La última línea imprime los códigos citados que el SRS no define. Contra el v3 imprimía **los
ocho** de §0. Ejecutada contra el v4, imprime exactamente **tres**:

```
AD-25
AD-26
AD-33
```

Y ese es el resultado correcto, no un residuo: son precisamente los tres códigos de §0 que **no
tenían ningún requisito detrás** y que por tanto la consolidación no podía crear. Corresponden a
C-12 (auditoría) y C-13 (seguimiento del pedido), cuyas intenciones sí tienen requisito —`AD-02`,
`ML-06`, `SG-02`, `FU-01` y `UM-03`— pero con otro número. **Cuando C-12 y C-13 se apliquen, el
barrido sale vacío.** Ese es el criterio de cierre de este documento.

Los otros cinco de §0 —`AD-04` a `AD-07` y `FU-06`— ya no aparecen, porque el v4 los creó. Y eso
es exactamente por lo que C-01 y C-04 son ahora las correcciones peligrosas: **este barrido ya no
las detecta**, porque el código existe. Lo que está mal es lo que significa.

Dos advertencias sobre el barrido. **No detecta `MoSCoW RF-03`** (A-01), porque `RF` está excluido
a propósito de la lista de prefijos: en las tablas del SRS es el *tipo* del requisito y no un
prefijo de identificador, así que incluirlo llenaría la salida de ruido. Y **no detecta las citas
mal dirigidas entre códigos que existen**, que son C-01, C-03, C-04, C-05, C-06, C-12, C-13 y
A-01: para esas no hay automatización posible, porque el error está en el significado y no en el
identificador. Son, justamente, las que se escaparon del análisis previo, y ahora son la mayoría
de lo que queda.
