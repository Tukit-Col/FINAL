# Consolidación del SRS en una línea base v4 — qué se aplicó, cómo se verificó y qué salió a flote

- **Tipo:** registro de aplicación. Documenta una operación ya ejecutada.
- **Fecha:** 2026-09-22.
- **Entrada:** `Arquitectura/SRS_ISIS2610G19_v3.docx`, **intacto**, conservado como historia.
- **Salida:** **`Arquitectura/SRS_ISIS2610G19_v4.docx`**, con copia idéntica en
  `ENTREGA_FINAL/SRS/`.
- **Qué se aplicó:** los 28 cambios de `Arquitectura/ENMIENDA_SRS.md` (E-01 a E-28) y los 12 de
  `tukit/docs/ADENDA_REQUISITOS_SRS.md` (E-29 a E-40). **Cuarenta cambios**, ejecutados como 70
  operaciones sobre el documento.
- **Por qué:** hasta hoy había que leer tres documentos juntos para saber cuál era el requisito
  vigente. Para un documento calificable eso es insostenible, y para los dos agentes que están
  construyendo contra él, peor: un requisito que hay que reconstruir mentalmente a partir de tres
  archivos no es una especificación, es un acertijo.

---

## 0. El resultado, en cifras verificadas

| | v3.0 | v4.0 |
|---|---:|---:|
| Requisitos declarados en tablas de requisitos | 99 | **131** |
| Filas del Anexo C (matriz de trazabilidad) | 76 | **131** |
| Requisitos declarados **sin** fila en el Anexo C | 25 | **0** |
| Filas del Anexo C **sin** requisito declarado | 2 (`DP-03`, `DP-04`) | **0** |
| Tablas | 32 | 40 |
| Requisitos sin columna de prioridad | 23 | **0** |
| Apariciones de `ePayco` | 4 | **0** |
| Requisitos de aplicación móvil nativa | 3 | **0** |

La correspondencia **131 ↔ 131 exacta y sin duplicados** entre las tablas de §3 y el Anexo C es la
comprobación más útil de todas, porque el criterio "Trazable" que §5.1 del propio SRS declara
verificado depende de ella, y en el v3 era falso en las dos direcciones a la vez.

El conteo MoSCoW del v4 es **89 Must, 26 Should, 3 Could, 13 Won't (v1)**, que suma 131. Coincide
con la predicción que `ADENDA_REQUISITOS_SRS.md` §10.4 había hecho antes de aplicar nada —120 + 11,
con siete Must y cuatro Should nuevos—, lo cual es una comprobación cruzada que no estaba buscada y
que conviene registrar: el conteo salió de dos derivaciones independientes.

---

## 1. Cómo se verificó que el `.docx` no se rompió

El encargo pedía intentar la manipulación programática de verdad y decir si resultaba insegura para
el formato. **Resultó segura**, y la razón es una decisión de método que conviene dejar escrita
porque es lo que separa un `.docx` intacto de uno roto.

**Regla que se siguió: nunca se creó XML desde cero para algo que ya existía en el documento.**
Cada bloque nuevo es una **copia profunda** de un bloque existente del mismo tipo —una fila de
tabla de requisitos, un párrafo de lista, un pie de tabla— con el texto reemplazado. Así el estilo,
los bordes de celda, el ancho de columna, la fuente y la numeración vienen del original y no de una
reconstrucción nuestra, que es exactamente donde el formato se rompe. Las cinco primitivas
(`set_text`, `clone_para_after`, `clone_row_after`, `clone_table_after`, `remove_block`) se
probaron una por una en una prueba de humo antes de tocar nada.

### 1.1 Integridad del paquete

