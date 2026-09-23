# Cierre de los tres cambios abiertos: SRS v4.0 → v5.0

- **Tipo:** registro de aplicación. Documenta una operación ya ejecutada.
- **Fecha:** 2026-09-22.
- **Entrada:** `Arquitectura/SRS_ISIS2610G19_v4.docx`, **intacto**.
- **Salida:** **`Arquitectura/SRS_ISIS2610G19_v5.docx`**, con copia en `ENTREGA_FINAL/SRS/`.
- **Qué cierra:** los tres cambios que el v4 dejó declarados abiertos —`DP-04` sin umbral, E-21 con
  la norma pendiente de corroborar, y la Tabla 4 incompleta— más dos defectos que aparecieron al
  auditar el propio v4.
- **Qué no cierra, a propósito:** el choque de alcance de `OP-03`. El encargo pide preparar la
  decisión, no tomarla, y está en `tukit/docs/DECISION_OP03_NR07.md`.

---

## 0. Por qué v5 y no una actualización del v4

El encargo dejaba la elección abierta y pedía justificarla. **Se produjo un archivo nuevo**, por
una razón que vale más que la comodidad de no crear archivos: **el v4 ya fue citado por nombre**
en cinco documentos de `tukit/docs/`, en las cabeceras de `ENMIENDA_SRS.md` y
`ADENDA_REQUISITOS_SRS.md`, y posiblemente por los dos agentes que están construyendo. Una línea
base cuyo contenido cambia sin que cambie su nombre permite que dos personas tengan archivos
distintos que se llaman igual, y eso no se recupera: no hay forma de saber cuál de los dos leyó
cada uno.

Es además el criterio que el propio proyecto aplica en la superficie compartida: `CONTRATO_API.md`
pasó de v1.0 a v1.1 al extenderse, en vez de mutar bajo el mismo número, y esa decisión es lo que
hizo posible que la tabla de correcciones siguiera siendo aplicable. Un archivo más cuesta 785 KB;
una línea base ambigua cuesta una sesión de arqueología.

Y hay un argumento de rastreo: **quien tenga el v4 puede diferenciarlo contra el v5 y ver
exactamente qué cambió al cerrar los tres puntos**, que es justamente lo que un lector del v4
necesita saber. Mutando el v4 esa comparación deja de existir.

Los tres archivos —v3, v4, v5— se conservan. El v3 sigue con su suma de verificación original.

---

## 1. `DP-04`: el umbral medido

### 1.1 La evidencia que sirve, y la que no

El encargo apuntaba a `tukit-mvp-pipeline/calibration/gold_standard_final.csv`, a los AUC de 0,728
del canal léxico, 0,825 del semántico, 0,753 de la fusión y 0,879 del reordenador, y al hallazgo de
que 150 de 542 ítems no tienen ningún candidato correcto entre sus cinco.

**Esa evidencia no sirve para `DP-04`, y conviene decirlo antes de nada.** `DP-04` es un requisito
de **latencia** de la etapa de percepción: *"desde la recepción del archivo hasta la lista de ítems
estructurados"*. Los AUC y el 27,7 % miden **calidad de recuperación**, que es otra cosa y que
pertenece a otros requisitos: los AUC son la evidencia de `NR-03`, el re-ranking por similitud,
precio y disponibilidad; y el 27,7 % sin candidato correcto es la evidencia de `NR-01` y `NR-02`.
Ninguno de los dos dice cuánto tarda la percepción en leer un PDF.

La evidencia correcta estaba en otro sitio del repositorio:
**`Tukit-Poc-Tesis/poc_01_percepcion/corpus/resultados_benchmark_10.json`**, 6,9 MB con **cinco
motores de percepción por diez documentos reales**, y un campo `latencia_s` por medición. Eso sí es
lo que `DP-04` mide.

| Motor | n | mediana | media | p95 | máx | ítems extraídos |
|---|---:|---:|---:|---:|---:|---:|
| OCR Baseline | 10 | 0,18 s | 0,32 s | 0,77 s | 0,96 s | 6.181 |
| Google Vision | 10 | 6,33 s | 7,16 s | 11,80 s | 12,51 s | 1.939 |
| Docling | 10 | 24,43 s | 46,49 s | 135,58 s | 152,71 s | 3.959 |
| Baidu GOT-OCR | 10 | 213,04 s | 201,78 s | 276,19 s | 294,18 s | 1.481 |
| **Gemini (LMM)** | 10 | **312,46 s** | 329,64 s | **767,91 s** | 806,05 s | 1.246 |

