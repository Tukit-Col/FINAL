# Guía de curaduría: conceptos, productos y atributos

Cómo crear un concepto, cómo asociarle productos y cómo escribir sus atributos sin dañar el formato
que el emparejador y el optimizador esperan. Es normativa: si algo aquí y el código no coinciden, uno
de los dos tiene un defecto.

- **Para quién:** quien cura el catálogo desde el back-office (`/catalogo`, `/cola`) o editando
  `datos/catalogo/*.csv`.
- **Qué no repite:** la historia de las decisiones y el registro de los conceptos creados están en
  [Curaduría del catálogo](../registros/CURADURIA_CATALOGO.md); el porqué de cada regla del
  emparejador, en el [documento de algoritmos](../algoritmos/main.tex) (§5 y §6).
- **Valores medidos sobre** `datos/catalogo/` el 2026-10-08: 148 conceptos (145 activos) y
  667 productos.

---

## 1. El modelo en un minuto

| Pieza | Qué es | Dónde vive |
|---|---|---|
| **Concepto** | Una clase de cosas intercambiables para el colegio: «Cuaderno», «Témpera», «Juego de geometría» | `datos/catalogo/conceptos.csv`, tabla `concepto` |
| **Producto canónico** | Una cosa concreta que se puede comprar: «Cuaderno cosido 100 hojas cuadriculado Norma» | `productos_canonicos.csv`, tabla `producto_canonico` |
| **Oferta / precio** | Dónde se vende ese producto y a cuánto | `ofertas_tienda.csv`, `precios_oferta.csv` |
| **Nivel** | La calidad de marca del producto: `economico`, `confiable` o `premium` | columna `nivel` del producto |
| **Representante** | El único producto que el kit ofrece por celda (concepto, nivel, personaje) | `es_representante_canonico` |
| **Atributo** | Una propiedad del producto que puede filtrar («tamaño oficio») o solo describir | JSON en `atributos` |

Cómo se usa todo esto al atender una lista: el renglón se clasifica a un **concepto**, del renglón se
leen los atributos que ese concepto declara como **discriminantes**, se descartan los productos que
no los declaran igual, y de los que quedan se ofrece **uno por nivel**. Por eso un concepto mal
partido, un sinónimo mal puesto o un atributo mal escrito no fallan con un error: fallan ofreciendo
el producto equivocado o ninguno.

---

## 2. Antes de crear un concepto

Crear un concepto es la última opción. En orden:

1. **¿Ya existe?** Buscarlo por nombre **y por sinónimos**: «Plumones» duplicaba a «Marcador», que
   ya tenía `plumon` entre sus sinónimos. Un duplicado reparte renglones y productos entre dos
   códigos y ninguno queda completo. Para probar sin gastar cuota de Gemini:

   ```powershell
   python -m tukit_catalogo.consulta "el renglon tal como lo escribe el colegio"
   ```

2. **¿Lo que pide el renglón se puede reemplazar por algo de un concepto existente sin que el
   colegio reclame?** Entonces es ese concepto, con un atributo. Cuaderno cuadriculado y cuaderno
   de cinco materias son el **mismo** concepto (`rayado`, `materias`).
3. **¿El reemplazo no sirve?** Entonces sí es un concepto nuevo. La cartulina iris no es papel iris
   (otro gramaje); la cinta métrica no es cinta adhesiva; el Ecoline (acuarela líquida) no es la
   acuarela en pastilla.
4. **¿Tukit lo vende?** Si no (audífonos, un títere, un computador), el concepto se crea igual,
   pero con tipo `otro`: el acudiente ve «Lo consigues por tu cuenta» y no aparece como hueco.

---

## 3. Crear un concepto, campo por campo

En el back-office: **Catálogo → Nuevo concepto**. El servidor valida lo marcado como *obligatorio*
y rechaza un nombre que ya existe (409, «Agregale productos en vez de duplicarlo»).

### 3.1 `codigo`

Lo asigna el sistema: el siguiente `C###` libre (hoy van hasta `C147`). No se escribe ni se
cambia: el código es lo que viaja por git con la curaduría de listas, y cambiarlo deja huérfanos los
renglones que lo usan. (`dic-ingles` es la única excepción heredada.)

### 3.2 `nombre_canonico` *(obligatorio, único)*

- Singular, mayúscula inicial, con tildes: `Diccionario de inglés`, `Juego de geometría`,
  `Papel crepé`.
- Nombra la cosa, no un producto ni una marca: `Plastilina`, no `Plastilina Play-Doh`.
- No repite la categoría ni agrega cantidades: `Cuaderno`, no `Cuaderno 100 hojas`.

