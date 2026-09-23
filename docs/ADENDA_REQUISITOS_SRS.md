# Adenda de requisitos al SRS — revisión del admin, artefacto validado reutilizable, aviso y factura

> # ⚠ INCORPORADA — NO VOLVER A APLICAR
>
> **Estado: aplicada el 2026-09-22.** Los 12 cambios de este documento (E-29 a E-40) están
> **incorporados** a la línea base **`Arquitectura/SRS_ISIS2610G19_v5.docx`**, junto con los 28 de
> `Arquitectura/ENMIENDA_SRS.md` (E-01 a E-28).
>
> **Aplicarlos otra vez duplicaría los once requisitos nuevos.** Este documento queda como
> **registro del razonamiento**: es donde está argumentado *por qué* cada requisito dice lo que
> dice, que es lo que el `.docx` no puede contener. Para saber qué dice hoy un requisito, la fuente
> es el v4.
>
> - Los once requisitos nuevos —`AD-04` a `AD-07`, `PE-07`, `SC-06`, `NR-07` a `NR-09`, `CO-05` y
>   `FU-11`— y la dependencia `[D5]` están en el v4 con su fila en el Anexo C.
> - **`PE-07` cambió respecto de la primera redacción de este documento.** La usuaria decidió
>   persistir la salida del modelo **en crudo, sin depuración**. El requisito y su argumento están
>   reescritos en E-33, con el caso residual nombrado. Lo que el v4 contiene es la versión en
>   crudo.
> - **Resultado de la aplicación, cambio por cambio:** `tukit/docs/CONSOLIDACION_SRS_V4.md`, y el
>   cierre posterior en `tukit/docs/CIERRE_V5.md`.
> - **Siguen abiertas dos decisiones** de este documento. La primera: qué hace exactamente un texto
>   diferido cuando llega (E-37); se explica ahí por qué no se puede redactar sin una decisión de
>   negocio previa. La segunda apareció al consolidar: el choque de alcance entre `OP-03` y el
>   camino corto de `NR-07`, con tres redacciones alternativas en
>   `tukit/docs/DECISION_OP03_NR07.md`.

- **Tipo:** ingeniería de requisitos. No hay código de producción en este documento.
- **Fecha:** 2026-09-22. **Revisión 2**: `PE-07` reescrito en crudo; estado incorporado.
- **Qué es:** doce cambios al SRS, numerados **E-29 a E-40**, que continúan la numeración de
  `Arquitectura/ENMIENDA_SRS.md` y se aplican **después** de ella. Once son requisitos nuevos;
  el duodécimo es una dependencia.
- **Documento hermano:** `tukit/docs/CORRECCIONES_TRAZABILIDAD.md`, que corrige las citas de
  código de requisito en el contrato, el plan y el código. Los dos se escribieron juntos y se
  leen juntos: esta adenda crea los códigos que aquel necesita para poder corregir.
- **Fuentes de verdad consultadas, con su estado al leerlas:**
  - **`Arquitectura/SRS_ISIS2610G19_v3.docx`**, extraído completo (704 bloques, tablas
    incluidas) y enumerado código por código. **Es la línea base normativa**, no el PDF v2.
    Ver §1, que es la corrección más consecuente de este documento.
  - `Arquitectura/ENMIENDA_SRS.md`, 2.221 líneas, 28 cambios **E-01 a E-28**, sin aplicar.
  - `Arquitectura/MOSCOW_REQUISITOS.md` para los criterios de prioridad y el inventario de
    faltantes.
  - `Arquitectura/ARQUITECTURA.md` v1.0 (lock del 2026-09-21) §1, para el reparto por servicio.
  - `Memoria/PLAN_MEMORIA.md`, para el capítulo de destino de cada requisito.
  - `tukit/arquitectura/CONTRATO_API.md` **v1.0**, leído a las 11:20 del 2026-09-22.
  - `tukit/docs/FLUJO_EXTREMO_A_EXTREMO.md`, que fundamenta el encargo. Se le corrigen tres
    afirmaciones en §1.3.
  - El código real de `tukit/servicios/catalogo/**` y `tukit/servicios/inteligencia/**`.

> **Advertencia de concurrencia.** Hay dos agentes construyendo: uno sobre `servicios/**`,
> `infra/**` y `CONTRATO_API.md`; otro sobre `apps/**`. Este documento **no toca ninguno de
> esos archivos**. Las afirmaciones sobre el código valen para el árbol a las 11:20 del
> 2026-09-22 y están ancladas por nombre de símbolo además de por línea, porque la línea se
> mueve y el símbolo no.

---

## 0. Lo que hay que saber antes de leer el resto

**El SRS tiene fuente editable, y la línea base no es la que el análisis previo leyó.**
`Arquitectura/SRS_ISIS2610G19_v3.docx` existe, es Word, y hay una copia idéntica por suma de
verificación en `ENTREGA_FINAL/SRS/`. El PDF de la raíz es la **v2**, una versión anterior con
otro alcance. El v3 define **cinco prefijos más** que el v2 —`PR`, `UM`, `AM`, `ED` y `PV`— y eso
reclasifica cuatro de los doce códigos que el encargo daba por falsos. Es §1.

**Aun así, este documento no edita el `.docx`.** No por prudencia genérica, sino por una razón
concreta que §2 desarrolla: `ENMIENDA_SRS.md` ya produjo 28 cambios que **nadie ha aplicado
todavía**, y cinco de ellos añaden requisitos en las mismas secciones donde esta adenda añade
los suyos. Escribir en el documento ahora produciría un §3.8 con `FU-11` y sin `FU-06` a
`FU-10`. La adenda continúa la numeración de la enmienda y declara su dependencia.

**Dos de los seis encargos ya estaban redactados y no lo sabíamos.** La facturación electrónica
es `FU-09` (E-27) y el canal de notificación con `wa-link` es `FU-10` (E-28), ambos en la
Parte VIII de `ENMIENDA_SRS.md`. No se reescriben. Lo que esta adenda aporta sobre ellos es lo
que les falta: el número de solicitud, la política de caducidad del aviso y la dependencia
bloqueante de la DIAN, que E-27 no enuncia aunque su prioridad depende de ella. Es la Parte III.

**La ventana de validez de precio no es una tarea pendiente: la columna ya existe.**
`precio_oferta.vigente_hasta` está en `servicios/catalogo/tukit_catalogo/modelos/oferta.py:174`,
con su restricción de coherencia y su índice único parcial sobre los precios abiertos. Lo que
falta no es el esquema sino la **política**: quién la fija, con qué plazo por omisión y qué
hace el pipeline cuando vence. Eso cambia `SC-06` de "crear una columna" a "escribir una regla",
que es más barato y más honesto. Es §1.3 y E-34.

---

## 1. La línea base normativa es el v3, y eso reclasifica un tercio del hallazgo

El encargo pedía verificar, y no dar por bueno, que el SRS define solo `AD-01` a `AD-03` en
administración y que doce códigos citados no existen. La verificación cambia el resultado, y
conviene empezar por ahí porque afecta a todo lo demás.

`SRS_ISIS2610G19_v2.pdf` se extrajo con `pdftotext -layout` (1.677 líneas) y
`SRS_ISIS2610G19_v3.docx` se extrajo recorriendo el cuerpo del documento en orden, párrafos y
tablas, porque **los requisitos del SRS viven en tablas** y una extracción que solo lea
párrafos los pierde enteros. El v3 rinde 704 bloques. Enumerando todos los identificadores de
la forma `XX-NN` en los dos:

| Prefijo | v2 (PDF) | v3 (DOCX, línea base) | Qué cambió |
|---|---|---|---|
| `AD` | 01–03 | 01–03 | Igual. **Administración sigue teniendo tres requisitos y nada más.** |
| `SC` | 01–05 | 01–05 | Igual |
| `PE` | 01–06 | 01–06 | Igual |
| `NR` | 01–06 | 01–04, 06 | `NR-05` desaparece (hueco de numeración, E-24) |
| `OP` | 01–06 | 01–06 | Igual |
| `UI` | 01–07 | 01–07 | Igual |
| `CO` | 01–03 | 01–03 | Igual |
| `FU` | 01–03 | **01–05** | **Nuevos `FU-04` (retracto) y `FU-05` (logística inversa)** |
| `DP` | 01–04 | 02–04 | `DP-01` desaparece |
| `RD` | 01–06 | 03 | Solo queda `RD-03` |
| `DI` | 01 | 01–02 | Nuevo `DI-02` (degradación elegante) |
| `SG` | 01–04 | 01–06 | Nuevos `SG-05` (segundo factor) y `SG-06` (sesión) |
| `ML` | 01–09 | 02–09 | `ML-01` desaparece |
| `LI` | 02 | — | Desaparece |
| `AM` | — | **01, 03, 04** | **Nuevo módulo 9, aplicación móvil nativa** |
| `UM` | — | **01–05** | **Nuevo módulo 10, operación de última milla** |
| `PR` | — | **01–09** | **Nuevo módulo 11, proveedores mayoristas** |
| `ED` | — | **01–10** | **Nuevo módulo 12, contenido editorial** |
| `PV` | — | **01–03** | **Nueva §3.11.6, privacidad y derechos del titular** |
| `BD`, `CF`, `MT`, `PT` | igual | igual | Sin cambio |

El v2 rinde **75 identificadores** distintos y el v3 rinde **101**. Y los 101 son un
**superconjunto exacto** de los que `MOSCOW_REQUISITOS.md` cataloga: `comm -23` entre las dos
listas sale vacío. Eso comprueba que el v3 es la línea base sobre la que el resto del expediente
ya trabaja, y que el PDF v2 de la raíz es historia.

La diferencia entre esos 101 identificadores y los **99 requisitos** que `MOSCOW_REQUISITOS.md`
§3 prioriza son exactamente dos, y vale la pena nombrarlos porque confirman por un camino
independiente un defecto que la enmienda ya había levantado: **`DP-03` y `DP-04` aparecen una
sola vez cada uno, y es en el Anexo C** (`srs_v3` líneas 668–669), con su método de verificación
asignado. En §3.9 no están: esa sección empieza en `DP-02`. O sea que el SRS planifica pruebas
para dos requisitos que no ha enunciado. Es literalmente lo que E-18 reporta, y aquí se reproduce
sin haberlo buscado, contando identificadores. Por eso §10.3 propone que la comprobación de esta
adenda sea "cada requisito nuevo aparece al menos dos veces": una sola aparición es la huella de
este defecto.

### 1.1 De los doce códigos, ocho no existen y cuatro sí

Se buscó cada uno en los dos SRS, en `MOSCOW_REQUISITOS.md` y en `ENMIENDA_SRS.md`.

| Código citado | ¿v2? | ¿v3? | ¿MoSCoW? | ¿Enmienda? | Veredicto |
|---|:--:|:--:|:--:|:--:|---|
| `AD-04` | no | no | no | no | **Inexistente** |
| `AD-05` | no | no | no | no | **Inexistente** |
| `AD-06` | no | no | no | no | **Inexistente** |
| `AD-07` | no | no | no | no | **Inexistente** |
| `AD-25` | no | no | no | no | **Inexistente** |
| `AD-26` | no | no | no | no | **Inexistente** |
| `AD-33` | no | no | no | no | **Inexistente** |
| `FU-06` | no | no | no | **sí (E-10)** | **Inexistente hoy**, reservado por la enmienda con **otro significado** |
| `FU-04` | no | **sí** | sí | sí | **Existe.** Retracto y reversión, Ley 1480 de 2011 |
| `PR-08` | no | **sí** | sí | sí | **Existe.** Historial de pedidos y facturación del proveedor |
| `UM-03` | no | **sí** | sí | sí | **Existe.** Estado de entrega y notificación al padre |
| `AM-01` | no | **sí** | sí | sí, **para retirarlo** | **Existe hoy**, y E-01 lo retira del alcance |

**Ocho códigos confirmados como inexistentes; cuatro reclasificados como reales.** El análisis
previo los marcó falsos porque leyó el PDF v2, y lo dice sin saberlo en su §8 al enumerar el
conteo por prefijo que obtuvo: ahí no aparecen `PR`, `UM` ni `AM`, que es la huella de haber
leído el documento equivocado.

Dos consecuencias que hay que decir en voz alta porque corrigen conclusiones del análisis
previo, no solo sus datos.

**El argumento sobre la facturación era correcto y se descartó por error.** El plan vigente
sostiene que la facturación al padre es un hueco del SRS porque *"'Factura' solo aparece en
`PR-08`, que es la del proveedor"* (`pipeline_end-to-end_monorepo_4a4ee99a.plan.md:293`). El
análisis previo lo declaró falso con el argumento de que *"`PR` no es un prefijo que el
documento use"* (§3, hallazgo 4). **El plan tenía razón.** `PR-08` existe en el v3 §3.15, dice
literalmente *"consultar el historial de sus pedidos mayoristas y su facturación con Tukit"*, y
es del proveedor. El hueco existía y el argumento con que se enunció era bueno. Lo que ya no se
sostiene es que siga siendo un hueco: `FU-09` lo cierra, y por eso E-40 no levanta un requisito
sino una dependencia.

**`FU-06` es el caso más delicado de los doce, y no por inexistente.** El contrato lo usa dos
veces con el sentido de "el precio no se mueve después de confirmar"
(`CONTRATO_API.md:387` y `:496`). La enmienda ya reservó `FU-06` para otra cosa: *"La
confirmación del pago se resuelve por notificación entrante idempotente"* (E-10). El
congelamiento de precio es **`FU-08`** en la misma enmienda. Así que el contrato no cita un
código vacío: cita un código que va a existir con un significado distinto del que le atribuye.
Eso es peor que una cita vacía, porque una vez aplicada la enmienda la cita **parecerá
correcta** y nadie la revisará.

### 1.2 Un hallazgo que el encargo no pedía: `AD-01` no se cita en ninguna parte

