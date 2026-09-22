# OE3 — Resolución híbrida con grafo sobre el catálogo

- **Fecha:** 2026-09-22
- **Objetivo específico:** OE3 (percepción y normalización semántica)
- **Servicios tocados:** `catalogo` (recuperación), `inteligencia` (reordenamiento y decisión)
- **Documento que manda por encima de este:** `Arquitectura/ARQUITECTURA.md`
- **Spec hermano:** `2026-09-22-optimizador-nsga2-maut-design.md` (OE4), que consume lo que este produce

---

## 1. El problema, medido

El emparejamiento de hoy (`catalogo/tukit_catalogo/consulta.py`) es **enteramente léxico**:
corrección ortográfica, `clasificar` por similitud de cadenas contra el nombre canónico y los
sinónimos del concepto, filtro duro de atributos impuestos y una opción por nivel. No hay
vectores, no hay grafo y no hay reordenamiento.

Estado verificado contra la base viva el 2026-09-22:

| Hecho | Valor | Cómo se verificó |
|---|---|---|
| Productos canónicos | 375 | `select count(*) from producto_canonico` |
| Productos **con vector** | **0** | `count(embedding)` |
| Columna de vector | `vector(1024)` | `\d producto_canonico` |
| Índice denso | `ix_producto_embedding_hnsw` (`vector_cosine_ops`) — existe | `pg_indexes` |
| Índice léxico | `ix_producto_nombre_trgm` — existe | `pg_indexes` |
| Columna `embedding` en `concepto` | **no existe** | `select embedding from concepto` → error |
| Conceptos | 100 | `select count(*) from concepto` |
| Aristas de sustituibilidad curadas | **0** | `select count(*) from sustituibilidad_concepto` |
| Listas oficiales cargadas | 175, de 17 colegios | `lista_oficial` |
| Renglones de listas oficiales | 4.719, sobre 98 conceptos distintos | `item_lista_oficial` |

> **Dos artefactos distintos que conviene no confundir.** `Arquitectura/UTILES_COLEGIO_GRADO.zip`
> contiene **80 PDF en crudo de 7 colegios** (San Pedro Claver 14, Modelia 14, Prados de
> Alameda 13, CACS 13, Bahía Solano 12, Matilde 11, Osito de Miel 3). Las **175 listas** de
> este spec son las filas de `lista_oficial` en `tukit_catalogo`, de **17 colegios**, ya
> parseadas y con cada renglón ligado a su concepto. El grafo se deriva de las 175, porque son
> las que tienen la liga a concepto que el prior necesita; los PDF son la fuente cruda de una
> parte de ellas.

O sea: la infraestructura vectorial está construida y **vacía**, y el grafo curado está
declarado y **vacío**. `cargador.py` no menciona la palabra `embedding` ni una vez.

Las mediciones del prototipo (`tukit-mvp-pipeline`, 2.710 pares anotados en
`calibration/gold_standard_final.csv`) fijan las líneas base y contienen el hallazgo que
gobierna este diseño:

| Canal | AUC |
|---|---|
| Léxico (`lex`) | 0,728 |
| Denso (`vec`) | 0,825 |
| Fusión RRF (`rrf`) | **0,753** |
| Reordenador cross-encoder (`rerank`) | 0,879 |

**La fusión RRF mide peor que su propio canal denso.** Por eso RRF no puede ser lo que
puntúa. Y el número que manda sobre todos: **150 de 542 ítems (27,7 %) no tienen ningún
candidato correcto entre sus 5**. Eso es recall que nunca ocurrió, y ninguna mejora de
ordenamiento lo recupera.

### 1.1 Supuesto de alcance declarado

Los **102 huecos de catálogo** (celdas concepto × nivel vacías) **quedan fuera de este
trabajo**. Los algoritmos se diseñan y se miden contra el catálogo tal como está, y la
abstención por hueco es una salida legítima que se mide como tal. Llenar celdas es trabajo de
datos y bloquearía este diseño sin cambiarlo. La consecuencia se asume explícitamente: el
recall de catálogo medido en la evaluación estará acotado por arriba por esos huecos, y el
informe lo dirá separando "no lo tenemos" de "no lo encontramos".

