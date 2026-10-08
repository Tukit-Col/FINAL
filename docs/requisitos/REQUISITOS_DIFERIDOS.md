# Proveedores mayoristas y contenido editorial — los diecinueve requisitos que el plan ignora

- **Tipo:** inventario de estado. No decide nada y no planifica nada.
- **Fecha:** 2026-09-22.
- **Línea base:** `Arquitectura/SRS_ISIS2610G19_v4.docx`, §3.15 (Módulo 10, Canal Comercial) y
  §3.16 (Módulo 11, Contenido Editorial).
- **Por qué existe este documento.** Los módulos 11 y 12 del SRS v3 —renumerados a 10 y 11 en el
  v4— aportan **diecinueve requisitos**, y el plan vigente
  (`pipeline_end-to-end_monorepo_4a4ee99a.plan.md`) **no menciona ninguno**. Seis de ellos dejaron
  de estar diferidos: el cambio E-14 de `ENMIENDA_SRS.md`, ya incorporado al v4, los trajo a
  **v1**. O sea que hoy hay seis requisitos de alcance vigente sin paquete de trabajo, sin dueño y
  sin aparecer en el plan que gobierna la construcción. Alguien tiene que decidir sobre ellos, y no
  puede decidir sobre lo que no ve reunido en un sitio.

---

## 0. El resumen, y por qué el número que importa es seis

| Estado en el v4 | Requisitos | Cuántos |
|---|---|---:|
| **v1 · Should · sin paquete de trabajo** | `ED-01`, `ED-03`, `ED-04`, `ED-05`, `ED-06`, `ED-08` | **6** |
| **v2 · Won't (v1)** · canal mayorista completo | `PR-01` a `PR-09` | 9 |
| **v2 · Won't (v1)** · mitad externa del editorial | `ED-02`, `ED-07`, `ED-09`, `ED-10` | 4 |
| | **Total** | **19** |

Los trece diferidos no son un problema: están declarados `v2` en su propia columna `Ver.`, con su
razón escrita, y el plan puede ignorarlos legítimamente. **Los seis de v1 sí son un problema**, y
de un tipo preciso: son alcance declarado sin trabajo presupuestado, que es exactamente el defecto
que el ADR 0009 corrigió cuando retiró la aplicación móvil nativa. La Parte VII de
`ENMIENDA_SRS.md` lo anticipó y lo dejó escrito como su comprobación más importante: *"el módulo
editorial parcial (E-14) necesita paquete de trabajo en la fase 4. **Sin él, esta enmienda crea el
mismo defecto que el ADR 0009 corrigió**"*. Esa comprobación está **sin hacer**.

Y hay un agravante que no es del módulo sino del actor: los seis los opera **el Panel Colegio**,
que es la aplicación que `ARQUITECTURA.md` §1 declara *"pendiente de portar"* y que el plan
tampoco menciona. No es que falte un paquete de trabajo: falta el actor que ejecuta los seis.

---

## 1. Los seis que están en v1 y nadie ha planificado

Entraron por E-14, cuyo argumento conviene resumir porque es lo que sostiene que sean v1 y no v2.
El lienzo de propuesta de valor del segmento colegio estableció que **los tres dolores mejor
documentados de la institución no tenían aliviador en v1**: el tiempo que consume evaluar textos,
la cobertura insuficiente de la oferta editorial frente al Bachillerato Internacional, y la ventana
de tres días para definir la lista. Mientras tanto, los aliviadores sí construidos atacaban dolores
que todavía son hipótesis. El encaje estaba invertido, y estos seis lo corrigen con lo mínimo.

El corte es **por actor**, y eso es lo que los hace baratos: entra la mitad que el colegio opera
sobre sí mismo, que no añade ningún tipo de inquilino nuevo, ningún ámbito de autorización nuevo y
ningún canal de notificación saliente.