### 3.3 `categoria` *(obligatorio)*

Es el filtro del catálogo público, así que se **elige una de las existentes**; una categoría nueva
solo si ninguna sirve, y nunca una variante de una que ya existe. `Otros / Varios` es el último
recurso, no el cajón por defecto. Las 50 categorías en uso:

| Categoría | Conceptos |
|---|---|
| Acetatos / Fundas plásticas | 2 |
| Agenda escolar / Planeador | 1 |
| Balón / Juegos / Rompecabezas / Ábaco / Lazo | 5 |
| Barras de silicona (pistola) | 1 |
| Bata / Delantal (laboratorio o pintura) | 2 |
| Blocks / Papel para dibujo, plegado, origami o sketch | 5 |
| Borradores | 2 |
| Calculadora | 1 |
| Carpetas / Folders / Legajadores / Sobres manila | 3 |
| Cartuchera | 1 |
| Cartulina | 2 |
| Cinta adhesiva / Enmascarar / Transparente / Aislante | 1 |
| Clips / Ganchos / Grapas / Chinches | 1 |
| Colbón / Pegante líquido / Pegastic | 2 |
| Colores / Crayolas / Crayones | 2 |
| Compás / Estuche de geometría | 2 |
| Corrector | 1 |
| Cuadernos / Bitácoras | 1 |
| Curvígrafo | 1 |
| Diccionario / Biblia / Libros / Constitución | 6 |
| Elementos de aseo (papel higiénico, jabón, gel, toallas, paños) | 9 |
| Elementos de laboratorio (guantes, gafas) | 2 |
| Escuadras | 1 |
| Esferos / Lapiceros / Bolígrafos | 2 |
| Foamy | 1 |
| Instrumentos musicales | 3 |
| Lana, algodón, aserrín, lentejuelas y manualidades varias | 12 |
| Lápices / Portaminas | 3 |
| Maleta / Morral / Mochila | 1 |
| Marcadores / Plumones | 1 |
| Material método Singapur (counters, cubos, fichas) | 1 |
| Natación | 2 |
| Notas adhesivas (Post-it) | 1 |
| Otros / Varios | 15 |
| Palitos / Bajalenguas / Paleta / Pinchos | 1 |
| Papel (seda, crepe, silueta, kraft, periódico, celofán, pliegos) | 6 |
| Pinceles / Lienzos | 2 |
| Plastilina / Masa para moldear | 1 |
| Punzón / Tabla de picar | 2 |
| Reglas | 2 |
| Resaltador | 1 |
| Resma de papel / Hojas de examen | 2 |
| Robótica y electrónica | 12 |
| Tabla periódica | 1 |
| Tajalápiz / Sacapuntas | 1 |
| Tecnología (USB, audífonos, memorias, kits) | 4 |
| Temperas / Vinilos / Pintura / Acuarelas | 9 |
| Tijeras | 1 |
| Transportador | 1 |
| Uniforme / Ropa deportiva / Muda de ropa | 3 |

Se escribe **exactamente** igual, con sus tildes, barras y espacios: dos grafías de la misma
categoría son dos categorías.

### 3.4 `tipo_item` *(por omisión `util`)*

Decide si los renglones del concepto se buscan en el catálogo o se muestran como una nota. Si el
renglón trae tipo propio (de la lista revisada), ese manda; si no, manda el del concepto.

| Valor | Se busca en el catálogo | Qué ve el acudiente | Cuándo usarlo |
|---|---|---|---|
| `util` | sí | el producto, o «No lo tenemos» si el concepto no tiene productos | casi siempre |
| `libro_libre` | sí | el libro | libros donde cualquier edición sirve (diccionario, Biblia) |
| `texto` | no | «Lo consigues por tu cuenta» | libros con edición exacta (título, editorial) |
| `licencia_digital` | no | «Se paga por fuera», con su enlace | plataformas y planes lectores virtuales |
| `no_comprar` | no | «No hay que comprarlo» | lo entrega el colegio, «el que tenga en casa» |
| `diferido` | no | «El colegio lo pedirá después» | «durante el año se solicitarán…» |
| `uniforme` | no | «Uniformes: fuera de Tukit por ahora» | uniformes |
| `otro` | no | «Lo consigues por tu cuenta» | lo que Tukit decidió no vender |

Un `util` sin productos es un **hueco real** y aparece en el informe de huecos para que alguien lo
surta. Un concepto de cualquier otro tipo sin productos no es un hueco.