---

## 2. Reparto entre servicios

El ADR 0012 ya partió `MS-Busqueda` por un criterio que este diseño respeta al pie de la
letra: **`catalogo` es exhaustividad, `inteligencia` es precisión**. Y los invariantes 1 y 3
de `test_fronteras.py` impiden que `inteligencia` importe código de `catalogo` o se conecte a
su base.

| Responsabilidad | Servicio | Por qué ahí |
|---|---|---|
| Vectores de concepto y producto, índices HNSW y GIN | `catalogo` | Es el dueño de la base que los contiene |
| Grafo de conceptos (construcción y consulta) | `catalogo` | Sus tres fuentes de aristas viven en `tukit_catalogo` |
| Recuperación de candidatos con puntajes por canal | `catalogo` | Exhaustividad |
| Reordenamiento cross-encoder | `inteligencia` | Precisión; perfil CPU/modelos es suyo (ARQUITECTURA §1) |
| Calibración a probabilidad | `inteligencia` | Depende del reordenador |
| Decisión τ/δ y estado de resolución | `inteligencia` | Es dueña de `resolucion_item` |

**`catalogo` recupera y no decide.** Esa frase es la prueba de diseño: si `catalogo` devuelve
un estado de resolución, la frontera se movió.

### 2.1 Cambio de contrato: un endpoint nuevo, no uno modificado

`POST /v1/catalogo/emparejar` **se conserva intacto**. Ya está documentado en
`CONTRATO_API.md` §12, lo usa el CLI de administración y devuelve una decisión
(`reconocido` / `abstencion` / `hueco_catalogo` / `sin_match`). Cambiarle la semántica
rompería consumidores vivos.

Se agrega **`POST /v1/catalogo/recuperar`**, que devuelve el pool con puntajes por canal y
ningún veredicto:

```jsonc
// petición
{ "renglones": [ { "texto": "cuaderno cuadriculado de 100 hojas", "grado": "Cuarto" } ],
  "k": 20 }

// respuesta, por renglón
{ "texto": "cuaderno cuadriculado de 100 hojas",
  "texto_corregido": "cuaderno cuadriculado de 100 hojas",
  "atributos_impuestos": { "tipo": "cuadriculado" },
  "candidatos": [
    { "producto_id": "…", "sku": "TK-C001-ECO", "nombre": "…", "nivel": "economico",
      "concepto_codigo": "C001", "personaje": null, "marca": "…",
      // Una fila por OFERTA, no por producto: el OE4 decide en qué tienda comprar,
      // así que un producto con 3 ofertas produce 3 candidatos y nunca un min(precio).
      "oferta_id": "…", "tienda_id": "…", "tienda_slug": "panamericana",
      "precio_cop": 4400, "unidad_base": "unidad", "unidades_por_empaque": 1,
      "cumple": true,
      "canales": { "lex": 0.62, "vec": 0.81, "grafo": 0.0, "prior_grado": 0.37 },
      "via": ["lex", "vec"] }
  ] }
```

`grado` es opcional y alimenta el prior; su ausencia deja `prior_grado` en el valor marginal
del concepto, no en cero, para que un renglón sin grado no quede castigado.

`via` dice qué canal trajo al candidato. No es decorativo: es lo que permite medir la
ablación de la §7 sin volver a correr la recuperación.

---

## 3. Los tres canales de recuperación

### 3.1 Canal léxico

`word_similarity` de pg_trgm sobre el índice GIN existente, con las dos correcciones que el
prototipo ya pagó y que se portan literalmente:

- **`variantes_lexicas`**: se genera una frase **completa** por cada sustitución de sinónimo,
  dejando el resto de la frase en su posición, y se toma el mejor `word_similarity` entre
  ellas. Nunca palabras sueltas (una palabra distintiva satura en 1,000 contra cualquier
  producto que la contenga) y nunca todos los sinónimos a la vez (la frase resultante no se
  parece a ningún nombre real).