| REQ | Qué hace en v1 | Dolor que ataca | MoSCoW | Dónde se implementa |
|---|---|---|---|---|
| `ED-01` | El Admin Colegio o el Admin Tukit registra las ediciones que las editoriales le han ofrecido, con título, área, grado y capítulos, y marca la versión vigente por área y grado. **Sin portal de autoservicio para la editorial** | Precondición de los otros cinco | Should | `catalogo` (`edicion_libro`, `version_vigente`) + `apps/colegio` |
| `ED-03` | Comparativo entre la versión vigente y la propuesta, con capítulos agregados, eliminados o modificados | **DC2**, el dolor mejor documentado del segmento: evaluar textos consume más tiempo que armar la lista de papelería | Should | `catalogo` + `apps/colegio` |
| `ED-04` | Aprobación total de la versión propuesta | DC2 | Should | `catalogo` (`propuesta_version`) + `apps/colegio` |
| `ED-05` | Aprobación **parcial por capítulos** | **DC3**: la oferta editorial no cubre el programa de Bachillerato Internacional. Es lo más cercano a un aliviador que Tukit puede ofrecer ahí: no cubre el hueco curricular, pero hace gestionable y registrable la adopción parcial que el colegio ya practica cuando ninguna edición le sirve completa | Should | `catalogo` + `apps/colegio` |
| `ED-06` | Rechazo con motivo obligatorio | DC2. Cierra el ciclo de decisión | Should | `catalogo` + `apps/colegio` |
| `ED-08` | Historial de versiones por materia y grado, con quién aprobó, cuándo y con qué alcance | **DC1**: la ventana de tres días. Es lo que hace que el año siguiente arranque de lo ya decidido en vez de un formato en blanco, que es el único ataque real a esa ventana | Should | `catalogo` + `apps/colegio` |

### 1.1 El dato que hace barato el paquete de trabajo

Las cuatro tablas que sostienen el módulo —`edicion_libro`, `version_vigente`, `propuesta_version`
y `configuracion_colegio_editorial`— **ya están** entre las diecinueve de `catalogo` en el esquema
objetivo y en `tukit/arquitectura/manifiesto.toml`. El esquema nunca difirió el módulo: lo que se
difirió fue la interfaz y el flujo. Y en el código ya existen los modelos: `modelos/editorial.py`
define `configuracion_colegio_editorial` con su `dias_ventana_decision` y su `politica_silencio`, y
`propuesta_version` con `vence_en`, `resuelta_por` y sus estados.

Lo que no existe es **ninguna línea de código de aplicación**: `FLUJO_EXTREMO_A_EXTREMO.md` §2.4
verificó que `propuesta_version` solo aparece en `tests/test_editorial.py`. El ciclo donde la
editorial propone y el colegio decide en tres días está modelado y no se puede ejecutar.

Así que el paquete de trabajo que falta no es "diseñar el módulo editorial": es exponer un modelo
que ya está, sobre una aplicación que no existe. Las dos mitades tienen costos muy distintos y
conviene no promediarlas al estimar.

### 1.2 La decisión que alguien tiene que tomar

Hay tres salidas y las tres son defendibles. No se recomienda ninguna aquí porque es una decisión
de alcance y de calendario, no técnica.

**(a) Crear el paquete de trabajo en la WBS y construirlos.** Es lo que E-14 supone. Cierra el
encaje del segmento colegio, que es la única motivación institucional verificada —el rector
condiciona la asociación a *"las editoriales y el Bachillerato Internacional"*— y arrastra la
creación de `apps/colegio`, que el lock ya declara pendiente. Es la salida coherente con el
documento tal como está.

**(b) Devolverlos a v2 con un cambio registrado.** Si el calendario no admite `apps/colegio`, lo
honesto es revertir E-14 en el v4 y dejar constancia del motivo, en vez de dejar seis requisitos v1
sin construir. Un requisito v1 no construido es peor que uno v2 declarado: el primero es un
incumplimiento y el segundo es una decisión.

**(c) Partir el corte una vez más: solo `ED-01` y `ED-08`.** Registrar las ediciones ofrecidas y
conservar el historial de decisiones es lo que ataca DC1, y es lo que menos interfaz necesita:
podría vivir en `apps/admin` operado por el Admin Tukit en nombre del colegio, sin esperar a
`apps/colegio`. Los cuatro de comparación y decisión (`ED-03` a `ED-06`) sí piden la pantalla del
colegio. Es la salida que conserva más valor por menos trabajo, y la que no está escrita en ningún
sitio.

**Lo que no es opción** es dejarlos como están: seis requisitos de alcance vigente que el plan no
nombra y que ninguna aplicación existente puede ejecutar.

---