### 3.5 `sinonimos`

Es lo que hace que la próxima lista se clasifique sola. Es también lo que más daño hace mal puesto.

**Formato:** minúsculas, **sin tildes**, sin puntuación, separados por `|` (en el formulario y en el
CSV): `lapiz negro|lapiz hb|lapiz triangular`.

**La regla de la cabeza.** El emparejador toma del renglón la **primera palabra útil** (después de
quitar cantidades, empaques, medidas y fracciones) y la compara con la **primera palabra** de cada
sinónimo. Una frase que empieza por la cabeza puntúa al menos 0,6; una que la nombra en otra
posición solo puntúa por palabras compartidas; una que no la nombra, 0. Por lo tanto:

- **Un sinónimo sirve si empieza por la palabra con la que el colegio empieza el renglón.**
  «Materiales para generar textura: piedras de bisutería» tiene cabeza `materiales`; el arreglo no
  es tocar otro concepto, es darle al correcto un sinónimo que empiece por `materiales`.
- Plurales y singulares son lo mismo (`lapices` = `lapiz`): no hace falta escribir los dos.
- Las palabras vacías (`de`, `la`, `con`, `para`…) y los números no cuentan.

**Qué no hacer:**

- **No** agregar la frase de un renglón para forzar *esta* lista. Llena el concepto de frases que
  después atraen renglones ajenos. El sinónimo se agrega cuando sirve para listas futuras.
- **No** poner el sinónimo en el concepto que se le parece, sino en el que lo vende: `cinta metrica`
  estaba en *Cinta adhesiva* y arrastraba renglones al concepto equivocado.
- **No** poner un sinónimo genérico que sea la cabeza de muchos renglones (`papel`, `kit`, `set`):
  atrae todo lo que empiece así.
- **No** incluir cantidades ni empaques (`x12`, `caja de`, `100 hojas`): se eliminan antes de
  comparar y solo estorban.

Después de agregar un sinónimo, **probar también los vecinos**: los renglones que antes caían bien
en otro concepto no deben moverse.

### 3.6 Atributos discriminantes y descriptivos

Cada concepto declara qué atributos **filtran** (discriminantes) y cuáles solo **describen**
(descriptivos). Una clave no puede estar en las dos listas.

- **Discriminante:** si el renglón lo menciona (`block oficio` → `tamano=oficio`), solo entran los
  productos que lo declaren y **cumplan** (igual, o con la tolerancia de §5.5); si ninguno cumple, el
  emparejador **se abstiene** y la línea queda como hueco. Úsese solo para lo que, si no coincide,
  el colegio reclamaría.
- **Descriptivo:** se muestra y se edita, pero no filtra.

Reglas:

1. **Solo son discriminantes las claves que el extractor sabe leer de un renglón** (§5.1). Una
   clave que el extractor no conoce nunca se impone, así que declararla discriminante no hace nada.
2. Un discriminante que casi ningún producto declara deja kits vacíos (pasó con `acabado` en
   Cartulina y Papel). Antes de declararlo, los productos del concepto tienen que traerlo.
3. Claves en minúsculas, sin tildes, con `_` en vez de espacio: `tamano`, no `Tamaño`.

### 3.7 Banderas

| Campo | Qué hace | Cómo se fija |
|---|---|---|
| `admite_personaje` | El concepto puede tener productos con personaje (cuaderno, cartuchera, maleta…). Hoy 19 conceptos | formulario |
| `uno_por_estudiante` | Es una herramienta que dura todo el año: si varias materias la piden, se compra una vez por hijo (la cantidad mayor, no la suma). Antes de elegir, todos los renglones del concepto se quedan con los productos que sirven para todos (`compás` y `compás de precisión` compran un solo compás de precisión). Hoy: Colores, Tajalápiz, Regla, Cartuchera, Tijeras, Compás, Transportador, Tabla periódica, Calculadora, Diccionario, Juego de geometría, Biblia, Bata de laboratorio, Portabasura | **solo en `conceptos.csv`** (`true`/`false`) |
| `frecuencia_demanda` | Cuántas veces lo piden las listas | lo calcula el sistema; no se edita |
| `activo` | Un concepto fundido en otro se **desactiva**, no se borra | formulario / CSV |

Lo que se gasta (pegante, cinta, cuadernos) **no** es `uno_por_estudiante`: puede pedirse uno por
materia a propósito.

---

## 4. Asociar productos a un concepto

### 4.1 Por dónde entran

