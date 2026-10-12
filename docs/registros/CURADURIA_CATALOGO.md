# Curaduría del catálogo y los conceptos: registro de la rama `feature/curaduria-de-listas`

- **Tipo:** registro de aplicación. Documenta un trabajo ya hecho y deja las reglas para continuarlo.
- **Fecha:** 2026-10-04.
- **Rama:** `feature/curaduria-de-listas` (commits `c57c0b3` a `6bffea2`, sin fusionar a `main`).
- **Material curado:** las listas 2026 del Colegio Agustiniano Ciudad Salitre (CACS), de
  Jardín a Undécimo, subidas una a una por el back-office.
- **Decisiones registradas aparte:** ADR [0037](../arquitectura/adr/0037-la-curaduria-viaja-por-git.md),
  [0038](../arquitectura/adr/0038-el-concepto-asignado-en-la-revision-manda.md) y
  [0027](../arquitectura/adr/0027-lo-que-tukit-no-vende-se-clasifica.md).

---

## 0. Qué cambió, en cifras

| | Al abrir la rama | Al cerrar este registro |
|---|---|---|
| Conceptos | 99 del corpus (`C001`–`C099`) | 148 (145 activos, 49 creados curando: `C100`–`C147` y `dic-ingles`) |
| Productos canónicos | los de la semilla | 685, de ellos 450 aprobados en la cola (`TK-REV-`) y 18 libros (`TK-LIB-`) |
| Conceptos activos por tipo | casi todos `util` | 131 `util`, 5 `otro`, 4 `libro_libre`, 2 `no_comprar`, 1 `uniforme`, 1 `texto`, 1 `licencia_digital` |
| Curaduría compartida | solo en la base de quien curaba | por git: `datos/curaduria/` y `datos/catalogo/` |

La regla de fondo, puesta por el dueño del producto al delegar las decisiones: **se corrige lo
que es lógico para el negocio, no lo que hace que una prueba deje de fallar.** Varias veces el
arreglo cómodo era meter un sinónimo en el concepto que ya tenía productos para que el kit
"saliera completo"; se descartó cada vez que el producto ofrecido no era lo que el colegio pedía.
Una línea que dice "No lo tenemos" es honesta; un producto equivocado en el carrito no.

---

## 1. Cómo decide el emparejador (lo que hay que saber para curar bien)

Curar sin este modelo es adivinar. Todo lo que sigue vive en
`servicios/catalogo/tukit_catalogo/descubrir.py` (clasificar) y `consulta.py` (emparejar).

### 1.1 La cabeza

Del renglón se quita el ruido —cantidades, empaques (`paquete`, `caja`, `pliego`, `metro`),
fracciones (`1/8`), medidas y palabras vacías— y la **primera palabra útil** es la cabeza: lo
que se pide. `"3 bolsas de aserrín de colores"` tiene cabeza `aserrin`.

Por cada concepto se prueban su nombre y sus sinónimos:

- Si el candidato **empieza** por la cabeza: `0.6 + 0.4 · Jaccard(renglón, candidato)`.
- Si solo **la nombra** en otra posición: `Jaccard`.
- Si no la nombra: 0, salvo rescate semántico (coseno ≥ 0.86 contra el vector del concepto).

Gana el mayor; por debajo de 0.5 el renglón queda sin concepto y va a revisión.

**Consecuencia práctica para curar:** un sinónimo sirve si empieza por la palabra con la que el
colegio empieza el renglón. `"Materiales para generar textura: piedras de bisutería"` tiene
cabeza `materiales` y por eso se lo llevaba *Material Singapur*. El arreglo no es tocar Singapur:
es darle al concepto correcto un sinónimo que empiece igual que el renglón.

### 1.2 Atributos discriminantes y descriptivos