| Comprobación | Resultado |
|---|---|
| El `.zip` no tiene errores de CRC | ✅ |
| Las 18 partes del v3 están todas en el v4, sin partes nuevas ni perdidas | ✅ |
| Todos los `.xml` y `.rels` parsean | ✅ |
| `word/media/image1.png` e `image2.png` **byte a byte** iguales | ✅ |
| `word/styles.xml` **byte a byte** intacto | ✅ |
| `word/numbering.xml` **byte a byte** intacto | ✅ |
| `word/theme/theme1.xml`, `fontTable.xml`, `header1.xml`, `footer1.xml` intactos | ✅ |

Que `styles.xml` y `numbering.xml` estén **byte a byte** idénticos es la prueba más fuerte de que
el formato se conservó: significa que no se inventó ni un estilo ni una lista, y que todo lo nuevo
reutiliza las definiciones del original.

### 1.2 Estructura y formato

| Comprobación | Resultado |
|---|---|
| Estilos de tabla | 40 de 40 en `Normal Table`, igual que el v3 |
| Estilos de párrafo | los mismos siete del v3: `Normal`, `List Paragraph`, `Body Text`, `toc 1`, `toc 3`, `Heading 3`, `Heading 4`. **Ninguno nuevo** |
| Tablas de requisitos | 22 tablas de 8 columnas, todas con la misma cabecera |
| Campo `TOC` del índice | presente e intacto |
| Entradas del índice | 61, intactas |
| Encabezados `Heading` | 58 |
| Pies de tabla | 30, numerados consecutivamente de 1 a 30 |
| Apertura por un lector independiente | ✅ `textutil` de macOS lo convierte completo (2.825 líneas), con las viñetas y las tablas |

### 1.3 Lo único que queda desactualizado, y por qué es correcto que quede así

**El índice de contenido conserva los números de página del v3 hasta que se abra en Word.** Es un
campo `TOC \o "1-4" \h \z \u` con un `PAGEREF` por entrada, y recalcular números de página exige un
motor de composición que ninguna biblioteca de Python tiene. Tocar el texto almacenado del índice
sería peor: son párrafos con hipervínculos y campos dentro, y reescribirlos los destruye —de hecho
ocurrió en una pasada intermedia, cuando una búsqueda por `startswith` encontró la entrada del
índice antes que el encabezado real y le escribió encima; se detectó en la verificación y se
corrigió excluyendo los estilos `toc` de toda búsqueda—.

La solución correcta es la que se aplicó: **`<w:updateFields w:val="true"/>` en `word/settings.xml`**,
que le pide a Word recalcular los campos al abrir el documento. Word mostrará el aviso habitual de
actualizar campos y el índice quedará correcto. Es la práctica estándar y no una limitación
disimulada; conviene saberlo para no alarmarse al abrirlo.

Un lector que **no** ejecute campos —`textutil`, una vista previa rápida, un visor web— verá el
índice del v3. El cuerpo del documento está bien en todos los casos.

---

## 2. Los 40 cambios, uno por uno

**67 operaciones limpias, 2 que exigieron criterio, 1 no aplicada.** "Limpio" significa que el
reemplazo era mecánico y se verificó después; "criterio" significa que la enmienda dejaba una
decisión abierta y hubo que tomarla, y aquí está dicha; "no aplicada" significa que exige una
decisión del equipo o una medición que este trabajo no puede producir.

### 2.1 Lo que exigió criterio

**`DP-04`, el umbral de velocidad de la percepción (E-18).** La enmienda dice que su valor *"no
tiene valor en ninguna parte del documento y hay que fijarlo, midiéndolo primero sobre el corpus
del Agustiniano en lugar de inventarlo"*. **Criterio aplicado: se enunció el requisito con su
método de verificación y se dejó el umbral sujeto a medición**, acotado superiormente por `OP-03`,
que limita el flujo completo a cinco minutos. El texto dice literalmente que *"el valor de
aceptación se fija por medición sobre el corpus del Agustiniano antes de cerrar la Fase 3"*. La
alternativa era inventar una cifra, y un umbral de desempeño fijado sin medir es una cifra que la
primera prueba desmiente. Queda como la única cifra pendiente del documento.