| Camino | Cuándo | Qué crea |
|---|---|---|
| **Cola de propuestas** (`/cola`) | La revisión de una lista nueva propuso productos de tiendas para renglones sin producto | Al aprobar: producto `TK-REV-<referencia>`, con su oferta |
| **Alta de útil** (`/catalogo`, pestaña de alta) | Se busca a mano en una tienda y se elige | Una propuesta en la cola; se aprueba igual |
| **Alta de libro** | Libros: lo que identifica un libro es el ISBN de una edición, no una búsqueda por título | Producto del concepto de libro, con ISBN |
| **CSV** (`productos_canonicos.csv`) | Carga masiva o semillas | Productos `TK-C###-NIV[-PERSONAJE]` (semilla del corpus) |

Toda propuesta pasa por una persona. Una búsqueda por texto devuelve productos reales, con foto y
precio, que no son lo pedido («punzón punta metálica» trae correctores de punta fina); ningún umbral
lo detecta, una persona sí.

### 4.2 A qué concepto va un producto

Al concepto cuyo reemplazo el colegio acepta (§2). Si el producto sirve para dos conceptos, va al
más específico (una «caja matemática» con compás y reglas es un *Juego de geometría*, no un
*Compás*). Para moverlo después, **Reclasificar** en el editor del producto: conserva sus ofertas y
su historia.

### 4.3 Campos del producto

| Campo | Formato y reglas |
|---|---|
| `nombre` | El de la tienda, legible; es de donde el extractor saca empaque y atributos, así que no se le quitan medidas ni cantidades |
| `marca` | Tal como se escribe la marca: `Norma`, `Faber-Castell` |
| `nivel` | `economico`, `confiable` o `premium` (minúsculas, sin tildes). Dentro de cada concepto el precio tiene que ordenar el nivel: económico ≤ confiable ≤ premium. La exportación lo corrige permutando etiquetas (§6), pero conviene ponerlo bien desde el principio |
| `personaje` | Vacío si no tiene. Si tiene: **minúsculas, sin tildes**, el nombre corto del personaje (`bluey`, `spiderman`, `paw patrol`, `stitch`). Ver §5.4 |
| `unidad_base` | `unidad`, `hoja`, `pliego`, `metro`, `gramo` o `mililitro`: en qué se cuenta lo que pide la lista |
| `unidades_por_empaque` | Entero ≥ 1: cuántas unidades base trae lo que se compra. Una caja de 12 lápices es 12; un cuaderno de 100 hojas es **1** (las hojas son atributo, no empaque). Es columna de `productos_canonicos.csv` desde 2026-10-11: antes solo vivía en la base y cada recarga lo dejaba en 1. `enriquecer` lo lee del nombre solo cuando vale 1; un valor mayor se respeta como curado |
| `imagen_url` | URL de la ficha de la tienda, o vacío |
| `quality_score` | Entre 0 y 1. Lo propuesto por una máquina entra bajo a propósito |
| `atributos` | Ver §5 |

**Los SKU no se escriben ni se editan a mano.** `TK-C###-NIV[-PERSONAJE]` es la semilla del corpus
(el código del concepto, las tres primeras letras del nivel y el personaje en mayúsculas);
`TK-REV-<referencia>` es lo aprobado en la cola. Al reclasificar un producto semilla, la exportación
re-acuña su SKU con el concepto nuevo.

### 4.4 Representante y profundidad

Por cada celda (concepto, nivel, personaje) hay **exactamente un representante**: es el que el kit
ofrece. Los demás productos aprobados de la celda son profundidad de compra detrás de él. La
exportación lo garantiza (prefiere el producto semilla de la celda y, si no hay, el más barato), así
que no hace falta marcarlo a mano, pero sí revisar que el elegido sea razonable.

---

## 5. Atributos: formato de los valores

### 5.1 Reglas generales

El emparejador compara un atributo impuesto con el del producto como **texto en minúsculas**
(`str(valor).lower()`), salvo los atributos que se miden, que admiten la tolerancia de §5.5. De ahí
salen todas las reglas:

1. **Un valor por clave, escalar:** texto, número o booleano. Listas y objetos se rechazan.
2. **Texto en minúsculas y sin tildes:** `pequeno`, `espanol`, `cafe`. Las mayúsculas no rompen la
   comparación, pero las tildes y los espacios sí: `pequeño` ≠ `pequeno`, `15x15 cm` ≠ `15 x 15 cm`.
3. **El valor sale del vocabulario de la tabla (§5.2)**, exactamente como está escrito. Un valor
   inventado (`cuadriculada`, `grande ` con espacio) nunca coincide con lo que el extractor lee del
   renglón, y el producto queda fuera de todo filtro.