- **`STOPWORDS_DOMINIO`**: se filtran palabras de envase y tamaño (`caja`, `grande`,
  `paquete`…) **solo en este canal**. El canal denso recibe la descripción completa sin
  filtrar, porque los modelos e5 se entrenaron sobre oraciones naturales.

### 3.2 Canal denso

Coseno sobre `vector(1024)` con el HNSW ya creado, en **dos niveles**:

- **Producto** (375 filas): la columna ya existe y hay que poblarla.
- **Concepto** (100 filas): **migración nueva** que agrega `embedding vector(1024)`,
  `embedding_model varchar(128)`, `texto_embedding text` y su índice HNSW coseno, con la misma
  forma que ya tiene `producto_canonico`.

El nivel de concepto no es opcional. La decisión que el pipeline toma es *renglón → concepto*,
y sin vector de concepto el canal denso no participa en la etapa donde el match falla.

**Qué texto se embebe**, registrado en `texto_embedding` para que sea auditable:

- Concepto: `nombre_canonico` + sinónimos + nombres de los atributos discriminantes,
  unidos en una frase natural.
- Producto: `nombre` + marca + la ruta de categoría.

Se consideró enriquecer el texto del concepto con renglones reales tomados de las listas
oficiales y **se descartó para esta versión**: mete la distribución de la evaluación dentro del
índice y contamina la medición del §7. Queda anotado como variante a probar después, con
partición explícita de entrenamiento y prueba.

### 3.3 Canal de grafo

Nodos: los 100 conceptos. Tres clases de arista, de tres procedencias distintas:

| Arista | Fuente | Estado hoy |
|---|---|---|
| **Sustituibilidad** dirigida con `grado ∈ (0,1]` | `sustituibilidad_concepto` | **0 filas — hay que sembrarla** |
| **Sinonimia** | `concepto.sinonimos` | Poblada |
| **Co-ocurrencia por grado** | `item_lista_oficial` (4.719 renglones, 98 conceptos, 175 listas) | Derivable hoy |

#### Cómo se siembra la sustituibilidad sin escribirla desde cero

La tabla exige `motivo` y `curado_por` no nulos **a propósito**: su propio docstring dice que
una arista que no dice por qué existe ni quién la puso no se puede revisar, y que poder
revisarla es lo único que la separa de un coseno. Eso **no** obliga a redactar cada arista a
mano. Obliga a que una persona **confirme** cada una.

El catálogo ya contiene la curaduría, en un sitio inesperado: **los nombres de las 49
categorías son grupos de sustitución** escritos con alternativas separadas por barra.

```
Colbón / Pegante líquido / Pegastic
Carpetas / Folders / Legajadores / Sobres manila
Témperas / Vinilos / Pintura / Acuarelas
Compás / Estuche de geometría
Lápices / Portaminas
```

Alguien ya decidió qué se parece a qué cuando nombró esas categorías. Derivar aristas
candidatas de la co-pertenencia a categoría no inventa una heurística nueva: cobra una
curaduría que ya ocurrió.

Volumen medido contra la base (2026-09-22):

| Fuente de candidatos | Pares dirigidos |
|---|---|
| Todas las categorías con ≥2 conceptos (18 de 49) | 362 |
| **Excluyendo `Otros / Varios` y las de >6 conceptos** | **120** |
| `CONCEPTOS` ya curados en `tukit-mvp-pipeline/pipeline/grafo_sustituibilidad.py` | 36 grupos |
| `SINONIMOS` ya curados en `stage2_busqueda.py` | 10 grupos |

`grupo_variante_id` se evaluó como cuarta fuente y **no sirve**: 0 de 375 productos la tienen
poblada.

**Procedimiento**: un script propone las ~120 aristas con su `motivo` pre-redactado
(«comparten la categoría *X*, que enumera alternativas»), y una persona acepta, rechaza o
ajusta el `grado` en bloque. Es el mismo patrón que `propuesta_producto` ya implementa para
productos candidatos, así que no se inventa un mecanismo nuevo. Se espera rechazar una fracción
alta y rápido: `Biblia` y `Diccionario` comparten categoría y **no** son sustitutos.