Cada concepto declara qué atributos **filtran** (discriminantes) y cuáles solo **describen**.
Si el renglón trae un discriminante (`block oficio` → `tamano=oficio`), solo entran productos que
lo declaren igual; si ninguno lo declara, el emparejador **se abstiene** en vez de ofrecer otro.
Por eso un atributo mal declarado como discriminante deja kits vacíos (el caso de `acabado` y de
`tipo=escolar`, §5), y un atributo que debería filtrar y no lo hace mete productos equivocados.

El vocabulario de atributos es fijo y está en `enriquecer.py` (`TAMANOS`, durezas, tipos…).

### 1.3 El tipo decide si se busca en el catálogo

| Tipo | Se busca en el catálogo | Qué ve el acudiente |
|---|---|---|
| `util` | sí | el producto, o **"No lo tenemos"** si el concepto no tiene productos |
| `libro_libre` | sí | el libro (diccionarios, Biblia: cualquier edición sirve) |
| `texto` | no | **"Lo consigues por tu cuenta"** (edición exacta que vende una librería) |
| `licencia_digital` | no | **"Se paga por fuera"**, con su enlace |
| `no_comprar` | no | **"No hay que comprarlo"** (lo entrega el colegio, el de casa) |
| `diferido` | no | **"El colegio lo pedirá después"** |
| `uniforme` | no | **"Uniformes: fuera de Tukit por ahora"** |
| `otro` | no | **"Lo consigues por tu cuenta"**: Tukit decidió no venderlo |

Si el renglón tiene tipo propio, manda sobre el del concepto; si no, el del concepto manda
(ADR 0038). La clasificación de líneas para pintar vive una sola vez en
`libs/ts/tukit-contrato/src/linea.ts` y la comparten `web` y `admin`.

---

## 2. Criterios de curaduría

Estas reglas salieron de casos concretos de la sesión y son las que hay que seguir.

**2.1 Concepto genérico, atributos para lo que filtra.** Un concepto es *lo que se puede
reemplazar por otro del mismo concepto sin que el colegio reclame*. Cuaderno 5 materias y
cuaderno cuadriculado son el mismo concepto con atributos distintos. Se crea un concepto aparte
solo cuando el reemplazo **no** sirve: la cartulina iris no es papel iris (gramaje distinto); la
cinta métrica no es cinta adhesiva; el Ecoline (acuarela líquida) no es la pastilla de acuarela.

**2.2 Antes de crear, buscar.** Un concepto duplicado reparte renglones y productos entre dos
códigos y ninguno de los dos queda completo. *Plumones* (`C104`) duplicaba a *Marcador* (`C006`),
que ya tenía `plumon` entre sus sinónimos: se fundió y se desactivó. *Juego geométrico* (`C105`)
duplicaba a *Juego de geometría* (`C036`): desactivado.

**2.3 El sinónimo va en el concepto que lo vende, no en el que se parece.** Se encontraron
sinónimos del corpus colgados del concepto equivocado porque compartían una palabra:
`cinta metrica` en *Cinta adhesiva*, `maleta capacidad carpeta tamaño oficio` en *Carpeta*,
`sobre de acetato` en *Acetato*, `diccionario ingles` en el de español, `plan lector` en *Libro*.
Cada uno arrastraba renglones al concepto equivocado.

**2.4 Si Tukit no lo vende, decirlo con el tipo.** Audífonos, un títere, vestuario de
presentación, un computador o una tablet, componentes de robótica raros (relay, puente H,
joystick): no son huecos del catálogo, son decisiones. Van con tipo `otro` y el acudiente lo ve
como "Lo consigues por tu cuenta" (ADR 0027). Un `util` sin productos, en cambio, es un hueco
real y aparece en el reporte de huecos para que alguien lo surta.

**2.5 Lo que el colegio entrega o cobra aparte no se busca.** *Lo entrega el colegio*
(`C137`, `no_comprar`), *Plan lector virtual* (`C133`, `licencia_digital`) y *Libro o texto con
título* (`C134`, `texto`) existen para que la revisión pueda asignar esos renglones sin que el
pipeline intente venderlos. El selector de conceptos del catálogo de productos solo muestra los
que se buscan (`util`, `libro_libre`), para no ofrecer agregarle productos a un uniforme.