4. **Medidas: número, un espacio y la unidad abreviada,** con punto decimal: `40 g`, `75 ml`,
   `30 cm`, `0.7 mm`, `3 m`, `30.5 x 30.5 cm`. Unidades: `g`, `kg`, `ml`, `l`, `mm`, `cm`, `m`.
5. **Conteos: número entero, sin unidad:** `hojas: 100`, `unidades: 12`. En el editor se escribe
   `100` y el editor lo guarda como número.
6. **Booleanos: `true` o `false`, en minúsculas.** El editor convierte `true`/`false` a booleano;
   `True` con mayúscula se guarda como **texto**. (Hoy hay un producto con `deposito: "True"`).
7. **Ausente antes que inventado.** Si no se sabe, la clave se deja vacía (no se guarda). Nunca
   `desconocido`, `n/a` ni el valor más frecuente: un atributo inventado hace elegir con confianza
   el producto equivocado; uno ausente manda el renglón a revisión.
8. **Surtidos:** un producto de varios colores lleva `color: surtido`, no una lista de colores.

### 5.2 Vocabulario por atributo

Las claves que el extractor sabe leer de un renglón y, por lo tanto, las únicas que pueden ser
**discriminantes**. Los valores son los que produce el extractor; el producto tiene que usar los
mismos.