Gemini es el motor que el sistema usa (`servicios/inteligencia/tukit_inteligencia/gemini.py`), así
que es su fila la que fija el umbral.

### 1.2 El primer resultado, que era alarmante y estaba mal

El p95 de Gemini sobre el documento completo es **767,91 s**, o 12,8 minutos. Contra los 300 s que
`OP-03` da al flujo **completo de cuatro etapas**, la primera etapa sola consumiría **2,56 veces el
presupuesto total**. Leído así, el umbral honesto de `DP-04` sería incompatible con `OP-03` y habría
que reportarlo como el conflicto que es.

Antes de reportarlo, dos comprobaciones lo desmontaron.

**La primera: los documentos medidos no son los que el sistema acepta.** Tres de los diez son
fusiones de varios grados —`ilovepdf_merged.pdf`, `1102_merged_merged.pdf`, `JARDÍN_merged.pdf`— y
`CONTRATO_API.md` §2.1 rechaza exactamente eso con un `422 lista_de_varios_grados`. `DP-04` acota
*"una lista de un grado"*. Medir el umbral sobre el documento completo mide algo que el sistema no
va a procesar.

**La segunda, y es la decisiva: la latencia registrada incluye las esperas por cuota.** El banco
está en `scripts/05_bench_lmm.py` y su instrumentación se puede leer línea por línea. El cronómetro
arranca en la línea 174, **antes** del ciclo de reintentos; la acumulación ocurre en la línea 216,
**después**. Dentro de ese ciclo, la línea 204 duerme **120 segundos** cada vez que la API responde
`429` o `RESOURCE_EXHAUSTED`, con hasta **quince reintentos** por página. Así que cada respuesta de
cuota excedida suma 120 s a la latencia «medida». La pausa deliberada de 6 s entre páginas de la
línea 229, en cambio, cae **fuera** de la ventana cronometrada y no contamina.

La huella es visible en los datos: la latencia por página va de **4,29 s a 65,57 s** entre
documentos de tamaño comparable, un factor de quince que ningún contenido explica. Y el `ANEXO_P.md`
del propio corpus documenta que la sesión estuvo *"bloqueada parcialmente por la cuota gratuita
diaria de Gemini"*.

**O sea que el p95 de 768 s mide el régimen de cuota del nivel gratuito, no la percepción.**
Reportarlo como umbral habría sido reportar una cifra que la primera medición en producción
desmiente, que es exactamente lo que el enunciado anterior de `DP-04` decía que no había que hacer.

### 1.3 La derivación que queda

Depurando la contaminación, **un solo documento del corpus no muestra exceso atribuible a cuota**:
`LISTAS-DE-TEXTOS-ESCOLARES-COLEGIO-SAN-JOSE-DE-FONTIBON.pdf`, 14 páginas, 78,68 s → **5,62 s por
página**. Los demás muestran excesos de entre dos y seis múltiplos de 120 s.

La percepción llama al modelo **una vez por página** (`percepcion.py`, el bucle sobre `paginas`), de
modo que la página es la unidad correcta del umbral. Con holgura de 2:

| Páginas de la lista | p95 estimado | Fracción del presupuesto de `OP-03` |
|---:|---:|---:|
| 1 | 11 s | 3,7 % |
| 2 | 22 s | 7,5 % |
| 3 | 34 s | 11,2 % |
| 4 | 45 s | 15,0 % |

La lista de un grado ocupa entre una y tres páginas en el corpus. **El umbral que quedó escrito es
p95 ≤ 12 s por página y ≤ 45 s para la lista completa de un grado**, con la regla de método que la
medición obligó a añadir: las esperas por límite de tasa no son latencia del módulo, se reportan
aparte y se excluyen del percentil, y una medición que no declare cuántas incurrió no es válida.

**Lo incómodo, dicho:** el valor se sostiene sobre **una sola observación** no contaminada. Es
suficiente para fijar un orden de magnitud y no para afirmar un p95, y por eso el requisito declara
sus propios valores **provisionales** y exige una re-medición con al menos diez documentos en
régimen de cuota de producción. Presentarlo como el p95 de diez documentos habría sido más limpio
de leer y falso.