El grafo es **incremental y opcional**: con 0 aristas el canal queda en silencio y la
recuperación funciona con léxico y denso. Eso acota el riesgo de que la curaduría se vuelva el
camino crítico del OE3.

> **Trampa que hay que evitar, y que la implementación no puede confundir.** Que dos conceptos
> aparezcan **juntos** en la misma lista es evidencia de que son **complementarios**, no
> sustitutos: si el colegio pide cuaderno y block, se necesitan los dos. La co-ocurrencia
> alimenta **solo** el prior de grado. La señal de sustituibilidad es la contraria —ocupar el
> mismo lugar sin aparecer juntos— y por eso no se deriva de co-ocurrencia.

El grafo hace **dos trabajos que no se deben confundir**:

1. **Expansión de recall.** Desde los conceptos top-k del canal denso se traen vecinos por
   sustituibilidad y entran candidatos al pool que ni el trigrama ni el coseno alcanzaron.
   Aporta `canales.grafo = grado` de la arista recorrida.
2. **Prior condicionado al grado.** `P(concepto | grado)` estimada sobre `item_lista_oficial`
   con suavizado de Laplace. Es lo que distingue un "block" de Párvulos de uno de Once, y es
   lo que hace que esto sea recuperación aumentada por grafo y no "coseno con sinónimos".

**Construcción y caché.** El grafo se construye **una vez al arrancar el proceso** y se
mantiene en memoria. No es una preferencia de estilo: el `PERFILADO_PIPELINE.md` atribuyó el
95,3 % de la latencia del pipeline a reconstruir un grafo por ítem (1.673 ms construir contra
0,137 ms consultar), y cachearlo bajó 20 ítems de 35,1 s a 1,7 s. Con 100 nodos cabe de sobra
en memoria, que es exactamente el hallazgo que motivó al ADR 0006 a eliminar Neo4j. Se invalida
por evento de cambio de catálogo, no por temporizador.

### 3.4 Formación del pool

El pool es la **unión** de los tres canales, cada uno aportando sus mejores `k` y sus puntajes.
No hay fusión de rangos aquí. RRF queda disponible únicamente como criterio de truncamiento si
la unión excede un tope, y se documenta que **no puntúa**, porque medido puntúa peor que el
canal denso solo.

El filtro duro de atributos impuestos se mantiene donde está hoy, en `catalogo`: es una
afirmación sobre lo que el catálogo declara. Los candidatos viajan con `cumple: bool` y la
abstención por atributo sigue siendo "el renglón pide X y ninguno de los N productos lo
declara; no ofrezco otro".

---

## 4. Reordenamiento, calibración y decisión

Todo esto vive en `inteligencia`.

### 4.1 Puerto `Reordenador` (ADR 0005)

```python
class Reordenador(Protocol):
    def puntuar(self, consulta: str, candidatos: Sequence[Candidato]) -> Sequence[float]: ...
```

El ADR 0005 ya fijó la escalera de adaptadores para este mismo componente, y este spec la
respeta en vez de inventar otra:

| Nivel | Adaptador | Origen |
|---|---|---|
| 1 | Cross-encoder en **GPU serverless** (Modal), por el arranque en frío de 1,5–3,5 s | ADR 0005 |
| 2 | Cross-encoder **local en CPU**: el de desarrollo y la demostración académica | ADR 0005 |
| 3 | **Respaldo sin modelo** cuando ninguno está disponible | Ver §4.1.1 |

El respaldo **no es decorativo**: el servicio arranca con él si no hay adaptador configurado,
y lo anuncia al arrancar, igual que hace hoy el `Cifrador` sin llave. La etapa queda en
`EstadoEtapa.DEGRADADA`, que ya existe en el modelo.

#### 4.1.1 Desviación del ADR 0005 que exige un ADR nuevo

El ADR 0005 dice, textualmente, que si el adaptador remoto falla «el pipeline **degrada al
orden de la fusión recíproca**». Este spec **contradice esa frase**, y la contradicción es
deliberada y está medida: RRF obtuvo AUC 0,753, **por debajo de su propio canal denso**
(0,825). Degradar a RRF es degradar por debajo de no fusionar nada.