| Clave | Tipo | Valores | Ejemplo |
|---|---|---|---|
| `tamano` | texto | `a3`, `a4`, `carta`, `media carta`, `oficio`, `tabloide`, `pliego`, `medio pliego`, `cuarto`, `cuarto de pliego`, `octavo`; o medidas `N x N cm`; o, para morrales y cartucheras, `pequeno`, `mediano`, `grande`, `extragrande` | `octavo`, `15 x 15 cm` |
| `color` | texto | `amarillo`, `azul`, `beige`, `blanco`, `cafe`, `celeste`, `cian`, `crema`, `dorado`, `fucsia`, `gris`, `kraft`, `magenta`, `morado`, `naranja`, `negro`, `neon`, `plateado`, `rojo`, `rosado`, `surtido`, `turquesa`, `verde`, `vinotinto`, `violeta` | `surtido` |
| `tinta` | texto | los mismos de `color` (es el color de la tinta, no del cuerpo) | `negro` |
| `rayado` | texto | `blanco`, `cuadriculado`, `cuadricula grande`, `cuadricula pequena`, `cuadrovia`, `doble linea`, `ferrocarril`, `milimetrado`, `pentagramado`, `rayado`, `triple linea` | `cuadriculado` |
| `encuadernacion` | texto | `cosido`, `argollado` | `cosido` |
| `presentacion` | texto | `barra`, `bolsa`, `crema`, `dactilar`, `frasco`, `gel`, `liquido`, `paquete`, `pastilla`, `polvo`, `sobre`, `spray`, `tubo`. Un tarro es `frasco`: son lo mismo para el colegio | `barra` |
| `material` | texto | `acero`, `acrilico`, `aluminio`, `antifluido`, `carton`, `caucho`, `foamy`, `icopor`, `latex`, `madera`, `metal`, `nitrilo`, `plastico`, `silicona`, `tela`, `vidrio` | `plastico` |
| `forma` | texto | `abanico`, `biselado`, `cuadrado`, `ergonomico`, `espatulado`, `hexagonal`, `lengua de gato`, `plano`, `rectangular`, `redondo`, `triangular` | `redondo` |
| `punta` | texto | `micropunta`, `punta bala`, `punta biselada`, `punta fina`, `punta gruesa`, `punta pincel`, `punta roma` | `punta roma` |
| `grosor` | texto | `delgado`, `pequeno`, `mediano`, `grueso`, `extra grueso` (`jumbo` se lee `grueso`); para pinceles, la serie `n` + número (`n5`, también escrita `# 5`); o una medida (`2 mm`). En Lápiz y Colores, el producto que no dice ser grueso lleva `delgado` | `n6` |
| `dureza` | texto | `hb`, `b`, `bb`, `h`, `hh`, `2b`…`9b`, `2h`…`9h` | `hb` |
| `tipo` | texto | un término del vocabulario de tipos: `acrilico`, `acuarela`, `aislante`, `argollado`, `baloncesto`, `balso`, `basica`, `blanco`, `bond`, `borrable`, `cartulina`, `celofan`, `celuguia`, `cientifica`, `colorear`, `con ruedas`, `cosido`, `cuadriculado`, `de escritorio`, `dibujo`, `doble faz`, `doble linea`, `dulce`, `enmascarar`, `escolar`, `examen`, `ferrocarril`, `fotografico`, `fuelle`, `futbol`, `futbol de salon`, `gigante`, `hembra-hembra`, `hexagonal`, `horizontal`, `humeda`, `intercambiable`, `iris`, `jumbo`, `kraft`, `lavable`, `legajador`, `lija`, `loza`, `macho-hembra`, `macho-macho`, `mariposa`, `miga de pan`, `milimetrado`, `montessori`, `morral`, `nata`, `oleo`, `origami`, `paleta`, `panuelo`, `papel`, `permanente`, `pincho`, `plato`, `por numeros`, `precision`, `propalcote`, `quirurgico`, `rayado`, `retractil`, `rompecabezas`, `soprano`, `tela`, `tempera`, `transparente`, `traversa`, `triangular`, `universitario`, `vaso`, `vertical`, `vinilo`, `voleibol` | `oleo`, `rayado` |
| `acabado` | texto | `escarchado`, `figuras`, `fluorescente`, `iris`, `metalizado`. Tabla propia desde 2026-10-11: leído con la de tipos, el acabado de una témpera fluorescente era `tempera` | `fluorescente` |
| `idioma` | texto | `espanol`, `ingles`, `frances`, `aleman`, `latin`; bilingües unidos con `-` en orden alfabético (`espanol-ingles`, sea cual sea el orden en que se escribieron). El monolingüe pedido a propósito (`Inglés – Inglés`) se escribe doble: `ingles-ingles` | `espanol-ingles` |
| `edicion` | texto | `completa`, `infantil` (Biblias) | `infantil` |
| `ano` | texto | años unidos con `-`, o `permanente` (agendas) | `2026-2027` |
| `gramaje` | texto | número + ` g` o ` kg` | `75 g` |
| `capacidad`, `volumen` | texto | número + ` ml` o ` l` | `450 ml` |
| `longitud`, `calibre` | texto | número + ` mm`, ` cm`, ` m` o ` in` (pulgadas) | `30 cm`, `8.5 in` |
| `hojas` | entero | número de hojas (cuando el concepto declara `hojas`, describe y no cuenta empaque) | `100` |
| `unidades` | entero | unidades del empaque, mayor que 1 | `12` |
| `colores` | entero | número de colores | `12` |
| `piezas` | entero | piezas o fichas | `100` |
| `grados` | entero | ángulo (transportadores) | `360` |
| `compartimentos`, `orificios` | entero | cantidad | `2` |
| `materias` | entero o texto | número de materias (también escrito en letras: `tres materias`), o `multiple`. Es el **único** atributo con valor por omisión: un cuaderno que no dice nada es de `1` materia. `multiple` no cumple ni 3 ni 5: hay que poner el número | `1`, `3` |
| `notas` | entero | placas, notas o tonos (xilófonos) | `8` |
| `puntos` | entero | puntos o contactos (protoboards) | `830` |
| `manga` | texto | `corta`, `larga` (`con mangas` es `larga`) | `larga` |
| `deposito` | booleano | `true` / `false` (tajalápices). `portabasura` se lee como depósito | `true` |
| `monolingue` | booleano | en desuso desde 2026-10-11: los diccionarios filtran por `idioma` | — |

Valores que el extractor lee pero que **no se le exigen a un producto**: `tipo = escolar`. Casi todo
en una lista dice «escolar», y exigirlo dejaba sin opciones a 27 maletas.

**Claves solo descriptivas** que hoy usan algunos conceptos y que el extractor no lee: `talla`,
`formato`, `ancho`, `largo`, `angulo`, `vigencia`, `titulo`, `caras`, `version`,
`dimensiones`, `contenido`. Se llenan a mano, con las mismas reglas de §5.1, y **no** pueden ser
discriminantes.

### 5.3 Valores compuestos

- Medidas en dos dimensiones: `ancho x alto cm`, con espacios alrededor de la `x`: `20 x 20 cm`.
- Idiomas: unidos con `-` sin espacios, en orden alfabético: `espanol-ingles`.
- Años: unidos con `-` sin espacios, en el orden en que aparecen: `2026-2027`.

### 5.4 Personajes

Se comparan sin distinguir mayúsculas al armar el kit Fan, pero la exportación agrupa la escalera
de niveles por el texto **exacto** del personaje, y el SKU semilla lo lleva en mayúsculas. `Frozen` y
`frozen` son, para la nivelación, dos escaleras distintas. Por eso: **minúsculas, sin tildes**, el
nombre corto con que lo pide un acudiente (`spiderman`, `minnie`, `paw patrol`, `hello kitty`).

