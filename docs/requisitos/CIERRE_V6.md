# SRS v5.0 → v6.0: una sola taxonomía, y el choque de `OP-03` cerrado

- **Tipo:** registro de aplicación. Documenta una operación ya ejecutada.
- **Fecha:** 2026-09-22.
- **Entrada:** `Arquitectura/SRS_ISIS2610G19_v5.docx`, **intacto**.
- **Salida:** **`Arquitectura/SRS_ISIS2610G19_v6.docx`**, con copia en `ENTREGA_FINAL/SRS/`.
- **Qué cierra:** la alternativa B para `OP-03` y `NR-07`, y la unificación de la taxonomía de §3
  sobre el reparto canónico de la arquitectura.
- **Comprobación reutilizable:** `Arquitectura/scripts/verificar_srs.py`. Sustituye a las
  comprobaciones que antes se corrían a mano y añade la que faltaba.

---

## 0. La comprobación, ahora reutilizable, y lo que encontró en la primera pasada

El encargo pedía convertir en herramienta la comprobación que nació de los tres defectos de
búsqueda. Está en **`Arquitectura/scripts/verificar_srs.py`**, con siete bloques: integridad del
paquete, formato conservado contra la versión anterior, estructura, correspondencia
requisitos ↔ Anexo C, validez de la taxonomía, **ubicación de cada edición**, y ausencia de
etiquetas retiradas. Devuelve código de salida 1 si algo falla, de modo que se puede encadenar.

```bash
python Arquitectura/scripts/verificar_srs.py Arquitectura/SRS_ISIS2610G19_v6.docx \
  --contra Arquitectura/SRS_ISIS2610G19_v5.docx --ubicaciones ubic.json
```

El bloque que importa es `verificar_ubicaciones`: para cada par *(fragmento, sección esperada)* sube
del párrafo editado hasta su encabezado numerado y afirma que coincide. El docstring del módulo
enumera los tres defectos que lo justifican, para que nadie lo borre por parecer redundante.

**Y valió la pena en la primera pasada: encontró un defecto mío.** Había añadido `DP-06` a §3.9 y
**no le había puesto fila en el Anexo C**. Lo detectó la comprobación de correspondencia en
segundos —132 requisitos contra 131 filas, faltando `DP-06`—. Es exactamente el defecto que E-18
levantaba contra `DP-03` y `DP-04` en la línea base v3, o sea que lo habría reintroducido en el
mismo documento que lo corrigió. Corregido antes de guardar.

Esa es la diferencia entre una comprobación y una lectura: la lectura de este documento ya la había
hecho y no lo vi.

---

## 1. `OP-03` y `DP-06`: la alternativa B aplicada

### 1.1 `OP-03` re-encuadrado

El defecto era interno: la **descripción** acotaba *"el motor"* y el **criterio** acotaba *"de
extremo a extremo"*, dos objetos que difieren por un factor de casi cuarenta (8 s contra 300 s). Un
requisito cuyo enunciado normativo y cuyo criterio miden cosas distintas no es verificable, porque
no se sabe qué hay que medir para aprobarlo. Y además duplicaba a `DP-03`, que ya posee el p95 del
optimizador.

La descripción pasa a ser:

> El sistema debe entregar los tres kits al acudiente en un tiempo que no afecte negativamente su
> experiencia, medido **de extremo a extremo** y con progreso visible por etapa mientras dura el
> procesamiento. Este requisito acota el flujo completo; el tiempo de cada etapa por separado lo
> acotan `DP-03` (optimización), `DP-04` (percepción) y `DP-06` (camino corto sobre lista validada).

El criterio no cambia: conserva el tope de cinco minutos, que es la cifra que `CONTRATO_API.md` §0
cita como fundamento de que la API sea asíncrona. Eso era el argumento para preferir B sobre C, y se
respeta: **ninguna cifra citada fuera del SRS se movió**, de modo que este cambio no crea trabajo en
el contrato, que es el archivo que no podemos editar.

### 1.2 `DP-06`, que nace declarándose provisional

Es la parte que el encargo marcó como la que no se puede perder al redactar, y está dentro del
requisito y no en una nota al pie, para que sobreviva a cualquier copia parcial:

> **`DP-06`** — Un trabajo que reutiliza la resolución validada de `NR-07` y arranca en la etapa de
> optimización […] debe completarse con un p95 ≤ **30 s** […]. **El valor es derivado y no medido, y
> el requisito nace declarándose provisional:** se obtuvo sumando al tope de 8 s del motor (`DP-03`)
> una holgura para la lectura del artefacto validado, y no se puede medir todavía porque el camino
> corto no está construido. Se re-mide en cuanto exista, y el p95 resultante sustituye este valor.

Su criterio de aceptación repite la condición en el sitio donde un verificador la va a leer:
*"Mientras el camino corto no esté construido el requisito no es medible y se verifica por análisis
del presupuesto de etapas; esa condición debe constar en el informe de verificación en vez de darse
el umbral por satisfecho."*

La razón conserva el argumento que hace que el número no sea arbitrario: **30 s es exactamente un
orden de magnitud por debajo de los 300 s de `OP-03`**, de modo que el criterio relativo de `NR-07`
—*"un orden de magnitud menos que el primero"*— queda satisfecho por construcción y deja de depender
de lo que tardó el primer trabajo, que varía con el documento.

`MoSCoW: Should`, heredado de `NR-07`: no se puede exigir el tiempo de un camino que puede no
construirse. `Servicio: inteligencia · catalogo`. Con su fila en el Anexo C, tras el susto de §0.

---

## 2. Una sola taxonomía: el reparto canónico de la arquitectura

### 2.1 La decisión de alcance que tuve que tomar, y por qué

El encargo dice **siete microservicios**. Apliqué **diez unidades**: los siete servicios más las
tres aplicaciones cliente, y conviene explicar por qué antes de nada, porque es la única parte donde
leí la intención por encima de la letra.

`ARQUITECTURA.md` §1 declara los siete servicios **y**, en el mismo sitio, las tres aplicaciones,
diciendo expresamente que estas *"no son servicios de dominio"*. Y hay **veinte requisitos que son
sobre el cliente y no sobre un servicio**: `UI-01` a `UI-07`, `AD-01` a `AD-07`, `PT-02`, `UM-04` y
la mitad de interfaz de varios más. `UI-06` exige un presupuesto de rendimiento del navegador —LCP
≤ 2,5 s e INP ≤ 200 ms en el percentil 75— y **ningún servicio de backend puede cumplirlo**:
asignarlo a `gateway` sería falso y asignarlo a `inteligencia` sería peor.

Así que la elección real era entre forzar una sexta parte del documento a un dueño que no le
corresponde, o tomar las diez unidades que el mismo documento maestro declara en la misma sección.
Tomé la segunda: **sigue siendo una sola taxonomía y una sola fuente**, con diez entradas en vez de
siete. Es reversible si se prefiere lo contrario, y el criterio de reversión sería explícito: habría
que decidir a qué servicio se le atribuye el rendimiento del navegador.

### 2.2 Qué cambió, en números

| | |
|---|---:|
| Requisitos cuya celda cambió de valor | **131** de 132 |
| Requisitos cuya celda ya era canónica | 1 (`DP-06`, escrito ya con la nueva) |
| Cabeceras de columna renombradas de `Módulo` a `Servicio` | 22 tablas + Anexo C |
| Filas del Anexo C normalizadas | 132 |
| Etiquetas de la taxonomía retirada que sobreviven en rol de clasificador | **0** |

La columna ahora se llama **`Servicio`** y no `Módulo`, porque seguir llamándola `Módulo` mientras
contiene nombres de servicio era la mitad del problema anterior.

### 2.3 Qué hice con `Transversal` (15) y `Todos` (6)

Las dos desaparecen. No eran unidades del reparto, eran etiquetas de agregación, y conservarlas
habría sido conservar la taxonomía paralela con otro nombre.

**La regla que las sustituye: un requisito que aplica a varias unidades las enumera, separadas por
` · `, usando solo nombres canónicos.** Enumerar es más verboso y es lo que hace la celda
**verificable**: un script puede afirmar que cada token de cada celda es uno de los diez, y eso es
un invariante mucho más fuerte que una palabra especial que significa «varias». Es precisamente la
comprobación `verificar_taxonomia`, que antes del cambio reportaba 131 celdas con valores ajenos y
después reporta cero.