El respaldo propuesto en su lugar es una **regresión logística** sobre los cuatro rasgos
`[lex, vec, grafo, prior_grado]`, entrenada con los 2.710 pares. Sale calibrada de fábrica, no
agrega modelo a la imagen, y explica exactamente por qué RRF pierde: RRF pondera rangos por
igual, y esta pondera por evidencia.

> **Requisito de gobierno, bloqueante.** El `ARQUITECTURA.md` §11 exige que toda modificación
> de arquitectura entre **primero al lock, con su ADR**, y solo desde ahí baje al código. Así
> que antes de implementar este respaldo hay que:
>
> 1. Levantar un **ADR 0019** que enmiende el respaldo del ADR 0005, con la medición como
>    evidencia y RRF como alternativa rechazada.
> 2. Actualizar la fila del ADR 0005 en la tabla del `ARQUITECTURA.md` §4.
>
> Implementar antes de eso deja el código contradiciendo un ADR aceptado, que es precisamente
> la deriva que el lock existe para impedir.

### 4.2 Puerto `Embebedor`

Mismo patrón, en `catalogo`:

```python
class Embebedor(Protocol):
    modelo: str
    dimensiones: int          # 1024, y se verifica contra la columna al arrancar
    def embeber(self, textos: Sequence[str]) -> Sequence[Sequence[float]]: ...
```

El modelo es **`multilingual-e5-large`**. No es una elección libre: la columna ya es
`vector(1024)` con índice coseno, que es exactamente e5-large, y es el que usó el prototipo,
así que los AUC medidos siguen siendo comparables. Cambiar a Gemini (768 dimensiones) obligaría
a migrar la columna, reconstruir el HNSW y re-medir todo desde cero.

Hay una trampa de peso que el puerto existe para resolver: vectorizar el catálogo es un trabajo
por lotes de 475 vectores que se corre una vez, pero **el renglón entrante también hay que
embeberlo en cada consulta**, así que el modelo se necesita en la ruta de servicio. Adaptadores:

- **Lotes, fuera de línea**: `python -m tukit_catalogo.vectorizar`, idempotente, escribe
  `embedding`, `embedding_model` y `texto_embedding`, y solo recalcula cuando el texto cambió.
- **Servicio**: adaptador remoto por omisión; adaptador local como respaldo.

Si no hay ningún embebedor disponible, el canal denso se apaga, se anuncia al arrancar y la
recuperación sigue con léxico y grafo. Degradar, nunca tumbar.

### 4.3 Calibración

El puntaje del reordenador **no es una probabilidad** y compararlo contra un umbral fijo fue
el defecto original. Se ajusta una **regresión isotónica** sobre los 2.710 pares, con validación
cruzada de 5 pliegues estratificada por ítem (no por par, para que candidatos del mismo renglón
no queden repartidos entre pliegues e inflen el resultado).

El calibrador se versiona como artefacto con su modelo, su fecha y el hash del gold con que se
ajustó. Un calibrador sin procedencia es un número mágico con otro nombre.

### 4.4 Decisión τ/δ (ADR 0010)

Sobre la probabilidad calibrada, usando los estados que **ya existen** en
`modelos.base.EstadoResolucion`:

| Condición | Estado |
|---|---|
| `p₁ ≥ τ` y `p₁ − p₂ ≥ δ` | `RESUELTO_AUTO` |
| `p₁ ≥ τ` y `p₁ − p₂ < δ` | `AMBIGUO` |
| `p₁ < τ` y hubo concepto reconocido | `HUECO_CATALOGO` |
| `p₁ < τ` y no hubo concepto | `SIN_MATCH` |
| Atributo impuesto que ningún producto declara | `HUECO_CATALOGO` |

`AMBIGUO` es el nombre que el proyecto ya le dio a lo que en la conversación llamamos
"clarify", y es un estado de primera clase: va a la cola de revisión humana y su distinción
respecto de `RESUELTO_AUTO` es justamente lo que `resolucion_item.decidido_por` existe para
registrar.

La abstención por atributo de `catalogo` mapea a `HUECO_CATALOGO`, que es lo que ese estado ya
significa: "te entendí y no lo tengo", frente a `SIN_MATCH`, que es "no te entendí". La
distinción está documentada en el docstring del enum y este diseño la respeta.