### 1.4 El conflicto que sí quedó, y es más estrecho

Una vez corregida la medición, **`DP-04` y `OP-03` no chocan**: 45 s es el 15 % de 300 s. El
conflicto real es otro y es angosto: **`TOPE_PAGINAS = 40`** en `percepcion.py` admite documentos de
hasta cuarenta páginas, y a 5,62 s por página eso son **225 s, el 75 % del presupuesto completo de
`OP-03`** consumido por la primera etapa. El tope de páginas y el tope de tiempo se fijaron por
separado y no se hablan.

En la práctica la guarda de un grado por archivo hace improbable que una lista legítima llegue a
cuarenta páginas —la más larga del corpus, el consolidado de CACS, tiene 39 y cubre catorce grados—,
pero el límite lo permite. La salida barata es bajar `TOPE_PAGINAS` a un valor coherente con el
presupuesto, y es decisión de quien posee `servicios/**`. Queda anotado, no resuelto.

---

## 2. E-21: la norma corroborada

### 2.1 El veredicto sobre las tres leyes candidatas

El encargo proponía tres. **Ninguna de las tres es donde está escrita la prohibición**, y una de
las tres sí aparece en la cadena.

| Norma propuesta | ¿Aplica al supuesto de E-21? |
|---|---|
| **Ley 1581 de 2012** (datos personales) y su decreto reglamentario | **No.** Gobierna el tratamiento de datos personales y el régimen especial de menores. En el SRS sostiene `PE-06`, `PV-01` a `PV-05` y `PS-01` a `PS-05`, donde está correctamente citada. No tiene nada que decir sobre marcas de útiles |
| **Ley 1480 de 2011** (estatuto del consumidor) | **No** para este supuesto. Es donde vive el derecho de retracto que `FU-04` implementa, y ahí está bien citada. La imposición de marcas por un colegio no es una relación de consumo entre el colegio y la familia en el sentido que esta ley regula |
| **Ley 1340 de 2009** (protección de la competencia) | **Sí, pero como marco y no como fuente.** Los actos administrativos que aplican la prohibición la invocan de forma expresa: la lista *"en sintonía con lo dispuesto en la Ley 1340 de 2009, no puede incurrir en prácticas restrictivas"*. Es el fundamento de competencia, no el texto que prohíbe |

### 2.2 Dónde está escrita de verdad

La prohibición es **sectorial, del Ministerio de Educación Nacional**, y tiene artículo concreto:

> **Resolución 019805 del 30 de septiembre de 2025, artículo 14** — que adopta la versión 11 del
> *Manual de Autoevaluación y Clasificación de Establecimientos Educativos Privados* para la
> vigencia 2026: los establecimientos *"no pueden incurrir en prácticas restrictivas en la solicitud
> de materiales educativos, tales como: exigir proveedores, marcas específicas, ni establecer
> mecanismos que de cualquier forma impidan la concurrencia de múltiples proveedores en la provisión
> de estos materiales"*.

La cadena completa, que es la que quedó escrita en §2.4.1 del v5:

| Pieza | Norma y artículo | Qué aporta |
|---|---|---|
| La prohibición | **Resolución 019805 de 2025, art. 14** (MinEducación) | El texto operativo: no exigir proveedores ni marcas específicas |
| Su reiteración anual | **Circular 002 del 8 de enero de 2026, numeral 7** (MinEducación) | La aplica al año escolar 2026 |
| Su antecedente | **Resolución 20310 de 2022, art. 13** | La misma regla en la vigencia anterior |
| La obligación de entregar la lista | **Ley 1269 de 2008, art. 1**, que modifica el **parágrafo 1 del art. 203 de la Ley 115 de 1994** | Lista completa en la matrícula, aprobada por el Consejo Directivo |
| El marco de competencia | **Ley 1340 de 2009** | Lo que los actos invocan para fundar «prácticas restrictivas» |
| No obligar a comprar en el colegio | **Decreto 1075 de 2015, art. 2.3.4.12, ordinal b)** | Prohíbe imponer la compra en el establecimiento o en negocios de las asociaciones de padres |

**Fuentes consultadas el 22 de septiembre de 2026:** el comunicado y la circular del portal de
MinEducación (`mineducacion.gov.co`), el texto de la Circular 002 en el repositorio de documentos
del Ministerio, la Ley 1269 de 2008 en el Gestor Normativo de Función Pública, y resoluciones
individuales de secretarías de educación que reproducen el articulado al autorizar tarifas para
2026.