**`E-21`, la norma citada que no se ha podido corroborar.** La enmienda daba dos salidas y exigía
tomar una: corroborar la Resolución 17821 de 2023 en fuente pública, o reformular la restricción
sobre la Ley 1340 de 2009. **Criterio aplicado: se conservó la restricción de fondo —el sistema no
puede exigir marcas— y se marcó la referencia normativa como pendiente de corroboración, nombrando
la Ley 1340 de 2009 como la alternativa verificable.** No se puede corroborar una norma sin acceso
a la fuente oficial, y afirmarla sin verificar es precisamente el defecto que E-21 levanta: el
documento ahora dice que la referencia está pendiente en vez de afirmar una norma que el propio
equipo no ha encontrado. Es menos cómodo y es más honesto.

### 2.2 Lo que no se aplicó

**`E-17`, completar la Tabla 4 de distribución de requerimientos.** Se aplicó su mitad de
redacción: la referencia falsa a *"§3.16-3.17"* está corregida y el marcador de sincronización que
declaraba la tabla incompleta está retirado. Lo que **no** se aplicó es completar las columnas de
los módulos que faltan, porque exige decidir **qué función del producto implementa cada módulo
nuevo**, y eso es contenido, no redacción. La propia enmienda lo declara: *"este documento no puede
producirlo sin decidir qué función del producto implementa cada módulo nuevo, que es una decisión
del equipo"*. Es el único cambio abierto de los cuarenta.

### 2.3 Los cambios más invasivos, y qué se hizo con ellos

**E-05.d, tabular §3.10 a §3.12.** Es el cambio de mayor riesgo para el formato y el de más valor:
23 requisitos vivían en listas con viñetas, **sin columna de prioridad**, y entre ellos estaban
*todas* las obligaciones legales del sistema. Se crearon **nueve tablas nuevas** —una por
subsección— clonando la tabla de requisitos de §3.1, de modo que heredan sus ocho columnas, sus
anchos y sus bordes. La `Descripción` de cada requisito es su texto normativo anterior, literal
salvo el prefijo del código; la `Razón` se tomó de la justificación de `MOSCOW_REQUISITOS.md`
§2.10–§2.17; y el `Criterio de aceptación` se extrajo del propio texto cuando lo contenía.

Dos requisitos **no tenían criterio de aceptación** y la tabulación lo hizo visible, tal como E-05.d
anticipaba: **`PT-01` y `BD-01`**. Se les redactó uno, y las dos celdas lo dicen expresamente
—*"Criterio redactado en esta versión: el requisito no tenía ninguno"*— para que no parezca que
siempre estuvo ahí.

**E-05.a, sustituir `Prior.` por `MoSCoW`.** Afectó a las 22 tablas de requisitos: se renombró la
cabecera y se mapearon los valores de `Alta`/`Media`/`Baja` a `Must`/`Should`/`Could`/`Won't (v1)`,
requisito por requisito, con el mapa de `MOSCOW_REQUISITOS.md`. Cero valores quedaron sin mapear. El
argumento de E-05.a se comprobó al hacerlo: de los 76 requisitos que la columna antigua tabulaba,
66 estaban en `Alta` y ninguno en `Baja`, así que no ordenaba el trabajo.

**E-01.d, retirar el Módulo 9.** Se eliminó la tabla de `AM-01`/`AM-03`/`AM-04` y su pie, se
sustituyó el encabezado por *"3.13 (retirada) — Aplicación Móvil Nativa"* y el cuerpo por la nota de
trazabilidad que E-01.d exige, incluida la advertencia de que `AM-04` **revive** si el artefacto de
Capacitor llega a publicarse en tienda. Los tres códigos siguen apareciendo en el documento
**exactamente tres veces**: en esa nota y en las dos filas del historial. Eso es lo correcto: un
retiro que no se nombra es indistinguible de un requisito perdido, que es el defecto de E-24.