**2.6 Nombres normalizados.** Mayúscula inicial y tildes (`Diccionario de inglés`, no
`diccionario ingles`); la categoría es una de las del corpus (es el filtro del catálogo público).
Los sinónimos se escriben sin tildes y en minúscula, como los compara el emparejador.

---

## 3. El flujo de trabajo del curador

1. Subir la lista en el back-office (`/cola` → *Subir lista*). La percepción con Gemini la
   parte en renglones.
2. Abrir la versión pendiente. Para cada renglón sin concepto o con el concepto equivocado:
   - si el concepto existe, asignarlo y, si el texto lo justifica, **agregarle el sinónimo**
     para que la próxima lista entre sola;
   - si no existe, crearlo con su tipo correcto (§1.3) y su categoría.
3. *Previsualizar los kits* para ver lo que verá el acudiente. La previsualización respeta el
   concepto asignado en la revisión (ADR 0038).
4. Aprobar. La versión queda revisada y el pipeline la reutiliza para todos los acudientes de ese
   colegio y grado.
5. Exportar y hacer commit:

   ```powershell
   .\tukit.ps1 exportar          # o: make curaduria-exportar
   git add datos/ ; git commit
   ```

Para probar un cambio de sinónimos **sin gastar cuota de Gemini**, el emparejamiento se puede
correr solo por palabras contra la base (`consulta.emparejar_en_catalogo` sin vectores). Así se
verificó cada concepto de este registro, incluidos los vecinos que no debían moverse.

Los compañeros, después de `git pull`, corren `.\tukit.ps1 importar` (o
`make curaduria-importar`). El detalle está en el README, *Compartir la curaduría de listas*.

---

## 4. La curaduría viaja por git

Hasta esta rama, curar dejaba todo en la base local. Ahora (ADR 0037):

| Archivo | Lo escribe | Qué lleva |
|---|---|---|
| `datos/curaduria/listas_revisadas.csv` | `tukit_catalogo.curaduria exportar` | la última versión revisada de cada lista, renglón por renglón, con el concepto por código |
| `datos/curaduria/colegios.csv`, `sedes.csv` | `tukit_identidad.curaduria exportar` | los colegios que esas listas nombran, sin datos de contacto |
| `datos/catalogo/conceptos.csv` | `curaduria exportar` (fusión) | conceptos creados y sinónimos editados; no toca los conceptos de libros |
| `datos/catalogo/productos_*.csv`, `ofertas_tienda.csv`, `precios_oferta.csv` | `volcar --escribir` | productos aprobados, reclasificados y sus atributos corregidos a mano |

`exportar` encadena cuatro pasos que no son opcionales, porque el CSV de productos tiene pruebas
de calidad (`test_catalogo_curado`) que la tesis cita:

1. **`representantes --escribir`**: exactamente un representante por celda (concepto, nivel,
   personaje), prefiriendo el producto semilla (`TK-C###-`) y si no el más barato.
2. **`volcar --escribir`**: de la base al CSV; nivel y atributos salen de la base (lo editado en
   el back-office), y la procedencia sigue al SKU vigente.
3. **`nivelar --escribir`**: ordena la escalera de precios económico < confiable < premium.
4. **`cargador`**: recarga la base desde el CSV, para comprobar que lo exportado se lee.

Cada uno de esos pasos existe porque su falta rompió una prueba durante la sesión: celdas con
dos representantes, EAN de 12 dígitos (se normalizan a 13 con `ean13`), SKU semilla que
nombraban el concepto viejo después de reclasificar (ahora se re-acuñan, con sufijo si chocan,
y se actualizan las referencias en `inteligencia`) y escaleras invertidas.