Buscando los doce códigos apareció su reverso. `AD-01` es el único requisito del SRS que exige
la cola de revisión —*"El Panel Admin debe mostrar los mapeos de útiles pendientes de
validación: lista de origen, grado, e ítems con estado COINCIDENCIA_PARCIAL o
SIN_COINCIDENCIA"*— y **no aparece ni una vez** en `CONTRATO_API.md`, ni en el plan, ni en
`tukit/apps/**`, ni en `tukit/libs/**`. La verificación es una búsqueda de `AD-01` sobre esos
cuatro ámbitos y devuelve vacío.

En su lugar, el contrato traza `GET /v1/admin/cola` a `AD-02` y `AD-03`
(`CONTRATO_API.md:441`). `AD-02` es la **corrección** del mapeo y `AD-03` es la
**autenticación**. La cola está trazada a todo menos al requisito que la pide. No es un código
falso —los dos existen— sino un trazado equivocado entre códigos reales, que es la clase de
defecto que ninguna búsqueda de identificadores inexistentes encuentra, y que un evaluador que
lea `AD-01` y pregunte "¿dónde se implementa esto?" encuentra en un minuto.

### 1.3 Tres afirmaciones del análisis previo que hay que corregir

Se listan aquí y no solo en el documento hermano porque condicionan requisitos de esta adenda.

**La ventana de validez de precio no está por construir.** `FLUJO_EXTREMO_A_EXTREMO.md` §2.5
dice que *"la ventana `vigente_hasta` es tarea pendiente del plan"* y su §5.3 le asigna 1,5
jornadas como hueco R5. La columna existe: `oferta.py:174`, con la restricción
`precio_vigencia_coherente`, el índice único parcial `uq_precio_vigente_por_oferta` sobre
`vigente_hasta IS NULL` y un comentario que describe la restricción de exclusión de rangos que
la acompaña en Postgres con su razón: *"Sin ella, 'el precio de hoy' es una consulta ambigua,
que es exactamente lo que les pasaba a las dos tablas de precio anteriores"*
(`oferta.py:187-194`). La tabla lo declara además como decisión de diseño: *"Un tramo de precio
con vigencia, no una columna que se sobreescribe"* (`oferta.py:152`). Lo que falta es la
política, y `SC-06` se redacta sobre eso.

**Ya hay una API HTTP de dominio.** El análisis afirma en §1 que *"no hay ninguna API HTTP de
dominio en todo `tukit/servicios/**`"*. Hoy existe `servicios/catalogo/tukit_catalogo/api.py`.
Es obra del agente de backend en vuelo y confirma lo que el propio análisis advertía de sí
mismo: sus medidas del código caducan rápido.

**El artefacto reutilizable necesita menos estructura nueva de la que se estimó.** El análisis
propone una tabla `resolucion_item_lista` y advierte que subiría el manifiesto de 70 a 71
tablas. Sigue siendo necesaria para el anclaje de línea a producto, pero la **procedencia** que
`NR-08` exige no necesita tabla: necesita una columna `origen` en `lista_oficial`, que hoy tiene
seis columnas (`listas.py:48-56`) y ninguna que diga de dónde vino la lista.

---

## 2. Por qué esta adenda es un documento y no una edición del `.docx`

El encargo pedía decidir esto y explicarlo. Hay fuente editable, y la decisión es **no
editarla**, por tres razones en orden de peso.

**La enmienda anterior no está aplicada, y solapa secciones con esta.** `ENMIENDA_SRS.md`
produce 28 cambios sobre el mismo `.docx` y ninguno se ha incorporado: el propio documento lo
declara en su cabecera —*"Este documento **no modifica el SRS**: produce el texto"*— y su
Parte VII escribe los comandos de verificación que se correrían *después* de aplicar. Cinco de
esos cambios añaden requisitos en §3.4, §3.7, §3.8, §3.11.6 y §3.11.7, que son tres de las
cinco secciones donde esta adenda añade los suyos. Si se escribiera ahora en el documento, §3.8
tendría `FU-11` y no `FU-06` a `FU-10`, y §3.7 tendría `CO-05` y no `CO-04`. La numeración
quedaría con huecos que nadie podría explicar, que es exactamente el defecto que E-24 levanta
contra la línea base actual.

**El proyecto ya fijó la convención, y es esta.** `ENMIENDA_SRS.md` y `ENMIENDA_VFP.md` son
documentos hermanos que producen texto de reemplazo con su sección de destino y su sustento, y
no tocan el binario. Escribir la adenda en el mismo formato la hace aplicable por la misma
persona en la misma sesión, con el mismo criterio. Inventar un segundo mecanismo para el mismo
trabajo sería la incoherencia de gobierno que el propio expediente audita en otros.

**Editar un `.docx` mecánicamente es más riesgoso de lo que parece.** El documento tiene tabla
de contenido con números de página, 22 tablas numeradas con sus leyendas, estilos con nombre y
una matriz de trazabilidad en el Anexo C que referencia cada requisito. Insertar once filas en
cinco tablas distintas y sus once entradas correspondientes en el Anexo C es trabajo de
procesador de texto con revisión visual, no de biblioteca. Un `.docx` con la tabla de contenido
desincronizada es peor que un `.docx` sin enmendar, porque el defecto es visible en la primera
página.

**Lo que sí se produce, entonces**, es texto listo para pegar: cada cambio trae su sección de
destino, el texto actual —que en los once casos es "no existe", y se dice—, el texto de
reemplazo con las ocho columnas de las tablas del SRS, y la fila del Anexo C. Y §9 da la lista
de comprobación posterior.

---

## 3. El formato del SRS, que es lo que estos requisitos tienen que imitar

Antes de redactar conviene fijarlo, porque el encargo insiste en que el nivel de detalle sea el
del documento y no el que a uno le parezca.

Los requisitos del v3 viven en **tablas de ocho columnas**, una tabla por módulo, con esta
cabecera literal (v3 §3.1 y siguientes):

```
# REQ | Tipo | Descripción | Razón | Criterio de aceptación | Prior. | Módulo | Ver.
```

- **`Tipo`** toma tres valores: `RF` funcional, `RNF` no funcional, `RML` de aprendizaje
  automático.
- **`Prior.`** toma `Alta | Media | Baja`.
- **`Ver.`** toma `v1 | v2 | v0.2`.
- **`Módulo`** es el nombre corto del módulo, y admite dos separados por barra cuando el
  requisito es compartido: `Fulfillment / Última milla` en `FU-05`, `RAG + PWA` en `ML-02`.
- La **`Descripción`** se escribe en tercera persona con "El sistema debe…", y la marca
  `[NÚCLEO]` se anexa cuando el requisito pertenece al flujo principal.
- El **`Criterio de aceptación`** es una oración verificable con su método implícito. Los
  buenos del documento nombran el corpus o la condición de prueba: `NR-04` exige *"El 100 % de
  los candidatos sugeridos existe en el catálogo activo"*; `UM-04` exige *"Con la red
  desactivada, el operador registra estados y estos se sincronizan sin pérdida"*.

Cada requisito aparece además en el **Anexo C**, la matriz de trazabilidad, con seis columnas:

```
ID | Tipo | Función | Módulo | Fase | Método Verificación
```

donde `Función` es una de las once del §2.2 (`F1` a `F11`) y `Método Verificación` empieza por
la letra del método —`I` inspección, `A` análisis, `D` demostración, `P` prueba— seguida de la
acción concreta: `D corrección y publicación` en `AD-02`.

`ENMIENDA_SRS.md` añade de hecho una novena columna, **`MoSCoW`**, con los tres criterios de
`Must` de `MOSCOW_REQUISITOS.md` §1.1: (a) eslabón del flujo `lista → kit → orden` o regla del
camino infeliz sin la cual el sistema cobra mal o borra a medias, (b) obligación legal, (c)
condiciona la validez de la evidencia académica. Esta adenda la conserva y, siguiendo la
disciplina de la Parte VIII de la enmienda, **dice en voz alta la razón de la prioridad cada
vez que no es `Must`**.

### 3.1 Por qué estos números y no otros

Los códigos nuevos son `AD-04` a `AD-07`, `PE-07`, `SC-06`, `NR-07` a `NR-09`, `CO-05` y
`FU-11`. Ninguno colisiona con lo que la enmienda reserva, que es `CF-02a/b`, `DP-03` a
`DP-05`, `PS-01` a `PS-05`, `CO-04`, `MT-03`, `FU-06` a `FU-10`, `PV-04`, `PV-05`, `DE-01` a
`DE-04`, `OP-07` y `OP-08`. Se verificó uno por uno.

Sobre el orden dentro de `AD` hay que ser transparente, porque hubo una elección y ocultarla
sería el tipo de cosa que este expediente audita. **El orden se escogió para que coincidiera
con el significado que el contrato y el código ya le dan a `AD-05`, `AD-06` y `AD-07`.** Hoy
`CONTRATO_API.md` §7 traza `POST /v1/admin/productos/{sku}/no-disponible` a `AD-05`,
`POST /v1/admin/trabajos/{id}/revision` a `AD-06` y `POST /v1/admin/productos` a `AD-07`, y hay
quince archivos de `tukit/apps/admin/**` y `tukit/libs/ts/tukit-contrato/**` que repiten esas
tres asignaciones. Al numerar los requisitos nuevos en ese orden, **tres de las cuatro citas se
vuelven correctas sin tocar una línea**, y la corrección se reduce a `AD-04`, que hoy nombra
las acciones por línea y tiene que apuntar a `AD-02`.

Eso sería una mala razón si el orden no se sostuviera por sí mismo, así que conviene mostrar
que sí: los cuatro quedan ordenados **por ámbito creciente de lo que la acción afecta**.
`AD-04` es la pantalla, que contiene a las demás. `AD-05` actúa sobre una línea. `AD-06` actúa
sobre el trabajo entero. `AD-07` actúa sobre el catálogo, o sea sobre todos los trabajos
futuros. Es el mismo criterio con que §3.8 ordena `FU-01` a `FU-05`, de la orden al ciclo de
vida. Si el orden hubiera exigido forzarse, se habría forzado la corrección y no el requisito;
no fue el caso.

---

# Parte I — La revisión del admin

Cuatro requisitos nuevos en §3.6 y uno en §3.2 que los sostiene. Es el bloque que se está
construyendo ahora mismo en `tukit/apps/admin/`, y el que hoy se construye contra cuatro
códigos que no existen.

---

## E-29 — Añadir `AD-04`: consola de revisión con comparación de tres paneles

**Severidad:** Alta.
**Sección:** §3.6 Módulo 6, Panel Administrador Tukit, tras `AD-03`.
**Sustento:** `AD-01`, `AD-02`, `PE-04`, `ML-09`, `PE-07` (E-33), ADR 0018 (la espera humana
como estado de primera clase).

`AD-01` exige una **lista** de mapeos pendientes con su estado, y `AD-02` exige poder
**corregirlos**. Ninguno de los dos exige que el revisor vea de dónde salió el renglón que está
corrigiendo. Esa omisión tiene una consecuencia que hay que enunciar con precisión, porque es lo
que convierte una mejora de pantalla en un requisito.

`PE-04` manda a esta cola *"los ítems con baja confianza de extracción"*, y `ML-09` repite la
obligación como atributo de calidad. Un ítem llega a la cola, entonces, precisamente porque se
duda de que **la percepción** lo haya leído bien. Pero con `AD-01` y `AD-02` solos, lo único que
el revisor ve es la descripción ya extraída y los candidatos de catálogo: puede detectar un
error de **resolución** —"este lápiz no es el que pide"— y no puede detectar un error de
**percepción** —"la lista nunca dijo lápiz"—. La pantalla que el SRS describe no puede descargar
la obligación que `PE-04` le encomienda. Eso no es un hueco de comodidad; es un requisito que
apunta a un mecanismo incapaz de cumplirlo.

El panel de ítems emparejados se pide **agrupado por tipo de kit** y no en una lista plana
porque el objeto que se aprueba es el trabajo con sus tres kits, y una diferencia entre perfiles
sobre la misma línea es información de revisión: si `Ahorrador` y `Premium` eligen el mismo
producto para un renglón, o el catálogo no tiene niveles para ese concepto o la resolución los
ignoró, y las dos cosas son defectos que solo se ven comparando.

#### Texto actual

> *(No existe. §3.6 termina en `AD-03`.)*

#### Texto de reemplazo

> | `AD-04` | `RF` | El Panel Admin debe presentar cada mapeo pendiente en una vista de comparación con tres paneles simultáneos: (1) el documento de origen tal como se recibió, (2) la salida sin procesar del modelo de percepción para ese documento, y (3) los ítems emparejados agrupados por tipo de kit, cada uno con su estado de resolución, el producto elegido y sus candidatos. Los tres paneles se refieren al mismo trabajo y se navegan juntos: al seleccionar un ítem del tercer panel, los otros dos señalan la página y el fragmento de los que salió. `[NÚCLEO]` | Un ítem llega a la cola porque se duda de la extracción (`PE-04`, `ML-09`), no de la resolución. Sin el documento de origen y sin la salida del modelo a la vista, el revisor solo puede juzgar si el producto elegido corresponde a la descripción extraída, y no si la descripción extraída corresponde a lo que el colegio escribió. La mitad de los errores que esta cola existe para atrapar es invisible sin los dos primeros paneles. | Para cualquier trabajo en estado de espera de revisión, el panel muestra los tres paneles poblados y el revisor puede recorrer las páginas del documento de origen sin salir de la vista. Seleccionar un ítem lleva el primer panel a la página de la que se extrajo y resalta el fragmento correspondiente en el segundo. Se verifica sobre al menos un trabajo por cada formato admitido por `PE-01`, y sobre un trabajo con un error de percepción inyectado a propósito, que el revisor debe poder identificar como tal y distinguir de un error de resolución. | Alta | Admin | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `AD-04` | `RF` | F7 Validar mapeos | Admin | Fase 5 | D revisar trabajo con error de percepción inyectado |