**τ y δ se eligen sobre la curva precisión-cobertura del gold**, no a ojo, fijando la precisión
objetivo de `RESUELTO_AUTO` y leyendo la cobertura que resulta. El par elegido se registra con
la curva que lo justifica.

---

## 5. Flujo completo

```
renglón + grado
      │
      ▼  catalogo · POST /v1/catalogo/recuperar
  corrección ortográfica → atributos impuestos
      │
      ├── canal léxico   (pg_trgm, variantes_lexicas, stopwords)
      ├── canal denso    (HNSW coseno: concepto y producto)
      └── canal grafo    (sustituibilidad → expansión; co-ocurrencia → prior_grado)
      │
      ▼  unión = pool con puntajes por canal, sin veredicto
      │
      ▼  inteligencia
  Reordenador (cross-encoder │ respaldo logístico)
      │
      ▼  calibrador isotónico → probabilidad
      │
      ▼  τ/δ
  RESUELTO_AUTO │ AMBIGUO │ HUECO_CATALOGO │ SIN_MATCH
      │
      ▼  candidatos con precio y tienda → OE4
```

Lo que este spec entrega al OE4 son **candidatos con `producto_id`, `oferta_id`, `tienda_id`,
precio, `unidad_base` y `unidades_por_empaque`**. Hoy `cargar_indice` colapsa la tienda tomando
`min(precio)`, y eso hay que quitarlo: el OE4 necesita la oferta, no el mínimo. Está detallado
en §3 del spec hermano.

---

## 6. Cambios de esquema, de manifiesto y de ADR

0. **ADR 0019 (bloqueante, va primero).** Enmienda el respaldo del ADR 0005: de RRF a la
   regresión logística, con la medición como evidencia (§4.1.1). Ningún código de este spec se
   escribe antes de que el ADR exista y el `ARQUITECTURA.md` §4 lo refleje.
1. **Migración en `catalogo`**: `concepto` += `embedding vector(1024)`, `embedding_model`,
   `texto_embedding`, e índice HNSW coseno. No agrega tablas: el contador de 70 no cambia.
2. **Siembra de `sustituibilidad_concepto`**: aristas curadas con `motivo` y `curado_por`.
3. **Sin referencias cruzadas nuevas** por parte de este spec: `catalogo` no adquiere
   dependencias de otro dominio. El OE4 sí las agrega y su spec las declara.
4. `pyproject` de `catalogo`: dependencia del adaptador de embeddings, detrás de un extra
   opcional para que la imagen base no cargue el modelo si usa el adaptador remoto.

Regla del ARQUITECTURA §7 que aplica: cualquier referencia cruzada se declara en
`manifiesto.toml` **antes** de escribirse en código, o el invariante 4 tumba la construcción.

---

## 7. Evaluación

### 7.1 Tres métricas, no una

El defecto a corregir es reportar un solo número que mezcla tres fallas distintas:

| Métrica | Pregunta | Qué falla mide |
|---|---|---|
| **Recall de catálogo** | ¿Existe algún candidato correcto en el pool? | Lo que hoy está en 72,3 % |
| **Accuracy de concepto** | ¿El concepto elegido es el correcto? | Falla de clasificación |
| **Precisión de selección** | Dado el concepto correcto, ¿el producto elegido lo es? | Falla de ordenamiento |

Más, por separado: AUC por canal y por fusión, y la curva precisión-cobertura que fija τ/δ.

### 7.2 Ablación

Se corre la evaluación completa quitando un componente por vez: sin grafo, sin canal denso, sin
reordenador (solo respaldo logístico), y sin prior de grado. La afirmación que hay que poder
sostener es **cuánto aporta el grafo**, y eso solo se sabe quitándolo.

### 7.3 Líneas base

Las cuatro ya medidas: `lex` 0,728 · `vec` 0,825 · `rrf` 0,753 · `rerank` 0,879. Un resultado
que no le gane a `vec` solo no es una mejora, por muy híbrido que se llame.

---

## 8. Pruebas, primero