### 2.3 Qué estaba mal en el SRS, y qué estaba bien

El v3 y el v4 citaban *"Resolución 17821/2023 MinEducación; Circular 002/2026"*. De los dos:

- **La `Circular 002/2026` estaba bien citada.** Existe, es del 8 de enero de 2026, y su numeral 7
  es precisamente donde se reitera la prohibición. El equipo tenía razón en esa mitad.
- **La `Resolución 17821 de 2023` no se pudo corroborar** en ninguna fuente pública, y la resolución
  que ocupa su lugar funcional para la vigencia 2026 es la **019805 de 2025**. Se retira.

Es el resultado que E-21 anticipaba al pedir corroborar o reformular: no era una norma inventada,
era un número equivocado junto a una cita correcta.

### 2.4 Un hallazgo del paso, que da fundamento legal a `ED-10`

Al leer la Circular 002 completa apareció algo que el SRS no recogía. Su **numeral 6** establece que
*"los textos escolares no podrán ser diferentes a los del año anterior, salvo que se hubiesen
mantenido por al menos tres (3) años"*.

Eso es exactamente lo que `ED-10` pide —vigencia mínima acordada de un texto— y el SRS lo
justificaba solo como defensa contra la fatiga de decisión de un colegio bombardeado por
propuestas. **Tiene fundamento normativo y no lo sabía.** Se le añadió a su razón en el v5. No
cambia su prioridad, que sigue siendo `Won't (v1)`, porque sin `ED-02` no hay flujo de propuestas
que frenar; sí cambia la calidad del argumento con que se defiende.

---

## 3. La Tabla 4: mapeo completo, con un límite declarado

### 3.1 Cerró completa

De 9×9 a **12×12**: las once funciones `F1` a `F11` contra los once módulos, con leyenda `M1`–`M11`
y la rejilla redistribuida para que los 9.405 twips de ancho útil no se desborden.

| | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | M9 | M10 | M11 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| F1 Cargar lista | | ✓ | | | ✓ | ✓ | | | | | |
| F2 Normalizar útiles | ✓* | ✓ | ✓ | | | ✓ | | | | | ✓* |
| F3 Generar kits | | | ✓ | ✓ | | | | | | | |
| F4 Visualizar y personalizar | ✓* | | | ✓ | ✓ | | | | | | |
| F5 Checkout | | | | | ✓ | | | ✓ | | | |
| F6 Cargar lista oficial | ✓* | ✓ | | | | ✓ | ✓ | | | | ✓* |
| F7 Validar mapeos | ✓* | | ✓ | | | ✓ | | | | | |
| F8 Mantener el catálogo | ✓ | | | | | ✓ | | | | ✓* | |
| F9 Pago y ciclo de la orden | | | | | ✓* | | | ✓* | ✓* | | |
| F10 Pedidos, rutas y entregas | | | | | | ✓* | | ✓* | ✓* | | |
| F11 Consentimiento y derechos | | | | | ✓* | | | | | | |

`M1` Scraper y Catálogo · `M2` Percepción · `M3` Normalización (RAG) · `M4` Optimización ·
`M5` Interfaz del padre · `M6` Panel Admin · `M7` Panel Colegio · `M8` Fulfillment y Pagos ·
`M9` Última Milla · `M10` Canal Comercial · `M11` Contenido Editorial.
**(\*)** = celda derivada en el v5, no presente en las versiones anteriores.

### 3.2 De dónde salió cada marca nueva

No se inventaron: se derivaron del reparto por servicio de `ARQUITECTURA.md` §1 y del ADR 0008.

- **`M1` en F2, F4, F6 y F7.** `catalogo` es el propietario del producto canónico y de los
  embeddings, así que participa en normalizar (F2); la re-verificación de precio del intercambio de
  ítems de `UI-03` lo lee, así que participa en personalizar (F4); el ADR 0012 §4 le asigna las
  listas oficiales, así que participa en cargarlas (F6); y la firma de revisión de `AD-06` y `NR-07`
  vive ahí, así que participa en validar mapeos (F7).
- **`M11` en F2 y F6.** Las líneas de tipo `texto` no se resuelven por emparejamiento sino por
  consulta de `version_vigente` por colegio, área y grado, que es el módulo editorial.