---

## 3. Lo que la consolidación sacó a flote

Esto es lo que el encargo anticipaba, y ocurrió. Cinco cosas que no se veían porque vivían en
documentos distintos.

**1. La nota de cabecera de §3.8 conservaba `PSE/ePayco`.** E-02 nombra §3.8 entre las secciones
afectadas, pero sus subcambios solo tocan `FU-03`. La nota introductoria del módulo —que es una
tabla de una celda, no un párrafo— decía *"pago real a través de PSE/ePayco"* y además *"los
operadores de última milla (Módulo 10)"*, con la numeración vieja. **Dos cambios se cruzaban en un
texto que ninguno de los dos nombraba.** Lo encontró la verificación, no la lectura.

**2. La marca `v14` sobrevivía en tres sitios que ningún cambio nombraba.** E-15 retira la marca de
`Profesor`, `Rector` y `Editorial` en la tabla de actores; `Proveedor (v14)` no estaba en su lista.
Y el Anexo C tenía cinco celdas con `v14 (pendiente)` en la columna de fase de verificación, que
E-05 declara eliminada pero ningún cambio toca. La marca que el documento dice haber retirado
sobrevivía en seis celdas.

**3. `n≥20` sobrevivía dentro de una tabla.** E-19 corrige la base de evidencia en §1.1 y §5.3, que
son prosa. La Tabla 19, de fases del proceso de ingeniería de requisitos, tenía la misma cifra en
una celda. Un cambio expresado por secciones no alcanza a lo que está en tablas, y este documento
tiene el 60 % de su contenido en tablas.

**4. `SG-05` quedó con una solución de compromiso, y solo se nota al tabular.** No hay cambio
numerado para `SG-05`, pero `MOSCOW_REQUISITOS.md` §2.13 dice que es `Should` *"y debe partirse"*,
porque no distingue entre el personal interno —para quien el segundo factor es indispensable— y el
acudiente —para quien es fricción sobre un flujo anual—. Al tabular §3.11.3 hubo que escribir **una
sola celda de prioridad**, y la distinción acabó dentro de la descripción en vez de en dos
requisitos. Funciona y no es lo que el insumo pide: el faltante `RF-13` del catálogo es
exactamente partirlo, y sigue pendiente. Antes de consolidar, esta tensión no tenía dónde
manifestarse.

**5. `OP-03` y `NR-07` ahora se contradicen dentro del mismo documento.** `OP-03` acota el flujo en
cinco minutos; `NR-07` crea un camino corto que debería medirse en segundos. Mientras `NR-07` vivía
en la adenda, la tensión era entre dos archivos y era fácil no verla. Ahora los dos están en §3 del
mismo documento, a pocas páginas uno del otro, y un lector atento pregunta cuál de las dos
estimaciones se le anuncia al acudiente. Hay que decidir si `OP-03` se parte en dos criterios por
camino o si la estimación pasa a depender del camino resuelto; lo segundo es más barato y no toca
el requisito.

**Y una que la consolidación resolvió sin proponérselo.** Al contar identificadores para verificar,
apareció que el v3 tenía **101 identificadores y 99 requisitos**, y que los dos de diferencia eran
`DP-03` y `DP-04`, presentes **solo** en el Anexo C. Es literalmente lo que E-18 reporta, obtenido
por un camino independiente. En el v4 los dos existen en §3.9 con su texto y su criterio.

---

## 4. Riesgo que hay que conocer antes de usar el v4

**Hay dos citas del contrato que contra el v4 pasan la comprobación automática y son falsas.** Es
el efecto secundario de crear los requisitos que las citas presuponían:

- `CONTRATO_API.md` cita **`FU-06`** para el congelamiento de precio. En el v4 `FU-06` existe y
  trata de **la confirmación del pago por notificación idempotente**. El congelamiento es `FU-08`.