## 2. Los nueve del canal mayorista, que siguen diferidos con razón

`PR-01` a `PR-09` son **Won't (v1)** y `v2`, y la razón es doble y consta por escrito. Primera: la
columna `Ver.` del propio SRS los marcaba `v2` desde el v3, de modo que es un diferimiento ya
tomado dentro del documento. Segunda, y es la que importa: el catálogo de v1 se construye por
scraping (`SC-01`), así que **ningún eslabón del flujo `lista → kit → orden` depende de que exista
un proveedor mayorista registrado**.

| REQ | Qué es | Por qué sigue diferido |
|---|---|---|
| `PR-01` | Registrar proveedor y condiciones comerciales negociadas | Es la palanca de margen identificada, pero el MVP opera con catálogo scrapeado y precio público observado |
| `PR-02` | El proveedor carga su lista de precios mayoristas | Depende de `PR-01`. Y hay una barrera de campo verificada: el canal mayorista cotiza por WhatsApp y publica precio en cero |
| `PR-03` | Generar pedido mayorista por demanda proyectada | Requiere una serie de demanda que el piloto todavía no produce |
| `PR-04` | El proveedor confirma o rechaza el pedido | Depende de `PR-03` |
| `PR-05` | El proveedor reporta inventario disponible | Depende de `PR-01`. El inventario que el MVP necesita es el del catálogo público, que `SC-05` ya cubre |
| `PR-06` | Registrar costo de compra y calcular margen | **Es el primero de la fila si el canal se abre.** Ver §2.1 |
| `PR-07` | Comparar costo por canal y marcar la fuente activa | Depende de que haya dos canales vivos |
| `PR-08` | Historial de pedidos y facturación del proveedor | Depende de `PR-01`. **Es el requisito que el plan citó correctamente** y que el análisis previo desmintió por error |
| `PR-09` | Confidencialidad de las condiciones entre proveedores | Es condición de entrada del módulo, no una función suya: sin ella no se puede abrir el canal |

### 2.1 `PR-06` merece una nota, porque responde una pregunta ya abierta

De los nueve, `PR-06` es el único que contesta algo que el proyecto **ya tiene sobre la mesa**: la
hipótesis H6 del modelo de negocio está en tensión con la evidencia, porque el 70 % de los
acudientes no pagaría más de un 5 % de sobreprecio frente al 15 % de comisión que el modelo
financiero asume. Registrar el costo de compra y calcular el margen por producto es lo que
permitiría saber si el negocio cierra sin ese sobreprecio.

Eso no lo vuelve v1 —no es eslabón del flujo, no es obligación legal y no condiciona la evidencia
académica—, pero sí lo vuelve **el primero de los nueve** si el canal mayorista se abre, y conviene
que el orden quede escrito y no se redescubra.

---

## 3. Los cuatro editoriales que quedan fuera, y dónde cae el corte

| REQ | Qué es | Por qué queda Won't (v1) |
|---|---|---|
| `ED-02` | La editorial propone directamente al profesor | Exige a la editorial como **actor externo autenticado**, con su propio ámbito de autorización y su aislamiento frente a otras editoriales. Es un tipo de inquilino nuevo, y abrirlo sin el equivalente de `PR-09` sería repetir el error que el canal mayorista tiene identificado como condición de entrada |
| `ED-07` | Notificar el resultado a la editorial | No tiene destinatario dentro del sistema mientras `ED-02` esté fuera |
| `ED-09` | El rector restringe el acceso directo de editoriales | Es la compuerta de `ED-02`. Sin la puerta no hace falta la compuerta. La tabla `configuracion_colegio_editorial` se crea igual, porque ya está en el esquema, pero sin requisito que la gobierne en v1 |
| `ED-10` | Vigencia mínima acordada de un texto | Su propósito es frenar propuestas demasiado frecuentes, que es el dolor DC13, de intensidad **baja** y que el colegio ya se autogestiona con una regla propia. Sin `ED-02` no hay flujo de propuestas que frenar |

El corte es coherente y conviene poder defenderlo en una sola frase: **entra lo que el colegio hace
sobre sí mismo, queda fuera lo que exige a un tercero autenticado.** Y sigue siendo útil recortado
porque el hecho de campo lo permite: las editoriales **ya vienen al colegio por su cuenta**
—*"ellos mismos vienen a ofrecer los productos"*—, así que el contacto comercial existe fuera del
sistema. Lo que no existe es el registro de la evaluación y de la decisión, y eso es justamente lo
que entra.