- **`M10` en F8.** El propio §3.15 dice que el canal mayorista *"coexiste con el scraper (Módulo 1)
  como fuente de catálogo"*.
- **F9, F10 y F11** son filas nuevas: no existían, porque la tabla se había quedado en F8.

### 3.3 El límite, que se declara en vez de rellenarse

**Tres de los siete servicios de la arquitectura no tienen módulo propio en la Sección 3:
`identidad`, `operacion` y `gateway`.** La tabla no puede darles columna porque sus columnas son los
once módulos, y eso se nota en `F11`, que aparece con **una sola marca** aunque el consentimiento y
los derechos del titular viven enteros en `identidad`. Lo mismo pasa con los casos, las
notificaciones y la auditoría, que son de `operacion`.

La consecuencia es medible y apareció al contar: **la columna `Módulo` de las tablas de la Sección 3
usa, para treinta y cinco requisitos, nombres que no son ninguno de los once módulos** —
`Transversal` (15), `Identidad` (8), `Todos` (6), y uno cada uno de `Catalogo`, `Comercio`,
`Inteligencia`, `Catalogo / Inteligencia`, `Comercio / Identidad` e `Identidad + Inteligencia`. Son
nombres de **servicio**, no de módulo.

Las dos taxonomías son correctas y describen cortes distintos del sistema: los módulos son
capacidades del producto y los servicios son unidades de despliegue con dueño de datos. Lo que falta
es **una decisión sobre cuál de las dos organiza la Sección 3**, y esa decisión no es de redacción.
Parte del desajuste es anterior (`Todos` ya estaba en el v3) y parte la introdujo la consolidación,
porque la enmienda y la adenda asignan requisitos a servicios —así piensan los ADR 0012 y 0013—
mientras §3 se organiza por módulo. Queda escrito en la nota de la propia Tabla 4.

---

## 4. Dos defectos del v4 que aparecieron al auditar, y su causa común

Al verificar el v5 se encontraron **dos cambios del v4 que no habían quedado como el registro
decía**. Los dos tienen la misma causa, que es la tercera aparición del mismo error de método.

**El primero: el cambio E-21 aterrizó en la bibliografía.** La edición se localizó buscando la
subcadena `"17821"`, que aparece **dos veces** en el documento: en la entrada **[14] de §1.4
Referencias** y en la viñeta de **§2.4.1 Restricciones Generales**. La búsqueda devuelve la primera,
que es la bibliográfica. Resultado: el v4 **sustituyó una entrada de la bibliografía por el texto de
una restricción** y dejó la restricción sin corregir. En el v5 se restituyó la entrada [14] —ahora
con las normas corroboradas— y se corrigió la viñeta de §2.4.1, que es la sección que E-21 nombraba
desde el principio.

**El segundo: el cambio de `F11` se registró como aplicado sin aplicarse.** La edición buscaba
`"Módulo PWA"` para sustituir `"Módulo PWA y App."`. Pero **`F4` también termina en `"Módulo
PWA."`** y aparece antes, de modo que la búsqueda encontró `F4`, el reemplazo no coincidió con nada,
y el script escribió `F4` con su propio texto sin cambios y registró el cambio como limpio. `F11`
siguió diciendo *"Módulo PWA y App"* en el v4. Corregido en el v5 anclando por el prefijo `F11.`.

**La causa común, y la lección.** Las tres veces —el índice de contenido en la primera sesión, la
bibliografía y `F11` en esta— el error fue el mismo: **una búsqueda por prefijo o por subcadena que
encuentra un sitio anterior y plausible.** La primera vez se corrigió excluyendo los estilos `toc`;
eso era necesario y no suficiente. La regla completa es que **una edición no está verificada porque
el texto buscado exista, sino porque el párrafo editado esté en la sección esperada**. En esta
sesión se añadió esa comprobación: una función que sube desde el párrafo hasta su encabezado y
afirma que coincide con el destino declarado. Pasada sobre las diecinueve ediciones del v4 y del v5,
encontró exactamente estos dos casos; los otros diecisiete estaban bien.

Conviene decir también por qué el registro del v4 no los detectó: verificaba **estructura y
códigos** —que los 131 requisitos estuvieran, que el Anexo C correspondiera, que el XML parseara— y
ninguna de esas comprobaciones pregunta si un cambio aterrizó en su sección. Una verificación que
cuenta bien no verifica que se haya escrito en el sitio correcto.