**Por qué `Must`.** Criterio (a). La revisión humana es eslabón del flujo `lista → kit → orden` y
no un adorno: `CONTRATO_API.md:274` lo formula como invariante —*"El acudiente **nunca** ve un
kit sin revisar"*— y el ADR 0018 hace de la espera humana un estado del que solo se sale por una
decisión registrada. `AD-04` no añade un eslabón: hace que el eslabón existente pueda cumplir lo
que `PE-04` le pide. Un requisito que habilita el cumplimiento de otro `Must` hereda su
prioridad.

**Dependencia dura.** `AD-04` no se puede construir sin E-33 (`PE-07`): hoy ni el documento de
origen ni la salida del modelo se persisten, y dos de los tres paneles no tienen datos que
mostrar. Se dice aquí y se repite en §9, porque es el error de secuencia más fácil de cometer:
empezar por la pantalla.

---

## E-30 — Añadir `AD-05`: marcar un ítem como fuera de stock o como categoría aún no provista

**Severidad:** Alta.
**Sección:** §3.6 Módulo 6, tras `AD-04`.
**Sustento:** `AD-02`, `SC-05`, `OP-06`, y el modelo de `item_lista_oficial`
(`servicios/catalogo/tukit_catalogo/modelos/listas.py:148-152`, `:196-199`).

`AD-02` permite *"marcar el ítem como no disponible"* y `SC-05` obliga a *"identificar y excluir
de los kits generados los productos marcados como sin stock"*. Entre los dos parece que el caso
está cubierto, y no lo está, porque **la frase "no disponible" tapa dos hechos que no tienen ni
el mismo alcance ni la misma duración ni el mismo remedio.**

Que el Éxito se quedó sin lápices Kores es un hecho **transitorio** sobre una **oferta**, cierto
para **todos los colegios** mientras dure, y se remedia recayendo a otra tienda o a otro nivel
del mismo concepto. Que Tukit no vende los uniformes del Agustiniano es un hecho
**estructural** sobre una **categoría**, cierto para **ese colegio** —otro colegio podría tener
un uniforme que sí se surte— y no se remedia: se informa. Marcarlos con el mismo botón produce
uno de dos defectos, según cuál semántica gane. Si gana la de stock, el uniforme reaparece en el
kit cuando el inventario se repone, y el sistema promete algo que nunca supo vender. Si gana la
de categoría, el lápiz agotado queda excluido para siempre.

El modelo ya tiene las dos piezas separadas y con la asimetría documentada. Para el lápiz,
`producto_canonico.activo` y la oferta. Para el uniforme, `item_lista_oficial.tipo_item`, cuyo
comentario explica exactamente por qué el alcance es por colegio: *"Nulo significa 'lo que diga
el concepto'… 'Diccionario: el disponible en casa' no vuelve el diccionario incomprable para los
diecisiete, solo para ese colegio"* (`listas.py:148-151`). Y la restricción
`item_no_surtible_explica_como_conseguirlo` (`listas.py:196-199`) ya impide marcar algo como no
surtible sin decir cómo se consigue, que es la mitad útil de la marca.

#### Texto actual

> *(No existe. `AD-02` menciona "marcar el ítem como no disponible" sin distinguir alcance ni
> duración.)*

#### Texto de reemplazo

> | `AD-05` | `RF` | El Panel Admin debe permitir dos marcas distintas sobre un ítem, con alcance y duración diferentes y no intercambiables. (1) **Fuera de stock**: marca transitoria sobre la oferta de un producto, que vale para todos los trabajos mientras dure y se levanta cuando el proveedor repone; el sistema excluye el producto de los kits (`SC-05`) y recae a otra oferta o a otro nivel del mismo concepto si existe. (2) **Aún no provisto**: marca estructural sobre una línea de la lista de un colegio, que declara que Tukit no surte esa categoría —el caso de los uniformes—, exige una instrucción textual de cómo conseguirlo y convierte la línea en informativa: se muestra, no se cobra y no cuenta para la cobertura. Ninguna de las dos marcas puede aplicarse sin quedar registrada con autor, marca de tiempo y motivo. | "No disponible" nombra hoy dos hechos con alcance, duración y remedio distintos. Con un solo botón, o el uniforme reaparece en el kit al reponerse un inventario que nunca lo contuvo, o el lápiz agotado queda excluido para siempre. Prometer lo que no se puede entregar es el modo de falla más caro del negocio, y callar lo que el colegio pide deja al acudiente peor que antes. | Un producto marcado fuera de stock no aparece en ningún kit generado mientras la marca esté activa, y vuelve a aparecer al levantarse sin intervención humana. Una línea marcada como aún no provista aparece en el kit del colegio afectado con la instrucción del colegio visible, queda fuera del total y del conteo de cobertura, y **no** cambia el comportamiento de esa misma categoría en los demás colegios. Verificado con el caso real del uniforme de un colegio del corpus y con un producto agotado y repuesto. | Alta | Admin / Scraper | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `AD-05` | `RF` | F7 Validar mapeos | Admin / Scraper | Fase 5 | D marcar uniforme y agotado, verificar alcance distinto |

**Por qué `Must`.** Criterio (a), como regla del camino infeliz. `SC-05` ya es `Alta` y exige el
efecto; `AD-05` es el mecanismo por el que una persona lo provoca y, sobre todo, es lo que
impide que el sistema cobre una línea que no puede entregar. Cobrar mal es el criterio (a)
literal.

---

## E-31 — Añadir `AD-06`: visto bueno del admin y constitución del artefacto validado

**Severidad:** Alta.
**Sección:** §3.6 Módulo 6, tras `AD-05`.
**Sustento:** `AD-01`, `AD-02` y su criterio *"El admin corrige mapeos y publica la lista al
padre"*, `PE-04`, ADR 0018, y `version_lista_oficial.revisada_en` / `revisada_por`
(`listas.py:91-102`).

El criterio de aceptación de `AD-02` dice, de pasada, *"El admin corrige mapeos y **publica la
lista al padre**"*. Publicar está ahí, en la columna de criterio de un requisito cuya
descripción es sobre corregir. Eso basta para justificar que exista un botón y no basta para
gobernarlo: no dice de qué estado a qué estado se pasa, ni qué se puede rechazar, ni qué
verificación previa es obligatoria, ni qué queda registrado. El ADR 0018 exige lo contrario:
estados explícitos y auditados, no banderas dispersas.

Y hay una razón mayor para separarlo. Este es el acto que, tras `NR-07` (E-35), **constituye el
artefacto validado reutilizable**. Mientras publicar sea un efecto lateral del criterio de otro
requisito, la reutilización no tiene de dónde colgarse. El modelo ya nombra esa firma y ya
explica que no es lo mismo que publicar: *"Publicar es decir 'esta es la lista del colegio';
revisar es decir 'ya miramos que tenemos para responderla'"* (`listas.py:94-96`), y el código la
hace cumplir con una excepción dedicada (`descubrir.py:411`, `exigir_sin_revisar`).

#### Texto actual

> *(No existe. La publicación al padre aparece en el criterio de aceptación de `AD-02`, no como
> requisito propio.)*

#### Texto de reemplazo

> | `AD-06` | `RF` | El Panel Admin debe exigir una decisión explícita del Admin Tukit para que un trabajo en espera de revisión salga de ese estado, con dos resoluciones posibles: **aprobar**, que publica los kits al acudiente y dispara su aviso, o **devolver**, que reabre el trabajo con una nota obligatoria y sin notificar al acudiente. Aprobar está bloqueado mientras quede algún ítem sin concepto resuelto y sin marca que explique por qué no lo necesita (`AD-05`), y mientras haya propuestas de alta de producto sin resolver (`AD-07`). La decisión queda registrada con autor, marca de tiempo, resolución y nota, y es la única transición que saca al trabajo del estado de espera humana. `[NÚCLEO]` | Publicar al padre aparece hoy en el criterio de aceptación de `AD-02` y no como requisito, de modo que el acto que cierra la revisión no tiene estado, ni condición previa, ni registro propio. Es además el acto que constituye el artefacto validado reutilizable (`NR-07`): sin un requisito que lo nombre, la reutilización no tiene de qué colgarse. Y cerrar con renglones sin resolver deja el renglón mudo en todos los kits futuros de ese grado. | Un trabajo en espera de revisión no cambia de estado por ningún otro camino que esta decisión, verificado intentando publicarlo por las demás rutas de la API. Aprobar con un ítem sin resolver ni marcar es rechazado con un error que nombra los ítems que faltan. Aprobar publica los kits, dispara el aviso (`FU-11`) y escribe la firma de revisión sobre la versión de la lista. Devolver deja el trabajo revisable de nuevo y no genera ninguna notificación al acudiente. Toda decisión queda consultable en la auditoría con autor y marca de tiempo. | Alta | Admin | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `AD-06` | `RF` | F7 Validar mapeos | Admin | Fase 5 | D aprobar, devolver y verificar transiciones bloqueadas |

**Por qué `Must`.** Criterio (a) sin matices: es la puerta del flujo principal. Si no existe, o
el kit llega sin revisar —lo que el contrato declara invariante que no ocurre— o no llega.

**Nota de implementación que evita rehacer.** El plan vigente pone los trabajos durables del
ADR 0018 de penúltima tarea. `AD-06` **es** una transición de esa máquina de estados.
Construirlo antes obliga a implementarlo sobre banderas booleanas y a rehacerlo después. No es
una preferencia de orden: es el mismo hallazgo que `FLUJO_EXTREMO_A_EXTREMO.md` §3 levanta como
desalineamiento 2, y `AD-06` le pone el requisito que le faltaba.

---

## E-32 — Añadir `AD-07`: alta manual de producto con sus tres fuentes

**Severidad:** Alta.
**Sección:** §3.6 Módulo 6, tras `AD-06`.
**Sustento:** `AD-02`, `NR-04`, `OP-06`, `SC-01`, `SC-04`, y la implementación existente en
`servicios/catalogo/tukit_catalogo/descubrir.py` y `tiendas.py`.

Este es el hueco de requisito más consecuente del módulo, porque es funcionalidad **ya
construida y probada** que hoy se ejecuta sin requisito que la respalde. `AD-02` cubre
*"seleccionar un producto diferente **del catálogo**"*. Crear uno que el catálogo no tiene es
otra cosa, y es la única salida cuando el estado es `HUECO_CATALOGO`: se entendió qué pide el
colegio y no lo tenemos. `OP-06` obliga a mostrarle al padre el ítem sin coincidencia *"y ofrecer
una acción de corrección"*, pero no dice que alguien pueda resolverlo por el lado de la oferta.

Las tres fuentes que el requisito tiene que cubrir están en estados de madurez muy distintos, y
el requisito debe enunciarlas las tres sin fingir que cuestan lo mismo.

| Fuente | Estado hoy | Evidencia |
|---|---|---|
| Las API de las tres tiendas | **Construida** | `tiendas.py` declara Éxito y Panamericana sobre VTEX y Papelería Grancentral sobre Shopify, con búsqueda y ficha exacta en funciones separadas; `descubrir.py --crear-util --consulta …` lista candidatos numerados sin escribir nada y `--elegir N` encola el elegido |
| El raspado de una URL con Firecrawl | **No existe** | No hay SDK, ni cliente, ni clave, ni dependencia declarada. Lo único que hay es el UUID de procedencia `AGENTE_FIRECRAWL` en `cargador.py` y un CSV de 19 filas producido fuera del sistema |
| El formulario manual puro | **Construida** | `descubrir.py --crear-libro --isbn … --titulo … --precio … --tienda …`, con validación del dígito de control del ISBN antes de tocar la base |

Y hay un invariante de la implementación que el requisito **tiene** que heredar, porque es lo
que hace segura el alta: nada entra al catálogo en un solo acto. Las tres fuentes encolan en
`propuesta_producto`, y solo una segunda acción con nivel explícito (`--aprobar ID --nivel …`)
crea el producto canónico con su oferta y su primer precio, en una transacción. Un alta de un
paso sería el camino más corto a violar `NR-04`, que es restricción dura: *"El normalizador nunca
debe sugerir un producto que no exista en el catálogo activo"*. Un producto dado de alta a la
carrera para cerrar una revisión es, a efectos del padre, un producto inventado.

Por el reparto del lock, el raspado **no puede vivir en `catalogo`**: `ARQUITECTURA.md` §1 le da
a `ingesta` todo lo que habla con el mundo exterior y a `catalogo` solo lo que existe y a qué
precio. Que hoy `tiendas.py` esté dentro de `catalogo` es una excepción tolerada del andamiaje,
no el destino.

#### Texto actual

> *(No existe. `AD-02` cubre elegir otro producto **del catálogo**, no crear uno que no está.)*

#### Texto de reemplazo

> | `AD-07` | `RF` | El Panel Admin debe permitir al Admin Tukit dar de alta un producto que el catálogo no tiene, cuando la resolución de un ítem termina sin coincidencia admisible, con tres fuentes de origen: (1) consulta a las API de las tiendas integradas, que devuelve candidatos con nombre, precio e imagen para que el admin elija uno; (2) extracción asistida desde una URL de producto indicada por el admin, ejecutada por el servicio de ingesta; y (3) formulario manual, para el caso en que ninguna fuente automática sirva. Las tres cubren útil y libro, y en los tres casos el alta registra como mínimo producto, precio e imagen, más el ISBN con su dígito de control verificado cuando es libro. El alta ocurre en **dos actos separados**: la fuente encola una propuesta, y un segundo acto explícito con el nivel de calidad asignado (`económico`, `confiable` o `premium`) la convierte en producto del catálogo con su oferta y su primer precio. Cada producto nacido así queda con la procedencia de su fuente y con el autor de las dos acciones. | `AD-02` solo permite elegir otro producto del catálogo; cuando el estado es `HUECO_CATALOGO` no hay nada que elegir, y hoy esa salida se ejecuta por línea de comandos sin requisito que la respalde. Las dos primeras fuentes existen porque el precio y la imagen fiables vienen de la ficha de la tienda y no de teclearlos. La separación en dos actos protege la restricción dura de `NR-04`: un producto creado en un solo paso para cerrar una revisión es, para el acudiente, un producto inventado. | El admin resuelve un ítem sin coincidencia por cada una de las tres fuentes y el producto resultante queda en el catálogo activo con producto, precio e imagen, y con ISBN validado si es libro. Ninguna de las tres fuentes crea un producto en un solo acto: verificado intentando publicar el trabajo con una propuesta sin aprobar, que `AD-06` rechaza. La procedencia de cada producto dado de alta es consultable y distingue las tres fuentes. Verificado sobre los ítems sin coincidencia del corpus de listas. | Alta | Admin / Scraper | v1 |
>
> **MoSCoW:** Should.