**Cuidado al aprobar desde la cola.** Al aprobar una propuesta, el sistema deduce el personaje del
nombre del producto con una tabla que lo escribe con mayúsculas (`Frozen`, `Mickey Mouse`, `Kiut`).
Hasta que eso se corrija en el código (ver [pendientes](../PENDIENTES.md)), hay que revisar el
personaje del producto recién aprobado y pasarlo a minúsculas en el editor.

### 5.5 Cómo se compara cada atributo

Lo que cambia **qué cosa es** se compara exacto: `materias`, `rayado`, `tipo`, `color`, `punta`,
`edicion`, `encuadernacion`, `forma`. Lo que **se mide** admite lo cercano (`consulta.py`,
`_valor_cumple`):

| Atributo | Cómo cumple | Ejemplo |
|---|---|---|
| `hojas` | al menos lo pedido y a lo sumo el doble | piden 80, sirve 100; no 200 |
| `unidades`, `colores`, `piezas`, `notas`, `gramaje`, `peso`, `capacidad` | al menos lo pedido | piden caja x12, sirve x15; no x10 |
| `puntos` | al menos lo pedido y a lo sumo 2,2 veces | piden 400, sirve 840; no 2.200 |
| `longitud` | entre 0,85 y 1,35 veces lo pedido, en cualquier unidad | piden escuadra de 20 cm, sirve la de 26 |
| `tamano` en medidas | cada lado con hasta un 25 % de diferencia, sin importar la orientación | piden lienzo de 25 x 25, sirve 20 x 30 |
| `tamano` | `carta` y `a4` son equivalentes | sketchbook carta: sirve el A4 |
| `material` | `plastico` y `antifluido` son equivalentes | delantal plástico: sirve el antifluido |
| `idioma` | `ingles` a secas acepta también `espanol-ingles`; `ingles-ingles` solo el monolingüe | diccionario de inglés: sirve el bilingüe |

**Lo que el producto no declara no cumple.** Es un hueco honesto, no un sustituto: si el producto
sí sirve, se le agrega el atributo.

**Varios a la vez.** En los conceptos que filtran por `unidades` (Marcador, Colores, Pincel,
Plastilina), un renglón que dice `caja`, `estuche`, `paquete`, `set`, `kit` o `juego`, o que empieza
en plural con cantidad 1 (`marcadores`), pide más de uno. Si ningún juego cumple, vale la pieza
suelta. En un juego de piezas distintas (`kit de pinceles delgados, planos, redondos y abanico`)
no se le exige al juego lo que describe cada pieza (`grosor`, `forma`).

### 5.6 En la lista: lo que corrige el revisor

En `listas_revisadas.csv`, cada renglón puede llevar:

- **`tipo_item`**, cuando el colegio no pide comprarlo aunque el concepto se venda: `no_comprar`
  para lo que ya se tiene (`cuaderno del año anterior`, `la misma bata`, `el disponible en casa`),
  `otro` para lo que el estudiante elige o arma (`lectura libre guiada`, `libro de recortes`),
  `uniforme` para lo que se hace «según modelo». Vacío, manda el tipo del concepto.
- **`atributos`**, que mandan sobre lo leído del texto, con las mismas claves y valores de §5.2. El
  valor `*` **quita** un atributo leído: la bitácora que trae la receta «15 hojas de cartulina…» se
  cura con `{"tipo": "dibujo", "tamano": "*"}`.

  **Desde el admin**, sin tocar el CSV: en la revisión de la lista (`/onboarding/{version_id}`,
  región 3) «Editar» un renglón muestra **«Atributos que se exigen»**: por cada atributo
  discriminante del concepto, lo que se leyó del texto y lo curado, y lo que resulta exigido. Ahí
  se cambia el valor (sugiere los que declaran los productos del concepto), se marca **«No
  exigir»** (guarda `*`), se agrega uno de los discriminantes que el texto no dice o se quita la
  curaduría para volver a lo leído; viaja en «Guardar cambios». Solo se pueden curar claves que el
  concepto filtra (la ruta rápida ignoraría otra: el backend la rechaza con
  `atributo_no_exigible`); lo que el renglón ya traía con el mismo valor se deja pasar, para no
  romper lo curado antes ni lo que quedó de otro concepto: se rechaza solo una clave nueva o
  cambiada. El «más de uno» que se deduce de `caja de…`, `kit` o un plural (§5.5) sale marcado
  como *deducido*: el texto no lo dice, y si ningún juego cumple vale la pieza suelta. Si se cambia el concepto, se guarda primero y se vuelve a abrir: lo leído
  se recalcula con el concepto nuevo. Una lista ya revisada no se edita en su lugar: «Editar (nueva
  versión)» en la página del grado la clona y cae en esa misma pantalla. Después, **exportar**
  (§6) para que la curaduría llegue al CSV.