Los repartos que resultaron, con su criterio:

- **Los diez que aplican a los siete servicios** enumeran los siete: `DI-01`, `DI-02`, `DP-02`,
  `DP-05`, `MT-01`, `MT-02`, `MT-03`, `PT-01`, `RD-03` y `SG-02`. Son requisitos de plataforma
  —disponibilidad, carga, pruebas, contenedores, fronteras, autorización— que por definición se
  cumplen o se incumplen en cada desplegable.
- **Los cuatro que aplican a los cinco almacenes con dato propio** enumeran esos cinco: `BD-02`,
  `BD-03`, `PS-03` y `PV-04`. No son los siete porque `ingesta` no tiene base y `gateway` no tiene
  dominio, así que una obligación sobre entidades o sobre supresión no les puede aplicar. Esa
  distinción es la que `Transversal` borraba.
- **Los demás se repartieron nominalmente.** `SG-04`, por ejemplo, pasó de `Transversal` a
  `identidad · comercio · inteligencia · operacion`: los cuatro almacenes que llegan a contener dato
  personal, y el tercero está ahí por la evidencia que `PE-07` persiste. `PV-03` pasó a
  `inteligencia · catalogo · identidad · operacion`, que son los cuatro sitios donde el dato de un
  menor puede llegar a escribirse o a salir hacia un tercero. `BD-05` pasó a
  `catalogo · inteligencia · comercio`, que son exactamente los tres almacenes de las seis consultas
  que el propio requisito enumera.

### 2.4 La Tabla 4, rehecha

De 12×12 a **12×11**: las once funciones `F1`–`F11` contra las diez unidades, con abreviaturas
`cat int ing com ope ide gw web adm col` y leyenda. La rejilla suma los 9.405 twips exactos de ancho
útil.

El cambio de eje **resuelve por sí solo el límite que la versión anterior tenía que declarar**:
`identidad`, `operacion` y `gateway` ya tienen columna, y `F11` puede marcar `identidad`, que es
donde viven el consentimiento y el ejercicio de los derechos, en vez de aparecer con una sola marca
en la interfaz. `gateway` aparece en `F1` y `F5`, que son las dos funciones donde el acudiente
atraviesa la puerta con una carga y con un pago.

### 2.5 Lo que no cambió, y por qué no es el problema anterior

**Los títulos de sección de §3 siguen agrupando por capacidad**: `3.2 Módulo 2 - Percepción`,
`3.8 Módulo 8 - Fulfillment y Pagos`. Eso es deliberado y hay un argumento decisivo: **los prefijos
de los códigos se derivan de esa agrupación.** `PE-`, `NR-`, `OP-`, `SC-`, `UI-`, `AD-`, `CO-` y
`FU-` *son* la taxonomía funcional. Renombrar las secciones sin renumerar los códigos dejaría a los
códigos huérfanos; renumerarlos invalidaría **todas** las citas de `CONTRATO_API.md`, de
`tukit/apps/**`, de `tukit/libs/**`, del plan, de `ARQUITECTURA.md` y de la propia tabla de
correcciones, que es un trabajo de otro orden de magnitud y con mucho más riesgo que beneficio.

Para que eso no se lea como la ambigüedad de antes, **se amplió la nota de alcance de §3 declarando
los dos ejes y qué contesta cada uno**: la sección agrupa por capacidad y de ahí sale el prefijo del
código; la columna `Servicio` nombra la unidad de despliegue que implementa el requisito. El defecto
anterior no era que existieran dos ejes: era que **una misma columna** mezclaba los dos, de modo que
`Percepción` y `Identidad` convivían como si fueran la misma clase de cosa. Ahora cada eje tiene su
sitio y su vocabulario.

---

## 3. Lo que reveló el cambio de taxonomía

Es la parte más interesante y no la buscaba. Al repartir los 132 requisitos por unidad y separar
**participación** de **propiedad exclusiva**, el reparto sale así:

| Unidad | Total | Único dueño | Compartido | Por enumeración |
|---|---:|---:|---:|---:|
| `inteligencia` | 62 | **16** | 32 | 14 |
| `catalogo` | 50 | 3 | 33 | 14 |
| `comercio` | 50 | **13** | 23 | 14 |
| `identidad` | 40 | 6 | 20 | 14 |
| `operacion` | 27 | **0** | 13 | 14 |
| `ingesta` | 16 | 1 | 5 | 10 |
| `apps/web` | 15 | 4 | 11 | 0 |
| `apps/admin` | 15 | 1 | 14 | 0 |
| `gateway` | 14 | **0** | 4 | 10 |
| `apps/colegio` | 11 | **0** | 11 | 0 |

Cinco cosas que salen de ahí.

**1. `operacion` no tiene ni un requisito propio, y eso es un hueco real.** Participa en 27 y no es
dueño único de ninguno. El lock le da **cinco dominios** —casos, PQRS, notificaciones, auditoría y
telemetría— y una política de recuperación exigente. Pero en el SRS esos dominios solo aparecen como
**efecto colateral de otros requisitos**: `FU-07` abre un Caso, `ML-06` exige trazabilidad, `FU-10`
notifica. Ninguno especifica el Caso como capacidad, con su ciclo de vida, su asignación y su cierre.
Y lo verificable es peor: **la palabra «PQRS» aparece cero veces en el SRS** mientras
`ARQUITECTURA.md` la menciona tres veces como dominio de `operacion`; «telemetría» aparece una vez.
O sea que hay un servicio con despliegue propio, base propia y política de respaldo propia cuyo
dominio **no está especificado en ninguna parte**. Eso no es un problema de tabulación: es un hueco
de requisitos que el eje funcional escondía, porque «Operación» no era un módulo de §3 y por tanto
nadie echaba de menos su sección.

**2. `gateway` con cero requisitos propios es lo correcto, y conviene decirlo para que no se lea como
lo mismo.** El lock dice literalmente que `gateway` es *"sin dominio"*. Un servicio sin dominio no
debe poseer requisitos de dominio, así que sus 14 apariciones —diez por enumeración de plataforma y
cuatro compartidas: `CF-01`, `SG-05`, `SG-06`, `OP-03`— son exactamente lo que se espera. **El mismo
número, cero, significa cosas opuestas en `gateway` y en `operacion`**, y sin separar propiedad de
participación no se distinguirían.

**3. `catalogo` participa en 50 requisitos y es dueño único de 3.** Es la firma de un servicio que es
la dependencia de todos: la lista, el producto, el precio y los embeddings los consume el resto.
No es necesariamente un defecto —un catálogo es por naturaleza el sustrato compartido—, pero
significa que **el SRS casi nunca especifica las obligaciones propias de `catalogo`**: la frescura de
los embeddings, la calidad de la curaduría, el grafo de sustituibilidad y los 99 conceptos no tienen
requisito. Solo `SC-04`, `BD-01` y `ED-10` hablan de él sin hablar de otro.

**4. `ingesta` tiene un solo requisito propio: `SC-03`**, el del `robots.txt` y el límite de una
petición por segundo. Es el único servicio que sale a la red, el único candidato a otro lenguaje, y
el que sostiene la tercera fuente de `AD-07`, y su especificación completa es una restricción de
buena conducta. Diez de sus dieciséis apariciones son enumeraciones de plataforma.

**5. Dos tercios de los requisitos nombran más de una unidad: 88 de 132.** Es el dato de fondo y
tiene una explicación que el propio lock da: `ARQUITECTURA.md` §1.2 concede que la separación en
servicios **no** se justifica por rendimiento sino por recuperabilidad asimétrica, frontera de
cumplimiento y perfil de recurso, que son criterios **operativos**. Los requisitos, en cambio, son
funcionales. Los dos ejes son genuinamente ortogonales, así que es coherente —y no un defecto— que
la mayoría de los requisitos cruce fronteras de servicio. Lo que sí hace falta es que el documento lo
diga, para que una celda con tres nombres no se lea como indecisión, y eso quedó escrito en la nota
de §3.

---

## 4. Verificación del v6

Corrida con `Arquitectura/scripts/verificar_srs.py`. **Todas las comprobaciones pasan.**