**Fila del Anexo C:**

> | `AD-07` | `RF` | F7 Validar mapeos / F8 Actualizar catálogo | Admin / Scraper | Fase 5 | D dar de alta por las tres fuentes y verificar los dos actos |

**Por qué `Should` y no `Must`, que es la decisión incómoda de este requisito.** El flujo
`lista → kit → orden` se completa sin `AD-07`. Un ítem sin coincidencia tiene ya una salida
enunciada y obligatoria: `OP-06` exige marcarlo *"no disponible en Tukit"* y mostrarlo al padre
con claridad. El kit se genera, se cobra y se entrega con ese hueco declarado. Lo que `AD-07`
mejora es la **cobertura**, que es el valor del producto y no su validez.

No cae tampoco en el criterio (c). La evidencia académica de cobertura se mide sobre el corpus
anotado, y el mecanismo de alta que la produce **ya existe y ya corre** en `descubrir.py`; lo
que `AD-07` exige es exponerlo en el panel. Un requisito cuya única parte nueva es la pantalla
de algo que ya se puede hacer no es un `Must` por obligación legal ni por eslabón del flujo.

Es, eso sí, el `Should` más fuerte de esta adenda, y por una razón que conviene dejar escrita:
es el único requisito de la lista cuya lógica está construida y probada, de modo que su relación
entre valor y costo restante es la mejor del inventario. Que sea `Should` describe su prioridad
formal, no su orden de construcción.

**Alcance diferido, declarado.** La tercera fuente —el raspado con Firecrawl— es la única de las
tres que es trabajo nuevo completo, y le corresponde a `ingesta`. El requisito la enuncia porque
un requisito describe el sistema y no el calendario, pero conviene que el plan la ordene después
de las otras dos, que cubren el caso común.

---

## E-33 — Añadir `PE-07`: persistencia del documento de origen y de la salida sin procesar del modelo

**Severidad:** Alta.
**Sección:** §3.2 Módulo 2, Percepción, tras `PE-06`.
**Sustento:** `AD-04` (E-29), `PE-04`, `PE-06`, `ML-06`, `ML-09`, `PV-03`, y el estado del código
en `servicios/inteligencia/tukit_inteligencia/percepcion.py` y `gemini.py`.

Este requisito existe porque `AD-04` no se puede construir sin él, y porque hoy el sistema
descarta deliberadamente lo que esa pantalla necesita.

La verificación es concreta. `percepcion.py` recibe el contenido, lo renderiza a páginas, llama
al adaptador del modelo por página y devuelve una estructura con los ítems, el número de
páginas, los grados detectados y las degradaciones: el documento recibido no se guarda en
ninguna parte. Y `gemini.py:99-107` decodifica la respuesta del modelo, extrae de ella el
fragmento de texto que le interesa y descarta el resto. Así que **dos de los tres paneles de
`AD-04` no tienen origen de datos**, y no por falta de interfaz sino por falta de persistencia
tres capas más arriba.

Hay un segundo motivo, independiente de la pantalla, y es de auditoría. `ML-06` exige que *"cada
kit generado tiene trazabilidad hacia los ítems de la lista que lo originaron"*. Hoy esa cadena
se corta en el primer eslabón: se puede llegar del kit al ítem extraído y no del ítem extraído
al renglón del documento, porque el documento ya no está. Un trabajo de grado cuya contribución
central es un pipeline de percepción y que no conserva la entrada de ese pipeline tampoco puede
reproducir su propia medición.

### El argumento de privacidad, que es la parte que hay que sostener y no declarar

**Decisión tomada: la salida del modelo se persiste en crudo, sin depurar.** El argumento es que
la lista de útiles no identifica al menor. Esa afirmación es correcta y hay que escribirla con
precisión, porque de su alcance depende que el requisito sea defendible.

Lo que el artefacto contiene es **un inventario de productos por grado**: "2 cuadernos cuadriculados
grandes", "1 caja de colores x12", "Don Quijote de la Mancha, Ed. Enlace". Eso es vocabulario de
catálogo, no un documento del estudiante. No hay nombre, ni documento de identidad, ni edad, ni
dirección, ni nota, ni diagnóstico. El sujeto del documento es **el grado**, que es un colectivo
de decenas de niños, y no una persona. Un dato personal es el que permite identificar a una
persona natural o hacerla identificable; una lista de útiles de Cuarto no permite ni lo uno ni lo
otro, y no lo permite tampoco cruzada con el resto del sistema, porque de ella no se deduce quién
está matriculado.

Conviene ser explícito sobre en qué **no** consiste este argumento, porque es donde se cae solo si
se estira. No se está afirmando que el pipeline no trate datos de menores: los trata, y por eso
existen `PE-06`, `PV-03` y la frontera de cumplimiento de `identidad`. Lo que se afirma es más
estrecho y más firme: **este artefacto concreto, en el caso normal, no es uno de ellos.** La
obligación de `PE-06` y `PV-03` no se relaja ni se reinterpreta; se constata que su objeto —el
nombre del menor— no está presente en el artefacto que `PE-07` conserva.

De ahí sale la razón positiva para conservarlo en crudo, que es la que justifica el requisito.
**El objeto de `PE-07` es auditar la percepción.** Una copia depurada solo permite comprobar que
el sistema depura; no permite comprobar que el modelo leyó bien, que es exactamente lo que el
revisor de `AD-04` tiene que juzgar y lo que `PE-04` manda a esa cola. Aplicarle una
transformación a la evidencia antes de guardarla la inutiliza para su único propósito. Y el
mismo razonamiento vale para `ML-06`: una trazabilidad del kit al renglón que pasa por una copia
alterada no es trazabilidad.

### El caso residual, que sí existe y hay que nombrar

Hay un caso en que el argumento anterior no aplica, y es la diferencia entre las dos entradas del
sistema. La lista **genérica que publica el colegio** no lleva nombres. El **PDF que sube un
acudiente** puede llevarlos: es habitual que el colegio entregue la lista con el nombre del
estudiante impreso en el encabezado, o que el papá suba la circular completa en vez de la página
de útiles, o una foto donde aparece el nombre escrito a mano en la esquina.

Ese caso es acotado, es reconocible y no invalida la decisión: lo que exige es que el requisito lo
nombre en vez de dejarlo implícito. La solución que `PE-07` adopta no es depurar el artefacto
—eso nos devolvería al problema anterior— sino **cortar la propagación**: el nombre, si aparece,
se detecta en la extracción y no sale del artefacto de evidencia. No entra a los ítems extraídos,
ni a los kits, ni a las notificaciones, ni a los registros de operación, que son justamente los
cuatro destinos que `PE-06` y `PV-03` protegen cuando dicen *"en registros almacenados, en logs de
operación y en el contenido enviado a servicios de terceros"*. El artefacto queda como una pieza
de evidencia con acceso restringido al rol de revisión, con cada acceso registrado y con plazo de
retención, que es el tratamiento que corresponde a algo que puede contener un dato sensible aunque
normalmente no lo contenga.

Esta es la parte que hace la decisión auditable, y por eso está escrita: el proyecto ya documentó
una vez una decisión de privacidad silenciosa que resultó equivocada —el servicio anterior
*"guardaba el texto crudo de la lista SIN redactar los nombres de menores, pese a que el mismo
sistema ya tenía la función de redacción"* (`listas.py:7-11`)—, y la diferencia entre aquello y
esto no es el resultado sino el registro. Aquello fue un descuido que nadie decidió; esto es una
decisión con su razón, su alcance y su caso de borde por escrito. Si mañana alguien la discute,
discute un argumento y no un silencio.

#### Texto actual

> *(No existe. §3.2 termina en `PE-06`.)*

#### Texto de reemplazo

> | `PE-07` | `RF` | El sistema debe persistir, asociados al trabajo que los produjo, el documento de origen tal como se recibió y la salida sin procesar del modelo de percepción por página, incluidas las respuestas truncadas o degradadas, y debe conservarlos **sin transformación**: la salida del modelo se guarda tal cual la devolvió, **sin depuración previa**, porque es evidencia de lo que el modelo leyó y una copia depurada no sirve para auditar el modelo. El acceso a ambos artefactos queda restringido al rol de revisión, cada acceso se registra en la auditoría, y los dos tienen plazo de retención declarado, vencido el cual se eliminan y el trabajo conserva solo los ítems ya extraídos. Cuando el documento de origen lo aporta un acudiente y trae impreso el nombre del estudiante, el sistema debe detectarlo en la extracción y tratar ese trabajo bajo el régimen de `PE-06` y `PV-03`: el nombre **no se propaga** a los ítems extraídos, ni a los kits, ni a las notificaciones, ni a ningún registro de operación. | La consola de revisión (`AD-04`) necesita los dos como paneles y hoy ninguno existe: el documento se lee en memoria y se descarta, y del modelo solo se conserva el fragmento ya parseado. Sin ellos el revisor no puede detectar un error de percepción, que es la clase de error que `PE-04` manda a esa cola, y no hay trazabilidad del kit al renglón que lo originó (`ML-06`). Se conservan en crudo porque el objeto del requisito es **auditar la percepción**: una salida depurada solo permite comprobar que el sistema depura, no que el modelo leyó bien. El artefacto no es dato personal por su propia naturaleza, que es un inventario de productos escolares por grado, y el único caso en que puede contenerlo está acotado y nombrado en la descripción. | Para cualquier trabajo terminado, el documento de origen se recupera íntegro y la salida sin procesar del modelo se recupera por página, **byte a byte igual a la respuesta original**, incluidas las páginas marcadas como incompletas. Un acceso por un rol sin permiso de revisión es rechazado y registrado. Al vencer el plazo de retención los dos artefactos se eliminan y el trabajo sigue siendo consultable. Sobre el corpus completo de listas se verifica por inspección que ningún nombre de estudiante detectado en un documento aportado por un acudiente aparece en los ítems extraídos, en los kits, en las notificaciones ni en los registros de operación. | Must | Percepción | v1 |

**Fila del Anexo C:**

> | `PE-07` | `RF` | F1 Cargar lista / F7 Validar mapeos | Percepción | Fase 3 | P recuperar origen y salida cruda; I inspección de nombre de menor |

**Por qué `Must`.** Criterio (a): es la precondición de `AD-04` y de `AD-06`, que son la puerta del
flujo principal. **No** se invoca el criterio (b), y eso es deliberado: al no ser el artefacto un
dato personal, `PE-07` no nace de una obligación legal. Lo que hace con la obligación legal es
respetarla en su caso de borde, que es distinto de derivar de ella.

**Nota de coherencia.** `PE-07` añade almacenamiento de objetos a la topología, lo que toca el
reparto del ADR 0014. Y aunque el artefacto no sea dato personal en el caso normal, su plazo de
retención y su control de acceso **sí** deben aparecer en `ANEXO_M_DATOS_PERSONALES.md`, con la
clasificación que corresponde a un artefacto que puede contener un dato sensible de forma
excepcional y la mención expresa del caso residual. Registrar ahí un artefacto que se declara no
personal puede parecer contradictorio y no lo es: el registro de tratamiento es donde se demuestra
que la clasificación se pensó, y un artefacto ausente del registro es indistinguible de uno que
nadie clasificó.

---

# Parte II — El artefacto validado reutilizable

Cuatro requisitos nuevos y uno que los habilita. Es el cambio de modelo del encargo: cuando un
admin valida los kits de una lista, el resultado queda como activo interno reutilizable para la
combinación colegio, sede, grado y año lectivo, y alimenta la vía "elijo colegio y grado".

La decisión de la usuaria, en sus palabras, es **activo interno reutilizable**, *"para la opción
del papá de buscar colegio y grado en vez de cargar la lista él mismo, con eso vamos llenando ese
flujo poco a poco a partir de la revisión"*. No se publica como lista oficial del colegio, porque
no se le puede atribuir al colegio algo que nunca envió. Eso resuelve la decisión abierta 5 de
`FLUJO_EXTREMO_A_EXTREMO.md` §7 a favor de su opción (b), y los cuatro requisitos de esta parte
son esa opción escrita.

El orden importa y es el inverso al intuitivo: `SC-06` va primero porque sin ventana de precio la
invalidación de `NR-09` no se puede definir, y sin `NR-09` la reutilización de `NR-07` es
insegura.

---

## E-34 — Añadir `SC-06`: ventana de validez del precio

**Severidad:** Alta.
**Sección:** §3.1 Módulo 1, Scraper y Catálogo, tras `SC-05`.
**Sustento:** `SC-02`, `SC-05`, `UI-04`, `UI-05`, `FU-03`, `FU-08` (E-10), `NR-09` (E-37), y
`servicios/catalogo/tukit_catalogo/modelos/oferta.py:150-207`.

`SC-02` exige actualizar el catálogo *"periódicamente"* y con más frecuencia en temporada.
`SC-05` exige excluir lo agotado. `UI-05` y `FU-03` exigen re-verificar precio y disponibilidad
antes de cobrar. Los cuatro hablan del precio y **ninguno dice cuánto tiempo un precio sigue
siendo válido**, que es la pregunta de la que depende todo lo demás.