---

## 4. Los actores que estos requisitos necesitan, y que también faltan

Conviene mirarlo por actor y no por módulo, porque es donde se ve el tamaño real del hueco.

| Actor | Estado en el v4 | Estado en el código | Requisitos que lo esperan |
|---|---|---|---|
| **Profesor** | Actor de v1. E-15 le quitó la marca de diferido y le dio alcance: *"decide sobre las ediciones de texto de su materia"* | No existe. Ni rol sembrado ni pantalla | `ED-03` a `ED-06` |
| **Rector / Admin Colegio** | Actor de v1, con `CO-01` a `CO-05` más `ED-01` y `ED-08` | El rol `rector` y el permiso `lista_oficial:publicar` existen **solo en tests** de `identidad` | `CO-01` a `CO-05`, `ED-01`, `ED-08` |
| **Proveedor** | `v2`. E-15 le corrigió la marca en esta ronda | No existe | `PR-01` a `PR-09` |
| **Editorial** | `v2`, declarado expresamente *"no es actor del sistema en v1"* | No existe | `ED-02`, `ED-07` |

Los dos primeros son de v1 y no existen. Es el mismo hallazgo que
`FLUJO_EXTREMO_A_EXTREMO.md` §2.4 levantó sobre el colegio —*"el rol está diseñado con más cuidado
que casi cualquier otra parte del sistema y tiene cero líneas de código de aplicación"*— y la
consolidación lo agrava, porque ahora el actor tiene ocho requisitos de v1 en vez de tres.

---

## 5. Qué hay que cruzar, y con quién

| Documento | Qué falta |
|---|---|
| `WBS_Tukit_ISIS2610G19_v3.csv` | **Paquete de trabajo para `ED-01`, `ED-03` a `ED-06` y `ED-08`.** Es la comprobación que la Parte VII de `ENMIENDA_SRS.md` declara como la más importante de su lista, y está sin hacer. Sin ella el v4 tiene alcance declarado sin trabajo presupuestado |
| `pipeline_end-to-end_monorepo_4a4ee99a.plan.md` | El reparto por microservicio no nombra `apps/colegio` ni ninguno de los diecinueve requisitos. Con seis de ellos en v1, la omisión pasa de ser un desalineamiento a ser un hueco de alcance |
| `MOSCOW_REQUISITOS.md` | Su §2.21 y §2.22 marcan los diecinueve como `Won't (v1)`. Seis ya no lo son: hay que moverlos a `Should` para que el conteo cuadre con el del v4 (89 Must, 26 Should, 3 Could, 13 Won't) |
| `Arquitectura/ARQUITECTURA.md` | §8.2 omite `colegio` del C4 nivel 2, contradiciendo su propia §1. Con ocho requisitos de v1 colgando de ese panel, la inconsistencia del diagrama ya no es cosmética |
| `Arquitectura/VPC_COLEGIOS.md` | Es el origen del cambio. Conviene marcar en su §4.3 y §4.4 qué dolores quedaron con aliviador tras E-14, para que el lienzo refleje el alcance vigente |

---

## 6. Lo que no verifiqué

- **Que las cuatro tablas editoriales estén completas para sostener `ED-03` a `ED-06`.** Comprobé
  que existen en el manifiesto y en `modelos/editorial.py`, no que sus columnas basten para el
  comparativo de capítulos, que es lo que `ED-03` necesita y lo más probable que falte.
- **El esfuerzo.** No estimo jornadas. `FLUJO_EXTREMO_A_EXTREMO.md` §5.4 estima el ciclo editorial
  ejecutable (su hueco C6) en 3–4 jornadas y `apps/colegio` en 6–10, pero esas cifras son de antes
  de que E-14 trajera seis requisitos a v1 y no las he revisado contra el alcance nuevo.
- **La marca de los nueve `PR` en el Anexo C del v4.** Las cambié de `v14 (pendiente)` a
  `v2 (diferida)` por coherencia con el retiro de la marca `v14`, y no comprobé que "diferida" sea
  el término que el resto del expediente usa para la columna de fase de verificación.