**Lo que no viaja:** los vectores (cuestan cupo de Gemini Embedding; `make bd-enriquecer` los
calcula después de importar), el PDF original, el contacto de los colegios y los **kits
canónicos**. Estos viven en la base de `inteligencia`, que la curaduría no toca; en su lugar,
`importar` deja por cada lista el mismo evento `lista_aprobada` que deja aprobarla en la cola, y
el poller de `inteligencia` arma el Ahorrador y el Premium en la máquina que importó. Hace falta
tener los servicios arriba (`.\tukit.ps1 arriba`) para que se armen; si se importa con todo
apagado, los eventos esperan en la bandeja y salen al levantar. Una versión que ya tiene sus
canónicos no se vuelve a optimizar, así que importar dos veces no cuesta nada.

**Defecto encontrado al escribir este registro** (`6bffea2`): el exportador pedía versiones
*vigentes y revisadas*. Volver a subir la lista de Jardín dejó vigente una versión sin revisar,
y desde `f23d2f1` la lista curada había dejado de exportarse sin que nada avisara. Ahora se
exporta la **última revisada** de cada lista, con una prueba para ese caso.

---

## 5. Cambios al emparejador

Cada fila es un renglón real que fallaba. La prueba que lo fija está en
`servicios/catalogo/tests/`.

| Renglón | Qué pasaba | Causa | Arreglo | Commit |
|---|---|---|---|---|
| `Maleta escolar` | ninguna de las 27 maletas | `escolar` se leía como `tipo=escolar` y ningún producto lo declara | `tipo=escolar` no se exige desde un renglón (afectaba a los 11 conceptos que filtran por tipo) | `46e6e76` |
| `Flauta dulce` | ninguna flauta | `Flauta Dulce … Soprano` se leía `tipo=soprano` | `dulce` va antes que `soprano` en el vocabulario | `e263ab2` |
| `metro de cable estañado` | caía en Lentejuelas | cabeza `metro` (sinónimo `metro lentejuelas`) | `metro` entra al ruido de unidades | `a41b9e5` |
| `paquete de (1/8 cartulina)` | sin concepto | cabeza `1/8` | las fracciones se quitan de la cabeza; `1/8` se lee `tamano=octavo` | `a41b9e5` |
| `Lápiz 2H-6B` | abstención | se exigía `dureza=2h` | un rango de durezas es la serie: va a *Kit de lápices de dibujo*, y dos durezas no imponen ninguna | `07de3b7` |
| `Juego didáctico … Opciones: rompecabezas` asignado a `C054` | "No entendimos qué pide" en la previsualización | la previsualización volvía a adivinar por el texto | el concepto asignado en la revisión se respeta (`concepto_forzado`) | `677f749` |
| `acabado` en Cartulina, Papel | kits vacíos | discriminante que casi ningún producto declaraba | se volvió descriptivo; en Cartulina vuelve a filtrar `iris` / `cartulina` con productos que lo declaran | `44309fa`, `8c6e273` |

---

## 6. Cambios a la percepción (Gemini)

El prompt (`servicios/inteligencia/tukit_inteligencia/gemini.py`) creció lo mínimo, porque cada
línea se paga en cada página leída:

- **Separar lo que se compra por aparte.** `Cartuchera con: esferos, borrador` son tres renglones;
  `Pinturas acrílicas: cian, magenta, rojo` es uno por color, también cuando los colores vienen
  al final (`4 carpetas oficio con gancho. Colores: azul, rojo…`). La cantidad total se reparte,
  no se repite. No se parte un producto entero ni lo unido con "o" (`tajalápiz o portaminas`).
- **Uniformes por nombre.** Un renglón por uniforme, sin sus prendas: antes salía unas veces el
  uniforme entero prenda por prenda y otras solo el título.
- **Un texto que sigue en la página siguiente no es una página cortada** (`948f319`). Sexto y
  Décimo del CACS se rechazaban con "Una página no se leyó entera" porque la página 2 terminaba
  a mitad de la descripción del uniforme. La protección contra listas leídas a medias se mantiene
  para imágenes recortadas o borrosas.
- **Un reintento de transporte** ante timeout, 429 o 5xx (no ante 403 ni ante JSON mal formado),
  con tiempo de espera de 40 s.