Sin esa respuesta, el sistema tiene exactamente dos comportamientos posibles y los dos son
malos. O trata todo precio almacenado como bueno, y le muestra al padre un total que la
re-verificación va a desmentir en el checkout, que es el costo sorpresa que `UI-04` existe para
evitar y que la referencia de ClearSale y la CCCE identifica como causa principal de abandono de
carrito en Colombia. O re-consulta las tiendas en cada lectura, y entonces el caché progresivo
del catálogo no sirve de nada y cada kit cuesta una ráfaga de red.

La parte que hay que decir con precisión, porque corrige al análisis previo: **el esquema ya
está.** `precio_oferta` tiene `vigente_desde` y `vigente_hasta` (`oferta.py:173-174`), la
restricción `precio_vigencia_coherente` que impide un tramo que termine antes de empezar, un
índice único parcial que garantiza un solo precio abierto por oferta, y un comentario que
describe la restricción de exclusión de rangos que lo acompaña en Postgres con su razón: *"Sin
ella, 'el precio de hoy' es una consulta ambigua, que es exactamente lo que les pasaba a las dos
tablas de precio anteriores"* (`oferta.py:187-194`). La tabla incluso lo declara como decisión de
diseño: *"Un tramo de precio con vigencia, no una columna que se sobreescribe"*.

Lo que no existe es la **política**: quién escribe `vigente_hasta`, con qué plazo cuando la
tienda no publica uno, y qué hace el pipeline con un tramo vencido. Ese es el requisito.

#### Texto actual

> *(No existe. §3.1 termina en `SC-05`.)*

#### Texto de reemplazo

> | `SC-06` | `RF` | Cada precio observado debe almacenarse como un tramo con vigencia explícita, y el sistema debe fijarle un fin de vigencia al registrarlo: el que declare la tienda cuando lo declare, y en caso contrario un plazo por omisión configurable, distinto para temporada y fuera de temporada, coherente con la frecuencia de actualización de `SC-02`. Un precio cuyo tramo venció **no es un precio**: la línea que dependa de él no entra al total del kit, se marca como pendiente de re-precio y el sistema la vuelve a consultar; si la re-consulta falla, la línea se muestra sin precio en vez de con el último conocido. El plazo por omisión se versiona como configuración y no requiere desplegar código para ajustarse. | `SC-02`, `SC-05`, `UI-05` y `FU-03` hablan del precio y ninguno dice cuánto vale. Sin una ventana explícita el sistema solo puede tratar todo precio como bueno —y desmentir en el checkout el total que mostró, que es el costo sorpresa que `UI-04` existe para evitar— o re-consultar en cada lectura, anulando el catálogo como caché. Es además prerrequisito de la invalidación por capas de `NR-09`: sin ventana no hay forma de distinguir un precio que sigue bueno de uno viejo, y entonces hay que re-revisar todo o no re-revisar nada. | Todo tramo de precio del catálogo tiene fin de vigencia, verificado por consulta sobre el catálogo completo: cero tramos sin vencimiento fuera del tramo abierto vigente de cada oferta. Con un tramo forzado a vencido, la línea correspondiente queda fuera del total del kit, aparece marcada como pendiente de re-precio y no muestra el precio caducado. El plazo por omisión se cambia por configuración y el cambio surte efecto sin desplegar. | Alta | Scraper | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `SC-06` | `RF` | F8 Actualizar catálogo | Scraper | Fase 1 | P consultar tramos sin vencimiento; D forzar vencido y verificar exclusión del total |

**Por qué `Must`.** Criterio (a) como regla del camino infeliz. Un precio vencido tratado como
vigente hace que el sistema cobre mal, que es el enunciado literal del criterio. `FU-08` (E-10)
congela el precio en la reserva, y `SC-06` es lo que le dice a `FU-08` qué precio tiene derecho a
congelar.

**Alcance que el requisito deja fuera a propósito.** `SC-06` gobierna el precio **público
observado** de `catalogo`. El costo contractual que un mayorista le cobra a Tukit es otro dato,
vive en `comercio` y lo gobierna `PR-02`; el modelo advierte explícitamente que no se unifican
porque *"están en lados opuestos de la asimetría de recuperación"* (`oferta.py:154-158`).

---

## E-35 — Añadir `NR-07`: reutilización de la resolución validada

**Severidad:** Alta.
**Sección:** §3.3 Módulo 3, Normalización Semántica, tras `NR-06`.
**Sustento:** `AD-06` (E-31), `NR-01`, `OP-03`, `CO-01`, ADR 0012 §4, ADR 0018, y
`version_lista_oficial` con `item_lista_oficial` (`listas.py:63-206`).

Este es el requisito central del encargo, y su dificultad no está en la reutilización sino en
**decidir qué se reutiliza**. La respuesta se obtiene con una sola pregunta por cada cosa que el
pipeline produce: ¿esto depende del hogar?

| Depende de la lista — se reutiliza | Depende del hogar — no se reutiliza |
|---|---|
| La percepción de ese documento | Qué hijos hay y en qué grados |
| La normalización de renglón a concepto, con cantidad, unidad, tipo y modo de adquisición | Los pesos declarados de precio, marca, calidad y personaje |
| La resolución de concepto a producto por nivel, incluidos los anclajes manuales del admin | El tope de presupuesto por hijo |
| La clasificación de lo no comprable: licencia, en casa, diferido, uniforme, edición exclusiva | La consolidación entre hermanos y el reparto de empaques |
| Las instrucciones textuales del colegio | El personaje que quiere cada niño |
| El juicio humano sobre si el mapeo está bien | Los tres kits y cuál se recomienda |

La columna izquierda es idéntica para todos los padres de ese grado; la derecha cambia con cada
hogar. Y esa división cae **exactamente sobre las cuatro etapas del ADR 0018**: percepción,
normalización y resolución se reutilizan; **optimización no**. Que la frontera del requisito
coincida con una frontera que la arquitectura ya trazó por otras razones es la mejor señal de que
está en el sitio correcto.

De ahí sale la forma precisa del requisito: un trabajo que entra por "elijo colegio y grado"
sobre una lista ya validada **arranca en la etapa de optimización**, con sus tres primeras etapas
marcadas como satisfechas desde el artefacto compartido. La clave `(trabajo_id, etapa, intento)`
del ADR 0018 ya sabe saltar etapas completadas; lo nuevo es que la evidencia de completitud venga
de otra tabla.

Y hay que ser explícito sobre **qué es el artefacto**, porque el error fácil es reutilizar el
objeto equivocado. No es el trabajo: un `trabajo_pipeline` tiene el usuario, los hijos de ese
hogar y unos kits que dependen de sus pesos. Reutilizar un trabajo entre hogares sería reutilizar
precisamente lo que cambia. Lo reutilizable es la **resolución validada de la lista oficial** de
un `(colegio, sede, grado, anio_lectivo)`, que vive en `catalogo` por el argumento del ADR 0012
§4: *"una lista oficial es la demanda y el catálogo es la oferta"*. La demanda de un grado es la
misma para todos; lo que cambia por hogar es cómo se satisface.

Casi todo está construido. La firma de aprobación es `revisada_en` / `revisada_por`
(`listas.py:101-102`). El contenido es el conjunto de `item_lista_oficial`, cada uno con su
concepto o con un tipo que explique por qué no lo necesita. Y el modelo **ya impide aprobar algo
a medias**: la restricción `item_sin_concepto_va_a_revision` (`listas.py:203-205`) exige
`concepto_id IS NOT NULL OR requiere_revision`, y `cerrar()` (`descubrir.py:1105`) se niega a
marcar la versión como revisada si quedan propuestas pendientes, con el argumento de que un
renglón sin resolver *"dejaría el renglón mudo en todos los kits futuros de ese grado"* — una
frase escrita para el alta de productos que describe este requisito mejor que cualquier
paráfrasis.

Lo que falta es poco y es específico: `item_lista_oficial` resuelve a **concepto**, no a
producto, y eso es correcto, porque fijar el SKU en la lista sería congelar la oferta dentro de
la demanda. Pero hay decisiones del admin que no caben ni en el concepto ni en el catálogo global
—"para *esta* línea de *este* colegio el producto es *este* SKU y no el que el nivel elegiría",
el caso del libro con edición exigida y el del alta manual—, y esas necesitan una tabla de
anclaje de línea a producto, de bajo volumen, en `catalogo`.

#### Texto actual

> *(No existe. §3.3 termina en `NR-06`.)*

#### Texto de reemplazo

> | `NR-07` | `RF` | Cuando el Admin Tukit aprueba un trabajo (`AD-06`), el sistema debe conservar su resolución como artefacto validado reutilizable de la combinación colegio, sede, grado y año lectivo, compuesto por la versión de la lista con su firma de revisión y por sus renglones, cada uno con su concepto resuelto o con la marca que explique por qué no lo necesita, más los anclajes de línea a producto que el admin haya fijado. Un trabajo posterior sobre esa misma combinación —entre por selección de colegio y grado o por carga de un documento reconocido como esa lista (`NR-08`)— debe reutilizar las etapas de percepción, normalización y resolución desde el artefacto y **empezar en la etapa de optimización**, sin invocar al modelo de percepción, sin recuperación de candidatos y sin pasar por la cola de revisión. La optimización, la consolidación entre hermanos y la recomendación **no** se reutilizan nunca: dependen de los pesos, del tope de presupuesto, de los hermanos y de los personajes de cada hogar, y se recalculan siempre. `[NÚCLEO]` | La demanda de un grado es la misma para todos los padres de ese grado; lo que cambia por hogar es cómo se satisface. Hacer que cada padre pague una revisión humana por una lista que otro ya validó es trabajo repetido cuyo costo crece con el uso, justo al revés de lo que debería. La frontera entre lo reutilizable y lo que no coincide con las cuatro etapas del pipeline, de modo que el mecanismo de reanudación por etapa que ya existe la soporta sin estructura nueva. Y es lo que llena incrementalmente el catálogo de listas disponibles para la vía "elijo colegio y grado". | Ejecutado dos veces el mismo grado del mismo colegio con dos hogares distintos, el segundo trabajo no invoca al modelo de percepción —verificado por ausencia de llamada en la traza—, no entra a la cola de revisión, y produce kits **distintos** de los del primero cuando los pesos o el presupuesto de los dos hogares difieren. El segundo trabajo se completa en un orden de magnitud menos de tiempo que el primero. Un trabajo sobre una lista cuya versión no tiene firma de revisión **no** toma el camino corto. | Alta | Normalización + Catálogo | v1 |
>
> **MoSCoW:** Should.

**Fila del Anexo C:**

> | `NR-07` | `RF` | F2 Normalizar útiles / F6 Cargar lista oficial | Normalización + Catálogo | Fase 3 | D correr el mismo grado dos veces y verificar camino corto y kits distintos |

**Por qué `Should`.** El flujo `lista → kit → orden` se completa sin `NR-07`: toda lista pasa por
revisión, más despacio. No hay obligación legal y no condiciona la evidencia académica, que se
mide sobre el corpus anotado y no sobre el camino que el trabajo tomó. Es una capacidad de
eficiencia construida sobre datos que ya existen, degradable sin romper el producto.

Dicho eso, es el `Should` con mayor valor demostrable de la adenda, y conviene que quede escrito
por qué: es el único requisito de esta lista que se puede **mostrar** en una sustentación sin
explicarlo. Se corre el mismo grado dos veces y la segunda tarda segundos. El efecto de red que
produce ya está descrito en el propio código como principio del catálogo: *"La primera lista de
un colegio nuevo consulta tiendas por sus renglones raros; al aprobarlos quedan en catálogo, y la
siguiente lista los encuentra en casa. Las listas ya revisadas no consultan nada, nunca."*
`NR-07` extiende ese principio del producto a la lista.

**Nota sobre `OP-03` y el tiempo.** `OP-03` acota el flujo en cinco minutos de extremo a extremo
con progreso visible por etapa. El camino corto no invoca al modelo ni a la recuperación híbrida:
es una lectura y una optimización, y debería medirse en segundos. El contrato anuncia hoy un
`estimado_segundos` único; con `NR-07` esa estimación tiene que ser distinta por camino, o la
pantalla de espera miente en el caso bueno.

**Nota de coherencia con el ciclo editorial.** Para las líneas de tipo `texto` la resolución no
es un emparejamiento sino un lookup de `version_vigente(colegio, area, grado, anio)` a un ISBN.
Ese lookup ya es por colegio y por año, así que **ya es un artefacto compartido por
construcción**. El artefacto de la lista y el ciclo editorial resuelven la misma necesidad por
dos caminos, uno para útiles y otro para textos, y el modelo debería decirlo en vez de
duplicarlo.

**Nota de manifiesto.** La tabla de anclaje de línea a producto sube `meta.total_tablas_esperado`
de 70 a 71 y obliga a declarar en `[[referencias_cruzadas]]` que quien fijó el anclaje es un
usuario de `identidad`, o falla `test_fronteras.py`.

---

## E-36 — Añadir `NR-08`: procedencia visible del artefacto y reconocimiento de lista conocida

**Severidad:** Alta.
**Sección:** §3.3 Módulo 3, tras `NR-07`.
**Sustento:** `NR-07` (E-35), `CO-01`, `CO-02`, `NR-06`, `ML-02`, `FU-04` (Ley 1480 de 2011), y
`version_lista_oficial.hash_origen` (`listas.py:83`).

`NR-07` crea un artefacto que puede haber nacido de dos orígenes muy distintos: de una lista que
el colegio publicó por su panel (`CO-01`), o de un PDF que un acudiente subió y que un admin
validó. Los dos producen el mismo artefacto técnico y **no tienen la misma autoridad**, y
confundirlos es un defecto de un tipo particular: el acudiente no lo puede detectar. El contrato
lo formula así al hablar del riesgo de atribuir mal una lista: *"Ahí el acudiente no puede
detectar el error: confía en que la lista que le mostramos es la de su colegio"*
(`CONTRATO_API.md` §2.2). Un error que la víctima no puede ver no se corrige solo, y por eso la
procedencia tiene que ser un atributo del dato y no una nota de la interfaz.