---

## 5. Verificación del v5

Misma disciplina que el v4, con los mismos resultados.

| Comprobación | Resultado |
|---|---|
| `.zip` sin errores de CRC | ✅ |
| Las 18 partes del v4 están en el v5, sin partes nuevas ni perdidas | ✅ |
| Todos los `.xml` y `.rels` parsean | ✅ |
| `word/styles.xml` **byte a byte** intacto | ✅ |
| `word/numbering.xml` **byte a byte** intacto | ✅ |
| Tema, tabla de fuentes, encabezado, pie e imágenes intactos | ✅ |
| `updateFields` presente para que Word regenere el índice | ✅ |
| Estilos de tabla: 40 de 40 en `Normal Table` | ✅ |
| Estilos de párrafo: los mismos siete, ninguno nuevo | ✅ |
| Campo `TOC` presente | ✅ |
| Pies de tabla: 30, consecutivos de 1 a 30 | ✅ |
| Requisitos declarados ↔ filas del Anexo C | **131 ↔ 131**, correspondencia exacta, sin duplicados |
| Tabla 4: rejilla de 12 columnas | suma 9.405 twips = ancho útil exacto |
| Cada edición en su sección declarada | 19 de 19 ✅ tras corregir las dos de §4 |

El índice de contenido sigue mostrando los números de página del v4 hasta que Word lo regenere, por
la misma razón de siempre: es un campo y recalcularlo exige un motor de composición. `updateFields`
lo resuelve al abrir.

---

## 6. Qué queda abierto sobre el v5

| Qué | Dónde | Bloqueado por |
|---|---|---|
| El choque de alcance de `OP-03` y el presupuesto del camino corto | `tukit/docs/DECISION_OP03_NR07.md` | Decisión entre tres alternativas |
| Re-medir `DP-04` con ≥10 documentos en régimen de cuota de producción | §1.3 de este documento | Cuota de producción del proveedor del modelo |
| `TOPE_PAGINAS = 40` frente al presupuesto de `OP-03` | §1.4 de este documento | Decisión de quien posee `servicios/**` |
| Elegir si la Sección 3 se organiza por módulo o por servicio | §3.3 de este documento | Decisión de arquitectura de documento |
| Partir `SG-05` en dos requisitos (faltante `RF-13`) | `CONSOLIDACION_SRS_V4.md` §3 | Nada; es redacción |
| Paquete de trabajo para los seis requisitos editoriales de v1 | `REQUISITOS_DIFERIDOS.md` | Decisión de alcance |
| Aceptar formalmente los ADR 0012, 0013 y 0014 | `CORRECCIONES_TRAZABILIDAD.md` §7.5 | Nada |
| Registrar el artefacto de `PE-07` en `ANEXO_M_DATOS_PERSONALES.md` | `ADENDA_REQUISITOS_SRS.md` E-33 | Nada |
| Actualizar el conteo de `MOSCOW_REQUISITOS.md` a 131 | `REQUISITOS_DIFERIDOS.md` §5 | Nada |

---

## 7. Lo que no verifiqué

- **Que el v5 se vea bien en Word.** Verifiqué integridad, estilos byte a byte, XML y ubicación de
  cada edición. **No lo he abierto en Word.** La Tabla 4 con doce columnas es la que más conviene
  mirar a ojo: los 628 twips por columna de módulo son suficientes para un tilde de verificación y
  ajustados para cualquier otra cosa.
- **Que 5,62 s por página sea la latencia real del modelo.** Es la única observación del corpus sin
  exceso atribuible a cuota, y es una sola. Puede seguir conteniendo esperas pequeñas que no llegan
  al múltiplo de 120 s.
- **Que la Resolución 019805 de 2025 siga vigente al momento de la sustentación.** Es el manual de
  autoevaluación para la vigencia 2026 y este tipo de resolución se reemplaza cada año. La cita
  lleva su fecha de consulta por eso.
- **El texto íntegro del artículo 14 de la Resolución 019805.** Lo leí reproducido en la Circular
  002 y en resoluciones de secretarías que lo citan literalmente, no en el documento original de la
  resolución.
- **Que `TOPE_PAGINAS = 40` siga siendo 40.** Lo leí en `percepcion.py` y ese archivo lo posee otro
  agente.