Cuotas a vigilar: Gemini Flash Lite lee los PDF (≈ una petición por página); Gemini Embedding
calcula vectores (`bd-enriquecer`) y tiene el cupo diario más bajo. Curar y probar sinónimos no
gasta ninguno de los dos.

---

## 7. Cambios en los kits y en el back-office

**Kits** (`linea.ts`, `trabajos.py`, `parseo.py`):

- La ruta rápida solo pone producto a lo que se busca en el catálogo. Un `util` cuyo concepto aún
  no tiene productos queda `HUECO_CATALOGO` en vez de tumbar el trabajo con un 500.
- Nueva sección **"Lo consigues por tu cuenta"** para `otro` y para los textos sin producto. Antes
  un títere caía en "Lo gestiona el colegio", que era falso.
- Validar una línea ambigua sin SKU toma el candidato que eligieron los kits; sin ninguno,
  responde 409 con la causa.

**Back-office** (`apps/admin`):

- Eliminar una versión de lista sin revisar desde la cola, con confirmación en línea que avisa si
  un acudiente la espera; si era la vigente, la vigencia vuelve a la última revisada.
- La cola de trabajos muestra colegio y grado (venían en los hijos del trabajo y no se enviaban),
  separa las **previsualizaciones** del revisor de los trabajos de acudiente, y pone las acciones
  en una línea.
- Alta de útiles: el candidato elegido se busca por tienda y SKU sin el filtro de palabras, que
  rechazaba `Pilot Pluma Pen Caligrafía` para `Pluma para caligrafía`.

---

## 8. Registro de conceptos

### 8.1 Creados curando

`Prod.` es el número de productos al cerrar este registro; 0 en un `util` es un hueco por surtir.

| Código | Concepto | Tipo | Prod. | Por qué existe |
|---|---|---|---|---|
| C100 | Cepillo de dientes | util | 3 | aseo personal |
| C101 | Peine | util | 3 | aseo personal |
| C102 | Protoboard | util | 1 | robótica; estaba colgado de otro concepto del corpus |
| C103 | Batería 9V | util | 3 | robótica |
| C104 | Plumones | — | 0 | **desactivado**: fundido en C006 Marcador |
| C105 | Juego geométrico | — | 0 | **desactivado**: duplicaba C036 Juego de geometría |
| C106 | Sobre de acetato | util | 4 | sus frases estaban en Acetato |
| C107 | Xilófono | util | 3 | música |
| C108 | Cables caimanes | util | 0 | reactivado: una lista de robótica lo pide |
| C109 | Cable mini USB | util | 3 | robótica |
| C110 | Audífonos de diadema | otro | 0 | Tukit decidió no venderlos |
| C111 | Gorro de natación | util | 3 | clase de natación |
| C112 | Papel durex | util | 1 | sketchbook de papel durex |
| C113 | Papel iris | util | 11 | distinto de la cartulina iris (§2.1) |
| C114 | Kit de lápices de dibujo | util | 3 | series de durezas (2H-6B) |
| C115 | Limpiatipos | util | 2 | la goma limpiatipos caía en Borrador |
| C116 | Pluma | util | 3 | caligrafía |
| C117 | Paleta de pintura | util | 3 | caía en Palitos; recibe "paleta de acuarelas" |
| C118 | Frascos para almacenar pintura | util | 1 | reemplaza al C083 del corpus (desactivado) |
| C119 | Papel acuarela | util | 3 | artes |
| C120 | Papel pergamino | util | 2 | block de pergamino |
| C121–C125 | Cables jumper, LED, Arduino, Switch, Resistencia | util | 0 | robótica de bachillerato |
| C126 | Papel kraft | util | 1 | Papel (C014) era tan general que atraía renglones con concepto propio |
| C127 | Papel crepé | util | 13 | ídem |
| C128 | Papel seda | util | 14 | ídem |
| C129 | Papel bond | util | 0 | ídem |
| C130 | Papel silueta | util | 4 | ídem; estaba en otro concepto del corpus |
| C131 | Uniforme | uniforme | 0 | uniformes por nombre (§6) |
| C132 | Títere | otro | 0 | no se vende |
| C133 | Plan lector virtual | licencia_digital | 0 | RAZ-PLUS y similares: se paga en la plataforma |
| C134 | Libro o texto con título | texto | 0 | la edición exacta la vende una librería |
| C135 | Antifaz | util | 0 | útiles de la clase de natación |
| C136 | Gafas de natación | util | 3 | no son monogafas de laboratorio |
| C137 | Lo entrega el colegio | no_comprar | 0 | agenda y material que entrega el colegio |
| C138 | Cable eléctrico | util | 0 | "metro de cable estañado calibre 22" |
| C139 | Vestuario para presentaciones | otro | 0 | falda, sombrero, pañoleta para ensayos |
| C140 | Servomotor | util | 0 | aparece en varias listas de robótica |
| C141 | Motor DC | util | 0 | ídem |
| C142 | Componente electrónico especializado | otro | 0 | relay, puente H, joystick: no se venden |
| C143 | Ecoline (acuarela líquida) | util | 0 | no es la acuarela en pastilla; filtra por color |
| C144 | Piedras decorativas | util | 0 | bisutería y jardinería caían en Material Singapur |
| C145 | Cinta métrica | util | 0 | estaba como sinónimo de Cinta adhesiva |
| C146 | Tapabocas | util | 0 | aseo |
| C147 | Dispositivo electrónico (computador o tablet) | otro | 0 | lo consigue la familia |
| `dic-ingles` | Diccionario de inglés | libro_libre | 3 | se llevaba "diccionario ingles" el de español |