La decisión de la usuaria es que la lista reconstruida **no se publica como lista oficial del
colegio**. Este requisito es esa decisión escrita, con su consecuencia en el modelo: hoy
`lista_oficial` tiene seis columnas —colegio, sede, grado, año, activa y su identificador
(`listas.py:48-56`)— y ninguna dice de dónde vino. Hace falta una columna, no una tabla.

La segunda mitad del requisito es el reconocimiento. Si un padre sube el PDF de un colegio cuya
lista ya está validada, debe recibir lo aprobado y no entrar a la cola. `hash_origen`
(`listas.py:83`) hace barato el caso común, que es el padre que descarga el mismo archivo del
sitio del colegio: un acierto de hash es identidad exacta. Cuando el hash no acierta y la lista
es la misma —una foto, un recorte, una reimpresión—, lo honesto es no adivinar. El acudiente es
el único actor que puede confirmarlo sin costo, y confirmarlo le cuesta un clic. Adivinar, en
cambio, pone al sistema a afirmar que un documento que no reconoció es la lista de un grado, que
es el mismo fallo de atribución por otra puerta.

#### Texto actual

> *(No existe.)*

#### Texto de reemplazo

> | `NR-08` | `RF` | Todo artefacto validado (`NR-07`) debe registrar su procedencia como atributo del dato, distinguiendo al menos si la lista la publicó el colegio por su panel (`CO-01`) o si se reconstruyó a partir del documento que aportó un acudiente y la validó el Admin Tukit. El sistema **no debe** presentar una lista reconstruida como lista oficial del colegio: al acudiente que la recibe se le muestra la procedencia en lenguaje llano, junto con la fecha de validación, y la posibilidad de aportar un documento más reciente. Cuando un acudiente sube un documento, el sistema debe intentar reconocerlo como una lista ya validada: por coincidencia exacta del contenido, que se resuelve sin preguntar, y cuando no la haya y la coincidencia sea solo probable, **proponiéndole al acudiente la lista candidata para que la confirme**, sin darla por buena por su cuenta. Un documento no reconocido sigue el camino largo. | Un artefacto nacido del PDF de un padre y uno publicado por el colegio tienen la misma forma y distinta autoridad. Atribuirle a un colegio una lista que nunca envió es un error que el acudiente no puede detectar, porque confía en que la lista que se le muestra es la de su institución. Reconocer el documento ya conocido es lo que le da a la reutilización su alcance real, ya que la mayoría de los padres sube el archivo que descargó del sitio del colegio. Y preguntar en vez de adivinar cuesta un clic al único actor que sabe la respuesta. | La procedencia de cualquier artefacto validado es consultable y se muestra al acudiente antes de que vea los kits, verificado con un artefacto de cada origen. Ninguna lista reconstruida se rotula como oficial del colegio en ninguna pantalla ni en ninguna respuesta de la API. Subir dos veces el mismo archivo hace que el segundo trabajo tome el camino corto sin preguntar. Subir una foto de la misma lista produce una propuesta de confirmación que el acudiente acepta o rechaza, y rechazarla manda el trabajo al camino largo. | Alta | Normalización + Catálogo | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `NR-08` | `RF` | F2 Normalizar útiles | Normalización + Catálogo | Fase 3 | D subir archivo idéntico y foto de la misma lista; I verificar rótulos de procedencia |

**Por qué `Must`, y en qué sentido es condicional.** `NR-08` no es exigible si `NR-07` no entra:
sin artefacto reutilizable no hay procedencia que declarar. Pero si `NR-07` entra, `NR-08` es
inseparable de él y no admite diferirse, porque lo que se diferiría es la salvaguarda y no la
capacidad. La priorización queda entonces así, y conviene escribirla sin eufemismos: **`NR-07` es
`Should` y puede no hacerse; si se hace, `NR-08` es `Must` y va en la misma entrega.** Un `Must`
condicionado a un `Should` es raro y aquí es correcto: la condición no es de calendario sino de
alcance.

El criterio es el (b), con una precisión sobre su fuerza. No se ampara en una norma que el SRS
cite para este caso —y conviene no fingir que sí—, pero la Ley 1480 de 2011, que el documento ya
invoca en `FU-04`, obliga a que la información al consumidor no lo induzca a error, y presentar
como institucional una lista que la institución no emitió es exactamente eso. Donde el amparo es
indiscutible es en el criterio (a): `NR-07` sin `NR-08` construye un mecanismo que afirma algo
falso sobre un tercero en cada uso.

---

## E-37 — Añadir `NR-09`: invalidación por capas del artefacto validado

**Severidad:** Alta.
**Sección:** §3.3 Módulo 3, tras `NR-08`.
**Sustento:** `NR-07` (E-35), `SC-06` (E-34), `AD-06` (E-31), `CO-01`, `SC-05`, y el índice
`uq_version_lista_vigente` (`listas.py:107-113`).

Aquí equivocarse es caro en las dos direcciones, y por eso el requisito no puede enunciarse como
"el artefacto se invalida cuando cambia algo". Re-revisar de más mata la eficiencia que `NR-07`
acaba de ganar; re-revisar de menos le manda al padre un precio o un significado que ya no
existe.

La salida es separar por capas, y el modelo ya está estratificado para eso. La regla que ordena
la tabla es una sola frase: **la revisión humana valida el significado, no el precio.** Que un
lápiz cueste 1.800 en vez de 1.700 no cambia que el renglón "1 lápiz negro" significa el concepto
lápiz.

| Capa | Qué guarda | Qué la invalida | ¿Re-revisión humana? |
|---|---|---|---|
| **Demanda** — `item_lista_oficial` | Renglón, concepto, cantidad, tipo | El colegio publica una versión nueva de la lista | **Sí**, y solo de los renglones que cambiaron |
| **Anclaje** — resolución validada | Línea a producto por nivel | El producto anclado se desactiva o sale del catálogo | **Sí**, y solo de esa línea |
| **Oferta** — `oferta_tienda` | Qué tienda lo vende | La oferta se cae | **No.** Recae a otra tienda del mismo producto |
| **Precio** — `precio_oferta` | Cuánto cuesta hoy | El tramo venció (`SC-06`) | **No.** Se re-precia, no se re-revisa |
| **Disponibilidad** — inventario | Si hay | Se agota | **No.** `SC-05` lo excluye del kit |

El caso duro es la lista nueva a mitad de año, y el modelo lo resuelve sin inventar nada: se crea
una versión con `numero + 1`, `vigente = true` y `revisada_en` nulo, y el índice único parcial
`uq_version_lista_vigente` (`listas.py:107-113`) fuerza a que la anterior deje de ser vigente. La
puerta se reabre para la versión nueva y no para la vieja, que es la semántica correcta: la vieja
sigue revisada y sigue siendo la verdad de lo que ya se compró contra ella, que es literalmente
la razón por la que la tabla está versionada —*"un acudiente que ya compró necesita saber contra
qué versión compró"* (`listas.py:65-68`)—. Lo que falta es la **comparación entre versiones**,
para no re-revisar los cuarenta renglones idénticos y revisar solo los tres que cambiaron. Sin
eso, corregir una línea cuesta una revisión completa, y nadie la va a hacer.

#### Texto actual

> *(No existe.)*

#### Texto de reemplazo

> | `NR-09` | `RF` | El sistema debe invalidar el artefacto validado (`NR-07`) por capas, y solo las capas afectadas, según esta regla: la revisión humana valida el significado y no el precio. Un tramo de precio vencido (`SC-06`), una oferta caída o un producto agotado se resuelven sin reabrir la revisión humana, re-preciando, recayendo a otra oferta del mismo producto o excluyendo del kit (`SC-05`). En cambio, una versión nueva de la lista publicada por el colegio y la desactivación de un producto anclado a una línea **sí** exigen revisión humana, y únicamente de los renglones afectados: al publicarse una versión nueva, el sistema debe compararla contra la anterior y encolar para revisión solo los renglones agregados, eliminados o modificados, conservando la validación de los idénticos. Las versiones anteriores conservan su firma de revisión y siguen siendo consultables como la resolución contra la que se compró. | Re-revisar de más anula la eficiencia que `NR-07` gana; re-revisar de menos le muestra al padre un precio o un significado que ya no existe. Separar por capas es lo que permite las dos cosas a la vez, y el modelo ya está estratificado así. Sin comparación entre versiones, publicar la corrección de una línea cuesta una revisión completa de la lista y en la práctica no se hace, de modo que la corrección del colegio no llega nunca a los padres. | Con un tramo de precio forzado a vencido, la versión conserva su firma de revisión y la línea se re-precia sin intervención humana. Con un producto anclado desactivado, solo la línea que lo anclaba queda pendiente de revisión y el resto de la lista sigue sirviendo el camino corto. Publicada una versión nueva que cambia tres renglones de cuarenta, la cola recibe tres renglones y los treinta y siete idénticos conservan su validación. La versión anterior sigue consultable con su firma. | Alta | Normalización + Catálogo | v1 |
>
> **MoSCoW:** Must.

**Fila del Anexo C:**

> | `NR-09` | `RF` | F2 Normalizar útiles / F6 Cargar lista oficial | Normalización + Catálogo | Fase 3 | D forzar cada evento de cada capa y verificar qué se re-revisa |

**Por qué `Must`, con la misma condicionalidad que `NR-08`.** No es exigible sin `NR-07`, e
inseparable de él si entra: un artefacto reutilizable sin regla de invalidación es un mecanismo
para servir datos vencidos a escala. Criterio (a).

**Dependencia dura, que es el orden de construcción.** `NR-09` no se puede definir sin `SC-06`:
la fila "Precio" de la tabla dice "el tramo venció", y sin ventana de validez esa condición no se
puede evaluar. Se dijo en la cabecera de la Parte II y se repite aquí porque es la dependencia
que el plan tiene que respetar.

**Los textos diferidos, que este requisito deja abiertos a propósito.** Un renglón de tipo
`diferido` es una obligación futura conocida: el colegio ya dijo que va a pedir algo y no dijo
qué. `CONTRATO_API.md` §1.1 promete que *"reabre el trabajo al publicarse"* y no hay código que
lo haga. `NR-09` **no** lo resuelve, y conviene decir por qué en vez de inventar una regla: la
respuesta depende de una decisión de negocio que no es de requisitos —si el piloto es de un solo
ciclo escolar, un texto diferido puede simplemente aparecer en la lista del año siguiente— y de
saber quién compró contra qué versión. Lo único que se puede afirmar sin decidir nada es que **no
debe reabrir el kit ya comprado**: el padre pagó lo que había. Queda como decisión abierta, y es
el único punto donde esta adenda deja algo sin cerrar.

---

## E-38 — Añadir `CO-05`: la aprobación del mapeo por el colegio como segunda puerta humana

**Severidad:** Media.
**Sección:** §3.7 Módulo 7, Panel Colegio, tras `CO-04` (E-08).
**Sustento:** `CO-02`, `CO-03`, `AD-06` (E-31), `NR-07` (E-35), `NR-08` (E-36), ADR 0018,
`version_lista_oficial.publicada_por` y `revisada_por` (`listas.py:88`, `:102`).

`CO-02` ya existe y dice más de lo que parece: el Panel Colegio *"debe mostrar el estado del
mapeo de su lista de útiles antes de publicarla al padre"*, con criterio *"puede ver el estado del
mapeo y **aprobarlo** antes de que llegue a los padres"*. O sea que el SRS ya previó **dos puertas
humanas sobre el mismo artefacto**, y nadie las ha distinguido.

No son la misma revisión y no las puede hacer la misma persona. El Admin Tukit valida que el
catálogo pueda responder la lista: sabe qué hay en el catálogo y no sabe qué quiso decir el
colegio. El colegio valida que la lista se interpretó como él la escribió: sabe lo que quiso decir
y no sabe ni le importa el catálogo. `CO-03` refuerza la asimetría al prohibirle al colegio ver
cualquier dato financiero, de modo que su vista es un subconjunto estricto.

La consecuencia para el modelo es directa y es la razón de este requisito: **`revisada_en` y
`revisada_por` no alcanzan.** Registran una firma y hacen falta dos, con semánticas distintas.
`publicada_por` ya existe y hoy significa "quién del colegio publicó esta versión", que es un
acto anterior y distinto de aprobar el mapeo; el propio modelo separa los dos conceptos y explica
por qué (`listas.py:94-96`). Modelar la segunda firma como un tercer par de columnas sería volver
a las banderas dispersas que el ADR 0018 rechaza; modelarla como un estado auditado de la misma
máquina es lo que ese ADR recomienda.

Y hay una restricción que el requisito **tiene** que llevar dentro, porque sin ella el requisito
rompe el negocio: hoy ningún colegio es cliente. Si la aprobación del colegio bloqueara la
entrega, el sistema no podría servir a nadie hasta cerrar el primer contrato institucional, y la
vía de entrada del acudiente —que es la que existe y funciona— quedaría muerta por un requisito
que describe un actor ausente. La puerta del colegio tiene que ser **exigible cuando el colegio
está vinculado y no bloqueante cuando no lo está**, y la diferencia tiene que ser visible en la
procedencia de `NR-08` y no escondida en una bandera de configuración.

#### Texto actual

> *(No existe. `CO-02` exige que el colegio pueda aprobar el mapeo y no lo distingue de la
> revisión del Admin Tukit.)*

#### Texto de reemplazo