- **`cantidad` en unidad base**: «3 paquetes de octavos» son `30` octavos y «2 cajas de colores
  x 12» son `24` colores. El kit compra los paquetes que hagan falta para cubrirla
  (`techo(cantidad / unidades_por_empaque)`); con la cantidad en paquetes, compraría de menos.
- **Un renglón por cosa.** «Transportador, compás de precisión» o «Gorro y gafas» se parten: la
  segunda cosa va en un renglón nuevo al final del grado, con su concepto y un texto que dice de
  qué renglón salió.

---

## 6. Después de curar

1. **Exportar** a `datos/` para que la curaduría viaje por git:

   ```powershell
   .\tukit.ps1 exportar        # o: make curaduria-exportar
   ```

   Corre, en este orden y sin opción de saltarlos: elegir representantes, volcar la base a los CSV,
   nivelar (permuta las etiquetas de nivel para que el precio las ordene) y recargar la base desde
   los CSV para comprobar que lo exportado se lee.
2. **Vectores** de los productos nuevos o cambiados (gasta cuota de Gemini Embedding; solo recalcula
   lo que cambió):

   ```powershell
   .\tukit.ps1 embeddings
   ```

3. **Probar** los renglones que motivaron el cambio y sus vecinos (sin Gemini):

   ```powershell
   python -m tukit_catalogo.consulta "renglon 1" "renglon 2"
   ```

4. **Regenerar los kits canónicos** si cambió cómo se arman los de una lista ya aprobada:

   ```powershell
   python -m tukit_inteligencia.poller --regenerar-canonicos
   ```

5. **Commit** de `datos/` y, si se creó un concepto o se decidió algo que cambia el comportamiento,
   su registro en [Curaduría del catálogo](../registros/CURADURIA_CATALOGO.md).

---

## 7. Lista de verificación

**Concepto nuevo**

- [ ] Busqué por nombre y por sinónimos y no existe.
- [ ] El reemplazo por un concepto existente no serviría al colegio.
- [ ] Nombre en singular, con mayúscula inicial y tildes.
- [ ] Categoría tomada de la lista, escrita exactamente igual.
- [ ] Tipo correcto (§3.4): si Tukit no lo vende, `otro`.
- [ ] Sinónimos en minúsculas, sin tildes, separados por `|`, y que empiezan por la cabeza con que
      los colegios lo escriben.
- [ ] Discriminantes solo de la tabla de §5.2, y los productos del concepto los declaran.
- [ ] Probé el renglón y sus vecinos con `tukit_catalogo.consulta`.

**Producto**

- [ ] Está en el concepto cuyo reemplazo acepta el colegio.
- [ ] Nivel coherente con el precio frente a los otros niveles del concepto.
- [ ] `unidades_por_empaque` cuenta lo que se compra, no las hojas ni los mililitros.
- [ ] Si el concepto filtra por algo que el nombre no dice (el tamaño de una carpeta, la manga de
      una bata), el atributo está puesto a mano; sin él, el producto no le sirve a ningún renglón que
      lo pida.
- [ ] Atributos: claves en minúsculas, valores del vocabulario, números como números, medidas como
      `N unidad`, booleanos `true`/`false`, nada inventado.
- [ ] Personaje en minúsculas, sin tildes, o vacío.

---

## 8. Valores que hoy no cumplen esta guía

Medidos sobre `datos/catalogo/` el 2026-10-08. Se corrigen editando el producto y exportando.

| Dónde | Qué tiene | Qué debería tener |
|---|---|---|
| Un producto con `deposito` | el texto `"True"` | el booleano `true` |
| 24 de los 76 productos activos con personaje | con mayúsculas: `Kiut` (6), `Barbie` (3), `Mickey Mouse` (3), `Avengers`, `Frozen`, `Hot Wheels`, `Unicornio` (2 cada uno), `Dinosaurios`, `Flower Power`, `My Melody`, `Totto` (1 cada uno) | en minúsculas. `Frozen` además convive con `frozen`, así que hoy son dos escaleras de nivel distintas |

La mayoría vienen de aprobaciones de la cola (§5.4): corregir los datos sin corregir el código solo
los vuelve a producir.