### 8.2 Correcciones a conceptos existentes

- **C006 Marcador** recibe `plumones`, `marcadores`, `rotuladores` y los productos de C104.
- **C014 Papel** pierde los sinónimos que pertenecen a kraft, crepé, seda, bond y silueta.
- **C015 Cinta adhesiva** pierde `cinta metrica` y `cinta metrica metro`.
- **Carpeta** pierde la frase de la maleta para carpeta oficio, que pasa a Maleta.
- **Cartulina** vuelve a filtrar por acabado (`iris` / `cartulina`) y sus productos declaran tamaño.
- **C092 Tablero de dibujo** recibe `tabla de diseño`, `tabla de dibujo` y variantes; tenía 3
  productos y un solo sinónimo.
- **C114 Kit de lápices de dibujo** recibe `lapiz serie durezas`, la forma a la que el
  emparejador reescribe un rango (§5).
- **Libro** pierde `plan lector`, que hacía buscar en el catálogo una licencia.
- Todos los nombres se normalizaron (§2.6).

### 8.3 Afinamiento con la auditoría del Agustiniano (2026-10-11)

Plan: [`2026-10-11-afinar-kits-agustiniano`](../diseno/planes/2026-10-11-afinar-kits-agustiniano.md).
Decisión de diseño: [ADR 0040](../arquitectura/adr/0040-como-se-compara-cada-atributo.md).