> | `CO-05` | `RF` | El sistema debe modelar la aprobación del mapeo por parte del colegio (`CO-02`) como una firma distinta e independiente de la revisión del Admin Tukit (`AD-06`), sobre el mismo artefacto validado y con semántica propia: el Admin Tukit certifica que el catálogo puede responder la lista, y el colegio certifica que la lista se interpretó como él la escribió. Las dos firmas se registran como estados auditados con su autor, su marca de tiempo y su alcance, y ninguna sustituye a la otra. Cuando el colegio está vinculado a la plataforma, su aprobación es exigible antes de que el artefacto se ofrezca a los padres de ese grado. Cuando no lo está, la ausencia de esa firma **no bloquea** la entrega: el artefacto se sirve con la firma del Admin Tukit y su procedencia declarada (`NR-08`), y la aprobación del colegio queda pendiente y se puede recoger después sin repetir la revisión del admin. La vista del colegio no incluye ningún dato financiero ni de pago (`CO-03`). | `CO-02` ya exige la aprobación del colegio y el modelo solo tiene una firma, de modo que hoy las dos revisiones se confunden en una columna. Son juicios distintos que ninguna persona puede emitir a la vez: el admin conoce el catálogo y no la intención; el colegio conoce la intención y no el catálogo. Y hacerla bloqueante mataría la operación, porque hoy ningún colegio está vinculado y la vía que funciona es la del acudiente: un requisito no puede dejar el sistema inservible describiendo un actor que todavía no existe. | Un artefacto validado registra por separado quién lo revisó por Tukit y quién lo aprobó por el colegio, con sus marcas de tiempo, y las dos firmas son consultables de forma independiente. Con un colegio vinculado, el artefacto no se ofrece a los padres de ese grado sin la firma del colegio. Con un colegio no vinculado, el artefacto se sirve con la sola firma del Admin Tukit y la procedencia visible, y recoger después la firma del colegio no vuelve a abrir la revisión del admin. Un usuario del rol del colegio no puede leer ningún dato de órdenes ni de pago, verificado por prueba de acceso cruzado. | Media | Colegio | v1 |
>
> **MoSCoW:** Should.

**Fila del Anexo C:**

> | `CO-05` | `RF` | F6 Cargar lista oficial / F7 Validar mapeos | Colegio + Catálogo | Fase 5 | D firmar por ambas puertas; P acceso denegado a datos financieros |

**Por qué `Should`.** `CO-02` ya es `Alta` y ya exige la capacidad; `CO-05` no la crea, la separa
de la del admin y fija su carácter no bloqueante. Lo que aporta sobre lo ya exigido es precisión
de modelo, no funcionalidad: el flujo cobra y entrega sin ella, con la firma del admin. No hay
obligación legal y no toca la evidencia académica.

**Nota sobre el actor ausente, que es un hallazgo de gobierno y no de este requisito.**
`apps/colegio/` no existe, `ARQUITECTURA.md` §1 la declara *"pendiente de portar"*, y el plan
vigente no la menciona: su reparto por microservicio nombra `apps/web` y `apps/admin` y omite la
tercera. Se está planificando un producto de dos actores para una arquitectura de tres. `CO-05`
está redactado para que **no dependa** de que `apps/colegio` exista: su mitad exigible vive en
`catalogo` como segunda firma, y la pantalla del colegio es lo que la recoge cuando exista.

---

# Parte III — El aviso y la factura

Los dos encargos que ya estaban redactados, y lo que les falta.

---

## E-39 — Añadir `FU-11`: aviso con enlace de WhatsApp que porta el número de solicitud, y caducidad

**Severidad:** Media.
**Sección:** §3.8 Módulo 8, Fulfillment y Pagos, tras `FU-10` (E-28).
**Sustento:** `FU-02`, `FU-10` (E-28), `AD-06` (E-31), `SC-06` (E-34), `SC-02`, `PV-02`,
`PV-04` (E-11), `CONTRATO_API.md` §10.

`FU-10` (E-28) ya fija el canal: puerto `Notificador` con correo y `wa-link` en v1, y el envío
proactivo diferido a v2 con su argumento —el `wa-link` no depende de aprobación de plantillas y no
arriesga el bloqueo de un número por envío no solicitado—. Eso está bien resuelto y no se
reescribe.

Lo que `FU-10` no dice es lo que este encargo pide, y son dos cosas.

**La primera es el número de solicitud.** El `wa-link` invierte la dirección de la conversación:
la plataforma no admite que el sistema escriba primero, así que **el acudiente envía siempre el
primer mensaje**. Eso tiene una consecuencia operativa que hay que diseñar y no descubrir: ese
primer mensaje llega a un buzón donde nadie sabe quién escribe. El correo del acudiente está en el
trabajo, no en WhatsApp, y el número desde el que escribe puede no ser el que registró. Si el
mensaje precargado no porta el identificador de la solicitud, quien atiende el buzón tiene que
preguntar por el colegio, el grado y el nombre del niño para encontrar el trabajo, que es
exactamente la fricción que el canal existía para quitar —y preguntar por el nombre del niño es
además lo que `PE-06` y `PV-03` trabajan para evitar—. El contrato ya lo insinúa al escribir
`?text=<mensaje con turno>` (`CONTRATO_API.md:516`) y el plan lo llama "número de turno", pero
ninguno lo exige ni dice qué debe poder hacerse con él.

**La segunda es la caducidad**, que `FLUJO_EXTREMO_A_EXTREMO.md` §7 dejó como decisión abierta 2
—*"¿cuánto vale un aviso al que el papá nunca responde, y cuándo caduca?"*—. El encargo pide una
respuesta razonada, y esta es, con su razonamiento a la vista para que se pueda discutir en vez de
aceptar.

*El aviso no debería caducar por su cuenta*, porque no hay nada en el aviso que se degrade. Lo que
se degrada es el **precio**, y eso ya lo gobierna `SC-06`. Anclar la caducidad del aviso a la
ventana de precio más corta del kit es la única regla que no inventa un plazo: el aviso vale
mientras lo que promete siga siendo cierto. Esa es la respuesta principal y de ella sale el resto.

*Sobre la insistencia*, la restricción de la plataforma da la respuesta. No se puede empujar por
WhatsApp, así que insistir solo es posible por correo, y una escalera corta es mejor que una
larga: el aviso al aprobar, y un único recordatorio por correo a las 72 horas. Después, nada. No
por timidez comercial sino porque insistir en un canal que el destinatario no inició es lo que
hace que un remitente acabe en la carpeta de correo no deseado, y porque el acudiente que no
contestó en tres días no está esperando un cuarto mensaje.

*Sobre el plazo absoluto*, 30 días, y el argumento es del catálogo y no del calendario: `SC-02`
actualiza el catálogo al menos mensualmente, de modo que una solicitud de más de un mes está hecha
contra un catálogo que ya se re-raspó completo. Revivirla no es leer un dato viejo, es recalcular.

Y aquí es donde la Parte II paga: **caducar es barato**. Una solicitud caducada no destruye el
artefacto validado, porque el artefacto es por lista y no por hogar (`NR-07`). Revivir una
solicitud caducada cuesta un re-precio y una optimización, no una revisión humana. Un sistema sin
`NR-07` tendría que elegir entre guardar kits vencidos o botar trabajo humano; con `NR-07` no
tiene que elegir. Es la mejor evidencia de que la Parte II no es solo eficiencia.

Queda un último punto, y es de datos personales. Una solicitud que caduca sin pago retiene el
correo y el celular de un acudiente cuya finalidad de tratamiento terminó. Eso **no** necesita
requisito nuevo: `PV-02` y `PV-04` (E-11) ya lo gobiernan. `FU-11` solo nombra el evento que
dispara el plazo, que es lo que faltaba.

#### Texto actual

> *(No existe. `FU-10` (E-28) define el puerto y los canales; no define el contenido del enlace ni
> el ciclo de vida del aviso.)*

#### Texto de reemplazo

> | `FU-11` | `RF` | El aviso al acudiente de que sus kits están listos (`AD-06`) debe enviarse por los canales del puerto `Notificador` (`FU-10`) y, en el caso del enlace de WhatsApp, el mensaje precargado debe portar el número de solicitud del trabajo, de forma que quien atienda el canal identifique la solicitud sin pedirle al acudiente ningún otro dato y en particular sin pedirle el nombre del menor. El número de solicitud se le muestra al acudiente desde que crea el trabajo y es el mismo en todos los canales. El aviso tiene ciclo de vida declarado: se emite al aprobarse la revisión, se reitera **una sola vez** por correo a las 72 horas si el acudiente no ha abierto sus kits, y no se reitera más. La solicitud caduca cuando vence la ventana de validez de precio más corta de su kit recomendado (`SC-06`) o a los 30 días de emitido el aviso, lo que ocurra primero. Caducar no destruye el artefacto validado que la resolvió: revivir una solicitud caducada exige re-preciar y volver a optimizar, y **no** una nueva revisión humana. | El enlace de WhatsApp invierte la dirección de la conversación —la plataforma exige que el acudiente escriba primero—, de modo que el primer mensaje llega a un buzón donde nadie sabe quién escribe: sin el número de solicitud en el mensaje, atenderlo obliga a preguntar colegio, grado y nombre del niño, que es la fricción que el canal existía para quitar y un dato que el sistema trabaja para no tratar. Y un aviso sin caducidad declarada deja el sistema prometiendo precios que ya no valen. Anclar la caducidad a la ventana de precio es la única regla que no inventa un plazo: el aviso vale mientras lo que promete siga siendo cierto. Un solo recordatorio, y por correo, porque no se puede empujar por WhatsApp y porque insistir en un canal que el destinatario no inició es lo que hace que se bloquee al remitente. | El mensaje precargado del enlace de WhatsApp contiene el número de solicitud, y ese número basta para recuperar el trabajo, verificado desde un número de teléfono distinto del registrado por el acudiente. Un acudiente que no abre sus kits recibe exactamente dos comunicaciones y no una tercera. Con la ventana de precio del kit recomendado forzada a vencida, la solicitud pasa a caducada y sus kits dejan de mostrarse con precio. Revivir una solicitud caducada produce kits nuevos sin pasar por la cola de revisión, verificado por ausencia de entrada en la cola. Los datos de contacto de una solicitud caducada sin pago se suprimen al vencer su plazo de retención (`PV-04`). | Media | Fulfillment / Operación | v1 |
>
> **MoSCoW:** Should.

**Fila del Anexo C:**

> | `FU-11` | `RF` | F4 Visualizar kit / F9 Ciclo de la orden | Fulfillment / Operación | Fase 4 | D recuperar solicitud por el número desde otro teléfono; D forzar caducidad y revivir |

**Por qué `Should`.** Coherente con `FU-10`, que E-28 dejó en `Should` con el argumento de que
`FU-02` ya obliga a la confirmación por correo y que el puerto y el segundo canal son mejora de
producto. `FU-11` aporta el identificador en el mensaje y el ciclo de vida: sin él el aviso llega
igual, solo que atenderlo cuesta más y los kits no vencen nunca. La mitad con peso legal —la
supresión del contacto de una solicitud caducada— **no** la carga `FU-11`: ya es `Must` por
`PV-04`, y `FU-11` únicamente nombra el evento que la dispara. Decirlo así evita inflar la
prioridad de este requisito con una obligación que ya está enunciada en otro sitio, que es un
truco fácil y un defecto de trazabilidad.

---

## E-40 — Añadir la dependencia `[D5]`: la factura electrónica exige un obligado a facturar

**Severidad:** Alta.
**Sección:** §2.6 Suposiciones y Dependencias, tras `[D4]`. Y nota de coherencia en el racional de
`FU-09` (E-27).
**Sustento:** `FU-09` (E-27), `[D4]`, ADR 0011.

No hace falta un requisito de facturación electrónica: **`FU-09` ya está redactado** en E-27, con
el patrón de puerto con adaptador, el proveedor autorizado intercambiable, el adaptador simulado
para pruebas y la regla de que un fallo del facturador crea un Caso y no revierte un pago ya
cobrado. Está bien hecho y no se toca.

Lo que le falta es la parte incómoda, y el encargo pide señalarla con honestidad. E-27 declara
`FU-09` **`Must`** con este argumento: *"Cae en el criterio b de §1.1 sin ambigüedad: obligación
legal. Una venta sin factura electrónica no es una venta incompleta, es una venta que
incumple."* El argumento es correcto **y está incompleto**, porque la obligación de facturar no
recae sobre un sistema: recae sobre un **obligado a facturar**. La DIAN exige factura electrónica
a quien vende teniendo NIT y habilitación como facturador electrónico. Sin negocio constituido no
hay nada que emitir, y lo que el proyecto puede demostrar es la integración, no el cumplimiento.

Esto no es una objeción a `FU-09`: es la razón por la que su criterio de aceptación está bien
escrito. E-27 exige que *"el flujo de checkout pueda ejecutarse de extremo a extremo en pruebas
con el adaptador simulado sin depender del proveedor real"*, o sea que el requisito **es
verificable sin NIT**. Lo que falta es decir en las dependencias por qué eso es suficiente, para
que nadie lea `Must` y concluya que el piloto académico emite facturas válidas.

El SRS ya tiene el precedente exacto de cómo se escribe esto. `[D4]` decía que PSE/ePayco
*"requiere registro empresarial y certificación de Tukit como comercio"* y lo declaraba bloqueante
del Módulo 8; E-02 lo reformula al entrar Wompi. `[D5]` es la misma figura para la facturación, y
su efecto es simétrico: bloquea la emisión válida, no la construcción ni la verificación.

#### Texto actual

> *(§2.6 termina en `[D4]`. Ni la facturación electrónica ni la DIAN aparecen en las dependencias,
> pese a que E-27 introduce `FU-09` como `Must` por obligación tributaria.)*

#### Texto de reemplazo