- El contrato y siete sitios de `apps/admin` citan **`AD-04`** para validar una línea. En el v4
  `AD-04` existe y es **la consola de comparación de tres paneles**. Validar una línea es `AD-02`.

Antes de consolidar, un barrido de códigos inexistentes las detectaba. Ahora no. Están las dos
como las primeras entradas de `tukit/docs/CORRECCIONES_TRAZABILIDAD.md` §1, y son lo primero que
hay que aplicar cuando el agente de backend libere el contrato.

El mismo barrido, ejecutado contra el v4, imprime exactamente tres códigos: `AD-25`, `AD-26` y
`AD-33`, que son los únicos de los ocho originales que no tenían ningún requisito detrás. Cuando se
apliquen C-12 y C-13, sale vacío.

---

## 5. Qué queda por hacer sobre el v4

| Qué | Dónde está documentado | Bloqueado por |
|---|---|---|
| ~~Completar la Tabla 4 de distribución (E-17)~~ | **CERRADO en el v5**, ver `CIERRE_V5.md` §3 | — |
| ~~Fijar el umbral de `DP-04`~~ | **CERRADO en el v5**, ver `CIERRE_V5.md` §1 | — |
| ~~Corroborar la referencia normativa de §2.4.1 (E-21)~~ | **CERRADO en el v5**, ver `CIERRE_V5.md` §2 | — |
| Paquete de trabajo en la WBS para los seis requisitos editoriales de v1 | `tukit/docs/REQUISITOS_DIFERIDOS.md` | Decisión de alcance y calendario |
| Partir `SG-05` en dos requisitos (faltante `RF-13`) | §3 de este documento | Nada; es redacción |
| Resolver la doble estimación de tiempo de `OP-03` y `NR-07` | §3 de este documento | Decisión de diseño, barata |
| Aceptar formalmente los ADR 0012, 0013 y 0014 | `CORRECCIONES_TRAZABILIDAD.md` §7.5 | Nada; es un cambio de una línea en cada archivo |
| Registrar en `ANEXO_M_DATOS_PERSONALES.md` el artefacto de `PE-07` y los plazos de retención nuevos | `ADENDA_REQUISITOS_SRS.md` E-33 | Nada |
| Actualizar el conteo de `MOSCOW_REQUISITOS.md` a 131 | `REQUISITOS_DIFERIDOS.md` §5 | Nada |
| Regenerar el índice abriendo el v4 en Word | §1.3 de este documento | Nada; Word lo ofrece al abrir |

---

## 6. Lo que no verifiqué

- **Que el v4 se vea bien en Word.** Verifiqué la integridad del paquete, que los estilos y la
  numeración están byte a byte intactos, que todo el XML parsea y que un lector independiente lo
  abre completo. **No lo he abierto en Word**, que es lo único que puede confirmar la paginación,
  los saltos de página dentro de las tablas nuevas y el resultado del índice regenerado. Las nueve
  tablas nuevas de §3.10–§3.12 son largas y conviene revisar a ojo si alguna rompe mal de página.
- **Las celdas del Anexo C, una por una.** Verifiqué la correspondencia 131 ↔ 131 por
  identificador. No verifiqué que la función `F1` a `F11` y el método de verificación de cada una de
  las 55 filas nuevas sean los más adecuados; los asigné por criterio y son revisables.
- **Que la `Razón` de los 23 requisitos tabulados diga lo que su autor original quería decir.** La
  tomé de la justificación MoSCoW, que es de otro documento y de otro propósito. Es coherente y no
  es lo mismo que una razón escrita por quien redactó el requisito.
- **El efecto sobre `ATAM_Tukit.tex` y el SAD.** `CF-02a`, `CF-02b`, `DP-02` y `DP-05` son
  escenarios del árbol de utilidad, y `NR-07` introduce un escenario de rendimiento con dos caminos
  de latencia muy distintos. No he tocado esos documentos.