En `servicios/catalogo/tests/`:

- `test_vectorizar.py` — idempotente; no recalcula si el texto no cambió; falla ruidosamente
  si las dimensiones del embebedor no coinciden con la columna.
- `test_recuperar.py` — el pool trae candidatos que el canal léxico solo no alcanzaba; cada
  candidato declara por qué canal entró.
- `test_grafo_conceptos.py` — se construye una vez y se reutiliza; la sustituibilidad se
  respeta como **dirigida** (que un block de dibujo sirva de origami no implica lo contrario).
- `test_prior_grado.py` — `P(concepto | grado)` difiere entre Párvulos y Once para el mismo
  renglón, y un renglón sin grado recibe el marginal y no cero.
- `test_recuperar_sin_red.py` — la ruta del acudiente no alcanza ninguna llamada de red. Es la
  prueba que ya existe en espíritu para `descubrir.py` y que este endpoint no puede romper.

En `servicios/inteligencia/tests/`:

- `test_calibracion.py` — la probabilidad calibrada está en [0,1] y es monótona respecto del
  puntaje crudo; el calibrador registra modelo, fecha y hash del gold.
- `test_umbral_tau_delta.py` — los cuatro estados salen donde deben; el margen manda aunque
  `p₁` sea alta.
- `test_degradacion_reordenador.py` — sin adaptador remoto, el respaldo logístico responde y la
  etapa queda `DEGRADADA`, no `FALLIDA`.

Casos concretos del corpus, que son pruebas y no ejemplos:

- `"block oficio"` → `HUECO_CATALOGO` con razón legible, **nunca** origami.
- `"punzón punta metálica"` → no devuelve correctores de punta fina.
- `"pompones de colores"` y `"chaquiras de colores"` → **no** caen en el concepto `colores`
  (el de los lápices). Es regresión de un defecto ya corregido en `clasificar` y el canal denso
  no puede reintroducirlo.
- `"libro para colorear"` → papelería, no camino editorial.
- `"cuaderno cuadriculado de 100 hojas (BIOLOGÍA)"` → el candidato correcto entra al pool
  (caso real donde la consulta léxica devolvía 0,000).

---

## 9. Trabajo previo reusable

No se parte de cero. Inventario verificado el 2026-09-22:

| Qué | Dónde | Cómo se usa |
|---|---|---|
| `variantes_lexicas` (una frase completa por sustitución) | `tukit-mvp-pipeline/pipeline/stage2_busqueda.py` | Se porta al canal léxico |
| `STOPWORDS_DOMINIO` con su justificación medida | ídem | Se porta, solo al canal léxico |
| `SINONIMOS` — 10 grupos curados a mano | ídem | Semilla de aristas de sinonimia |
| `CONCEPTOS` — 36 grupos de tipo de producto | `pipeline/grafo_sustituibilidad.py` | Semilla de aristas de sustituibilidad |
| Adaptador de reordenador cross-encoder | `pipeline/reranker.py` | Base del adaptador del puerto |
| **2.710 pares anotados** | `calibration/gold_standard_final.csv` | Calibración, τ/δ y toda la evaluación |
| Guiones de calibración y medición de equivalencia | `calibration/*.py` | Referencia de método |

`Tukit-Poc-Tesis/` contiene una copia del mismo prototipo más
`tukit-mvp-pipeline-investigacion/`; se toma `tukit-mvp-pipeline/` como fuente y la otra solo
para consultar el análisis.

Lo que **no** se reusa: la fusión RRF (§1) y la decisión sobre puntaje crudo, que son
precisamente los dos defectos que este spec corrige.

## 10. Lo que este spec NO hace

- No llena los 102 huecos de catálogo (§1.1).
- No toca `POST /v1/catalogo/emparejar` ni el contrato ya publicado.
- No resuelve ISBN ni el camino editorial: para textos la resolución es un lookup de
  `version_vigente`, con cero fuzzy y cero τ, y eso ya está decidido.
- No implementa la cola de revisión de `AMBIGUO`; la alimenta, y la cola ya existe.
- No sustituye el reordenador remoto por uno propio ni lo reentrena.