| Bloque | Resultado |
|---|---|
| A · `.zip` sin errores de CRC, todo el XML parsea, `updateFields` presente | ✅ |
| B · partes del paquete iguales al v5; `styles.xml`, `numbering.xml`, tema, fuentes, encabezado, pie e imágenes **byte a byte intactos** | ✅ |
| C · 40 tablas en un solo estilo; 30 pies numerados consecutivamente | ✅ |
| D · requisitos ↔ Anexo C | **132 ↔ 132**, sin repetidos, sin huérfanos en ninguna dirección |
| E · taxonomía: los 132 usan solo nombres canónicos | ✅ (antes del cambio: 131 con valores ajenos) |
| F · cada edición en la sección que declara | 8 de 8 ✅ |
| Etiquetas retiradas en rol de clasificador | **0** en las 132 celdas de requisito y las 132 del Anexo C |
| Tabla 4 | 12×11, rejilla = 9.405 twips = ancho útil exacto |

El índice sigue mostrando los números de página del v5 hasta que Word lo regenere; `updateFields` lo
resuelve al abrir. Es la misma nota de siempre.

---

## 5. Lo que queda abierto sobre el v6

| Qué | Dónde | Bloqueado por |
|---|---|---|
| **`operacion` sin dominio especificado**: ni PQRS, ni ciclo de vida del Caso, ni requisitos del registro de auditoría ni de telemetría | §3.1 de este documento | Decisión de alcance: levantar requisitos o declarar los dominios fuera de v1 |
| `TOPE_PAGINAS = 40` frente al presupuesto de `OP-03` | `CORRECCIONES_TRAZABILIDAD.md` §5 | Quien posee `servicios/**` |
| Re-medir `DP-04` con ≥10 documentos en cuota de producción | `CIERRE_V5.md` §1.3 | Cuota de producción del proveedor |
| Medir `DP-06` cuando el camino corto exista | §1.2 de este documento | Que `NR-07` esté construido |
| Obligaciones propias de `catalogo` sin requisito (frescura de embeddings, curaduría, sustituibilidad) | §3.3 de este documento | Decisión de alcance |
| Partir `SG-05` en dos requisitos (faltante `RF-13`) | `CONSOLIDACION_SRS_V4.md` §3 | Nada; es redacción |
| Paquete de trabajo para los seis requisitos editoriales de v1 | `REQUISITOS_DIFERIDOS.md` | Decisión de alcance |
| Aceptar formalmente los ADR 0012, 0013 y 0014 | `CORRECCIONES_TRAZABILIDAD.md` §7.5 | Nada |
| Registrar el artefacto de `PE-07` en `ANEXO_M_DATOS_PERSONALES.md` | `ADENDA_REQUISITOS_SRS.md` E-33 | Nada |
| Actualizar el conteo de `MOSCOW_REQUISITOS.md` a 132 | `REQUISITOS_DIFERIDOS.md` §5 | Nada |

---

## 6. Lo que no verifiqué

- **Que el v6 se vea bien en Word.** Verifiqué integridad, estilos byte a byte, XML y ubicación de
  cada edición; **no lo he abierto en Word**. La Tabla 4 con once columnas y las celdas de `Servicio`
  que enumeran siete nombres son lo que más conviene mirar a ojo: esas celdas son largas y pueden
  ensanchar filas de las tablas de requisitos.
- **Que la asignación de cada uno de los 132 sea la mejor posible.** Está derivada del reparto del
  lock y cada caso no obvio lleva su justificación en `/tmp/dx/mapa_servicios.py`, pero es un juicio
  de 132 decisiones y algunas son discutibles. Las más discutibles, para que se revisen primero:
  `SC-05` (¿el stock es de `comercio` o la exclusión es de `inteligencia`? puse los dos),
  `OP-03` (le puse `gateway` y `apps/web` porque el progreso por etapa se reporta y se muestra),
  y `NR-03` (le puse `comercio` porque el re-ranking pondera disponibilidad).
- **Que no haya más huecos como el de `operacion`.** Encontré ese porque el reparto lo puso en
  evidencia. No hice el ejercicio inverso completo —recorrer los dominios que el lock declara y
  buscar cuáles no tienen requisito—, que es lo que encontraría los demás si existen.