> **`[D5]`** — La emisión de una factura electrónica **válida** exige que Tukit esté constituida,
> tenga NIT y esté habilitada como facturador electrónico ante la DIAN, y que exista contrato con
> un proveedor de facturación autorizado. Es una dependencia **externa y bloqueante de la
> emisión**, no de la construcción: `FU-09` se implementa y se verifica de extremo a extremo
> contra el adaptador simulado del puerto de facturación, igual que `FU-03` se verifica contra el
> adaptador falso de la pasarela. Mientras `[D5]` no se satisfaga, el sistema entrega al acudiente
> un comprobante interno de la compra, declarado expresamente como no fiscal, y el puerto de
> facturación queda conectado al adaptador simulado. La transición al proveedor real no cambia el
> dominio de Comercio: es un cambio de adaptador y de configuración.

**Nota de coherencia que hay que añadir al racional de `FU-09`:** la prioridad `Must` de `FU-09`
se sostiene sobre la obligación tributaria del negocio, y su criterio de aceptación se satisface
con el adaptador simulado. Las dos cosas son compatibles y conviene escribirlas juntas: el
requisito es `Must` porque el día en que Tukit venda tendrá que facturar, y es verificable hoy
porque lo que se verifica es que el sistema **sepa** facturar cuando se le conecte el proveedor.
Sin esa frase, un evaluador que lea `Must` y pregunte por la factura del piloto encuentra una
promesa que el proyecto no puede cumplir, y la respuesta correcta —"la integración está construida
y probada; la emisión depende de `[D5]`"— parece una excusa en vez de una decisión tomada.

---

## 8. Lo que queda fuera de esta ronda, declarado

El encargo excluye explícitamente dos capacidades, y conviene que la exclusión quede escrita para
que no se lea como olvido.

**El front generativo con chat** y **la gamificación con personaje** no tienen requisito en esta
adenda y se mantienen como **alcance diferido**. Ninguna de las dos tiene requisito en la línea
base tampoco: `UI-03` cubre intercambiar un ítem por una alternativa del catálogo con
re-verificación de precio, que es otra cosa, y el personaje solo aparece como criterio del perfil
Fan y como objetivo de la optimización, con el SRS poniendo al niño como *"Influenciador · sin
acceso al sistema"* en su tabla de actores. Están en el radar de producto y no en esta ronda. La
regla que lo hace defendible es la misma que ordena todo este documento: en un documento
calificable, implementar sin requisito rompe la trazabilidad, y levantar un requisito para algo
que no se va a construir este semestre infla el conteo de `Must` sin mejorar el producto.

Queda además **una** decisión abierta que esta adenda no cierra, y está señalada en E-37: qué hace
exactamente un texto diferido cuando llega. Se explica ahí por qué no se puede redactar sin una
decisión de negocio previa.

---

## 9. Trazabilidad: a qué servicio y a qué capítulo va cada requisito

El encargo pide las dos columnas. La de servicio sigue el reparto de `ARQUITECTURA.md` §1, que
manda sobre todo lo demás por su propia regla de §0; la de capítulo sigue `Memoria/PLAN_MEMORIA.md`.

| Requisito | Servicio de `ARQUITECTURA.md` §1 | Aplicación | Capítulo de la memoria | ADR de respaldo |
|---|---|---|---|---|
| `AD-04` consola de tres paneles | `inteligencia` (trabajo y etapas) | `apps/admin` | Desarrollo de la solución (percepción, bucle humano) | 0018 |
| `AD-05` fuera de stock / no provisto | `catalogo` (oferta y línea) + `comercio` (inventario) | `apps/admin` | Desarrollo; Diseño (vista de datos) | 0012 |
| `AD-06` visto bueno del admin | `inteligencia` (máquina de estados) + `catalogo` (firma) + `operacion` (auditoría) | `apps/admin` | Desarrollo; Diseño (vista de procesos) | 0018, 0002 |
| `AD-07` alta manual, tres fuentes | `catalogo` (propuesta y resolución) + `ingesta` (raspado) | `apps/admin` | Diseño (catálogo canónico de tres capas); Desarrollo | 0012, 0003 |
| `PE-07` persistencia de origen y salida cruda | `inteligencia` + almacenamiento de objetos | — | Desarrollo (percepción); Análisis del problema (datos personales) | 0014, 0018 |
| `SC-06` ventana de validez del precio | `catalogo` + `ingesta` | — | Diseño (preparación de datos); Resultados | 0012, 0017 |
| `NR-07` reutilización de la resolución validada | `catalogo` (artefacto) + `inteligencia` (camino corto) | `apps/web` | Diseño (vista de datos); Desarrollo (las cuatro etapas) | 0012, 0018 |
| `NR-08` procedencia y reconocimiento | `catalogo` (columna `origen`, `hash_origen`) + `inteligencia` | `apps/web` | Diseño; Descripción general (modelo B2B2C) | 0012 |
| `NR-09` invalidación por capas | `catalogo` + `inteligencia` | — | Diseño (vista de datos); Resultados (defectos corregidos) | 0012, 0017 |
| `CO-05` segunda puerta humana | `catalogo` (segunda firma) + `identidad` (rol con ámbito) | `apps/colegio` | Diseño (autorización con ámbito, matrícula como ancla) | 0013, 0016, 0008, 0018 |
| `FU-11` aviso con número de solicitud y caducidad | `operacion` (puerto `Notificador`) + `comercio` | `apps/web` | Desarrollo; Descripción general (actores) | 0004, 0011 |
| `[D5]` dependencia de facturación | `comercio` (puerto de facturación) | — | Conclusiones (limitaciones); Análisis del problema (dependencias) | 0011 |

Dos observaciones que salen de armar esta tabla y que valen por sí solas.

**El capítulo de la memoria que más se beneficia no es el de requisitos.** `NR-09` y `SC-06`
pertenecen naturalmente a la sección que `PLAN_MEMORIA.md` propone como *"un capítulo que no
estaba previsto y conviene escribir"*: los defectos encontrados y corregidos. La invalidación por
capas y la ventana de precio no son funcionalidades vistosas; son la demostración de que el
proyecto se preguntó qué pasa cuando su propio caché miente. El argumento de ese capítulo —*"una
tesis que demuestra que midió su propio sistema, encontró que estaba mal y lo corrigió acredita
más método que una que presenta un diseño impecable que nunca se auditó"*— les aplica tal cual.

**`CO-05` es el único que traza a una aplicación que no existe**, y eso es información y no un
problema del requisito. Se redactó a propósito para que su mitad exigible viva en `catalogo` como
segunda firma, de modo que se pueda construir y probar antes de que `apps/colegio/` exista.

---

## 10. Comprobación después de aplicar, y el orden que no se puede invertir

### 10.1 Orden de aplicación documental

1. **`ENMIENDA_SRS.md` completa, E-01 a E-28.** Esta adenda numera desde E-29 y cita `CO-04`,
   `FU-08`, `FU-09` y `FU-10` como existentes. Aplicarla antes produce citas a requisitos que el
   documento no tiene, que es el defecto que ambos documentos existen para corregir.
2. **Esta adenda, E-29 a E-40.**
3. **`tukit/docs/CORRECCIONES_TRAZABILIDAD.md`**, cuya columna "código correcto tras la adenda"
   solo es válida después de los dos pasos anteriores.

### 10.2 Orden de construcción, donde hay tres dependencias duras

Ninguna es de preferencia y las tres se violan fácil:

- **`PE-07` antes de `AD-04`.** Dos de los tres paneles no tienen datos hasta que algo los
  persista. El error natural es empezar por la pantalla, que es la parte visible.
- **`SC-06` antes de `NR-09`.** La fila "Precio" de la invalidación por capas dice "el tramo
  venció"; sin ventana esa condición no se puede evaluar.
- **La máquina de estados del ADR 0018 antes de `AD-06`.** `AD-06` es una transición de esa
  máquina. Construirla encima de banderas booleanas obliga a rehacerla, y el plan vigente pone esa
  tarea de penúltima.

### 10.3 Comprobaciones sobre el documento

```bash
textutil -convert txt -stdout Arquitectura/SRS_ISIS2610G19_v3.docx \
  | rg -o 'AD-0[4-7]|PE-07|SC-06|NR-0[7-9]|CO-05|FU-11' | sort | uniq -c
```

Cada uno de los once debe aparecer **al menos dos veces**: una en la tabla de su módulo en §3 y
otra en el Anexo C. Un requisito que aparece una sola vez es un requisito sin trazabilidad, que es
exactamente lo que E-18 levanta contra `DP-03` y `DP-04` en la línea base actual.

```bash
textutil -convert txt -stdout Arquitectura/SRS_ISIS2610G19_v3.docx | rg -n '\[D5\]|DIAN'
```

`[D5]` debe aparecer en §2.6 y citado en el racional de `FU-09`, y no en ningún otro sitio.

### 10.4 Documentos que comparten contenido y hay que cruzar

| Documento | Qué cruzar |
|---|---|
| `MOSCOW_REQUISITOS.md` | El conteo pasa de **120** —el resultado de la enmienda— a **131**: entran siete `Must` (`AD-04`, `AD-05`, `AD-06`, `PE-07`, `SC-06`, `NR-08`, `NR-09`) y cuatro `Should` (`AD-07`, `NR-07`, `CO-05`, `FU-11`). La proporción de `Must` pasa de 68,3 % a **67,9 %**, o a **66,1 %** aplicando además la consolidación de duplicados de E-23. Es la primera enmienda que **no** sube la proporción de `Must`, y conviene decir por qué: cuatro de los once nuevos son mejoras de producto y no obligaciones, que es la forma que tiene un documento de crecer sin degradar su priorización |
| `tukit/arquitectura/manifiesto.toml` | `NR-07` añade la tabla de anclaje de línea a producto: `meta.total_tablas_esperado` de 70 a 71, más la referencia cruzada a `identidad.usuario`. `NR-08` añade la columna `origen` a `lista_oficial`, que no cambia el conteo. `PE-07` añade almacenamiento de objetos, que no es tabla pero sí topología |
| `ANEXO_M_DATOS_PERSONALES.md` | `PE-07` introduce el plazo de retención del documento de origen y `FU-11` el de los datos de contacto de una solicitud caducada. Los dos necesitan fila en el registro de tratamiento con finalidad, base legal y plazo |
| `ATAM_Tukit.tex` | `SC-06` y `NR-09` son escenarios de modificabilidad y de correctitud del árbol de utilidad; `NR-07` es un escenario de rendimiento con dos caminos de latencia muy distintos, que es más interesante que el actual de un solo camino |
| `WBS_Tukit_ISIS2610G19_v3.csv` | Once requisitos nuevos necesitan paquete de trabajo. Sin ellos, esta adenda comete el defecto que el ADR 0009 corrigió y que la Parte VII de la enmienda señala como su comprobación más importante: **alcance declarado sin trabajo presupuestado** |
| `tukit/arquitectura/CONTRATO_API.md` | No se toca aquí. Sus correcciones están en `CORRECCIONES_TRAZABILIDAD.md`, y son aplicables cuando el agente de backend termine la v1.1 |

---

## 11. Lo que no verifiqué

Por honestidad, y para que nadie construya sobre esto sin comprobarlo.

- **Que el `.docx` v3 sea la versión aprobada.** Es la más reciente, es la que
  `MOSCOW_REQUISITOS.md` cuenta y es la que `PLAN_MEMORIA.md` declara insumo del capítulo de
  análisis del problema. No encontré un acta que la declare línea base formal; `ACTA_APROBACION_OE1.md`
  y `ACTA_APROBACION_OE2.md` están en el repo y no los leí completos.
- **Que las celdas del Anexo C sean correctas.** Coteje el Anexo C contra el cuerpo **por
  identificador**, no celda por celda: no verifiqué que la función `F1` a `F11` ni el método de
  verificación de cada fila sean los adecuados. Lo que sí medí es la cobertura, y da un desajuste
  en las dos direcciones: el cuerpo define **99** códigos, el Anexo C tiene **76** filas, **25
  requisitos definidos no tienen fila** y **2 filas no tienen requisito** (`DP-03` y `DP-04`, §1).
  Los 25 huérfanos no son aleatorios y ahí está lo útil: son `BD-01` a `BD-05`, `CF-01`, `CF-02`,
  `DI-01`, `ML-02` a `ML-09`, `MT-01`, `MT-02`, `PT-01`, `PT-02`, `RD-03` y `SG-01` a `SG-04`, o
  sea **casi exactamente los requisitos que §3.10 a §3.12 escriben como lista de viñetas en vez de
  como tabla**. Los que esas mismas secciones ganaron después en formato tabular —`SG-05`,
  `SG-06`, `DI-02`, `PV-01` a `PV-03`— **sí** tienen fila. La hipótesis evidente es que la matriz
  se llenó desde las tablas y nadie volvió por las viñetas. Eso hace que `E-05`, que ya propone
  tabular §3.10 a §3.12, cierre la mayor parte de este hueco como efecto secundario; lo que E-05
  no dice es que además hay que añadir las 25 filas. No lo levanto como cambio numerado porque
  pertenece a E-05 y no a esta adenda, pero contradice el criterio "Trazable" que §5.1 del propio
  SRS declara *"Verificado"*, así que conviene que quien aplique E-05 lo sepa.
- **`CONTRATO_API.md` v1.1.** Leí la v1.0. Si la extensión ya añadió endpoints de catálogo, la
  tabla de correcciones del documento hermano puede necesitar filas nuevas; las existentes siguen
  siendo válidas porque están ancladas por texto citado y no solo por número de línea.
- **Los plazos que propongo en `FU-11`.** Las 72 horas y los 30 días son razonados, no medidos. El
  argumento de los 30 días se apoya en la periodicidad de `SC-02` y es el más firme de los dos; el
  de las 72 horas es una convención defendible y no un dato. Si hay analítica de apertura de
  correo del piloto, ese número debería salir de ahí.
- **Que `[D5]` describa bien el régimen de la DIAN.** Describo la obligación a grandes rasgos y no
  cito resolución. Antes de congelar la línea base conviene corroborarlo en una fuente pública, que
  es la misma cautela que E-21 exige para la Resolución 17821 de 2023 y por la misma razón: una
  norma citada y no verificada es lo que un jurado comprueba en dos minutos.