| Concepto | Cambio | Por qué |
|---|---|---|
| C071 Kit de tecnología | **desactivado**. Las protoboards pasan a C102; el kit protoboard + 40 jumpers, a C121; el L298N, el sensor MQ135, el kit de circuitos y el kit Arduino, a C142 (no se vende); las herramientas para celulares se desactivan | decisión del usuario: C142 no se vende y C071 mezclaba productos de naturaleza distinta |
| `dic-ingles` | **fundido en C034**, que filtra por `idioma` | partido, el mismo diccionario salía bien en un grado y como hueco en otro |
| C149 Portabasura | **creado**, `util`, sin productos | 1#64 estaba curado en Carpeta |
| C002, C004 | discriminante `grosor`; los productos que no dicen ser gruesos llevan `delgado` | lápices y colores gruesos (preescolar) |
| C006, C021 | discriminante `unidades` | una caja o un kit no se resuelve con una pieza suelta |
| C010, C029, C051 | `acabado` con tabla propia (fluorescente, escarchado, metalizado, iris, figuras) | cartulina y témpera fluorescentes, foamy escarchado |
| C013 | discriminante `longitud` | tijeras de 8,5 pulgadas |
| C014, C044, C097, C116 | discriminante `tipo` | celofán y lija; libro para colorear; esponja de loza; pluma de puntas intercambiables |
| C016 | discriminante `gramaje` | pegante en barra de 125 g |
| C020 | discriminante `color`; todos sus productos `presentacion=frasco` | pintura escolar por color; tarro y frasco son lo mismo |
| C022 | discriminante `tipo` (`gigante`) | plastilina gigante |
| C024 | discriminantes `material` y `manga`; `uno_por_estudiante` | bata antifluido; bata de artes con mangas; una bata sirve para todas las materias |
| C033 | discriminante `color` | palos de paleta de colores |
| C050 | discriminantes `tamano` y `tipo` | lienzo por medidas; lienzo de pintura por números |
| C086 | discriminante `longitud` | maleta que cabe una carpeta oficio |
| C102 | discriminante `puntos` | protoboard de 400 o de 830 puntos |
| C106 | discriminantes `tamano` y `grosor` | sobre de acetato grueso oficio |
| C107 | discriminante `notas` | xilófono de 8 placas |
| C113 | discriminante `tamano` | block de plegado 15 x 15 |
| C121 | discriminantes `tipo` y `longitud` | jumpers macho-macho, macho-hembra, hembra-hembra, de 10 o 20 cm |

Productos: el empaque pasa a `productos_canonicos.csv`; 8 productos de personaje sin marcar
(Moana, Princesas, Toy Story, Tigger, Mickey, Among Us, Marvel); 14 libros recuperan el título; se
desactivan el computador didáctico (C054), el set para hacer pompones (C089) y el galón de vinilo
(C020); los sets de herramientas de arte pasan a C148 Espátulas.

---

## 9. Entorno Windows

El proyecto se levantaba con `make`, que no corre en Windows. `tukit.ps1` (raíz) hace
`arriba`, `abajo`, `estado`, `embeddings`, `exportar` e `importar`, lee las llaves de `.env` y usa
Postgres en Docker por el puerto 5433. Problemas que aparecieron y su arreglo:

- Faltaban `pypdfium2` y `aiosqlite`: `uv sync --all-packages --all-extras`.
- `/v1/grados-canonicos` respondía 500: faltaba la migración de `kit_canonico` (escrita a mano,
  porque `alembic --autogenerate` falla por la zona horaria en Windows).
- Rutas `[item_id]` del admin en 404: caché de Next corrupta; se borra `apps/admin/.next`.
- `curl` desde Git Bash daña las tildes en los POST: usar Python (`urllib`) para crear conceptos
  por la API.
- El backend no recarga solo: después de cambiar código de un servicio,
  `.\tukit.ps1 abajo` y `.\tukit.ps1 arriba`.

---

## 10. Pendientes y límites conocidos

- **Huecos por surtir.** Varios `util` creados no tienen productos (§8.1, `Prod.` = 0): el
  acudiente ve "No lo tenemos". También falta un lápiz 2B, que piden varias listas.
- **Renglones ya asignados no se reasignan solos.** Crear un concepto o mover un sinónimo cambia
  las listas futuras, no las versiones que ya están en la cola: hay que reasignarlas a mano.
- **Códigos de concepto locales.** `C1NN` se numera en cada base: si dos personas crean conceptos
  a la vez, chocan. Mientras cure una sola persona no pasa (README).
- **No hay endpoint para editar sinónimos.** Hoy se agregan al crear el concepto o directamente en
  la base; un `PATCH /v1/admin/catalogo/conceptos/{codigo}` evitaría tocar SQL.
- **Pruebas que ya fallaban antes de la rama**, sin relación con este trabajo:
  `test_subir_listas::test_colegio_del_directorio_deriva_el_id_del_dane` y
  `arquitectura test_ningun_servicio_nombra_la_base_de_otro[inteligencia]`.
