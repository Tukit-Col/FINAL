# Qué buscar con el scraper: huecos reales del Colegio Agustiniano (2026)

- **Fuente:** [auditoría de huecos del Agustiniano](nuevo-reporte-huecos-agustiniano.md) (commit `d4ea7cb`), secciones 4.1 (A🔴) y 4.2 (A).
- **Fecha:** 2026-10-11. Actualizada el mismo día después del afinamiento ([plan](../diseno/planes/2026-10-11-afinar-kits-agustiniano.md), [ADR 0040](../arquitectura/adr/0040-como-se-compara-cada-atributo.md)): los atributos que ya se agregaron a cada concepto están puestos y lo ya resuelto salió de la lista.
- **Para qué:** la lista de búsqueda del scraper. Cada fila es un producto que el catálogo no tiene y que alguna lista del colegio pide. Hoy son **220 renglones** del colegio que salen como hueco; esta lista los cubre todos.

## Cómo leer esta lista

- **Qué buscar:** la especificación mínima que tiene que cumplir el producto. Para el Premium conviene traer de cada cosa una opción económica y otra de buena marca.
- **Atributos al cargarlo:** los que el filtro por renglón le va a exigir (`_cumple` en `consulta.py`; cómo compara cada uno, en la §5.5 de la [guía de curaduría](../guias/GUIA_CONCEPTOS_Y_PRODUCTOS.md)). Un producto que no los declare, o que los declare con otro valor, queda fuera aunque sea el correcto, y el renglón vuelve a salir como falso hueco (sección 3.2 a de la auditoría).
- **⚠ sin discriminantes:** el concepto no tiene atributos discriminantes. Cargar el producto no basta: el Ahorrador toma el más barato del concepto. Primero hay que agregarle al concepto el discriminante que se indica.
- **Empaque:** el nombre tiene que decir el empaque ("x 10", "x 20 hojas"), porque de ahí lo saca `enriquecer`. Sin eso, el kit compra un paquete por cada unidad pedida (3.4).
- **Renglones:** `grado#orden` (J Jardín, T Transición, 1–11). Entre paréntesis, la cantidad cuando es mayor que 1.
- **Dónde:** tiendas ya registradas (`datos/catalogo/tiendas.csv`): Éxito (incluido su marketplace), Papelería Grancentral, Panamericana, Librería Nacional y Buscalibre. La electrónica casi no está en esas tiendas: hace falta registrar una tienda de electrónica o buscar en el marketplace de Éxito.

## 1. Cuadernos, blocks y papelería

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 1 | Cuaderno cuadriculado de **cuadros de 1×1 cm**, 100 hojas, cosido (preescolar) | `rayado=cuadriculado`, `hojas=100`, `encuadernacion=cosido`. La cuadrícula grande no tiene atributo: hay que agregar uno (`cuadricula=1 cm`) o curarlo en el renglón | C001 | J#3 | Éxito, Grancentral, Panamericana |
| 2 | Cuaderno **3 materias** cuadriculado, grande | `materias=3`, `rayado=cuadriculado` | C001 | 10#17, 10#24, 10#27, 11#21, 11#24 | Éxito, Panamericana, Grancentral |
| 3 | Cuaderno **5 materias** cuadriculado, grande (argollado o empastado) | `materias=5`, `rayado=cuadriculado` | C001 | 8#17, 9#16, 10#10, 11#10, 11#17 | Éxito, Panamericana, Grancentral |
| 4 | Cuaderno **argollado cuadriculado de 100 hojas, sin personaje** (opcional: quita 21 cobros de Stitch) | `rayado=cuadriculado`, `hojas=100`, `encuadernacion=argollado`, `materias=1`, sin `personaje` | C001 | 5#46, 6#24, 6#26, 7#14, 7#23, 7#25, 7#28, 8#21, 8#24, 8#29, 9#21, 9#25, 9#28, 10#31, 10#33, 10#34, 10#35, 11#28, 11#29, 11#30, 11#31 | Éxito, Grancentral |
| 5 | Cuaderno **cosido cuadriculado de 50 hojas, sin personaje** (opcional: quita 11 cobros de Disney) | `rayado=cuadriculado`, `hojas=50`, `encuadernacion=cosido`, `materias=1`, sin `personaje` | C001 | 1#19, 2#45, 3#43, 4#41, 5#49, 6#29, 7#29, 8#30, 9#29, 10#36, 11#32 | Éxito, Grancentral |
| 6 | Block **rayado** tamaño carta | `tipo=rayado`, `tamano=carta` | C003 | 2#10 | Éxito, Panamericana, Grancentral |
| 7 | Block **rayado** tamaño oficio | `tipo=rayado`, `tamano=oficio` | C003 | 1#48, 4#15, 5#16 | Éxito, Panamericana, Grancentral |
| 8 | Block de **hojas blancas** tamaño carta | `tipo=blanco`, `tamano=carta` | C003 | 3#16 (2) | Éxito, Panamericana, Grancentral |
| 9 | Block de **hojas blancas** tamaño oficio | `tipo=blanco`, `tamano=oficio` | C003 | 2#26, 4#17, 5#18 | Éxito, Panamericana, Grancentral |
| 10 | Block de papel **milimetrado** tamaño carta | `tipo=milimetrado`, `tamano=carta` | C003 | 10#21 | Panamericana, Grancentral |
| 11 | **Sketchbook de papel durex**, 50 hojas, tamaño carta | `tamano=carta`; el nombre debe decir "50 hojas" | C112 | 7#33, 8#31, 9#30, 10#37, 11#33 | Panamericana, Grancentral |
| 12 | **Block de cartulina iris** tamaño carta | `tamano=carta`, `color=surtido` | C010 | 5#66 | Panamericana, Grancentral |
| 13 | **Carpeta legajadora plástica translúcida**, oficio, con gancho, en **amarillo, azul, rojo y verde** (una por color) | `tipo=legajador`, `tamano=oficio`, `color=<el color>`. El concepto filtra `tamano` y `tipo`, pero no `color`: al cargarlas, agregar `color` a C011 | C011 | Amarillo: J#7, T#8 · Azul: J#8, T#9 · Rojo: J#9, T#10 · Verde: J#10, T#11 | Éxito, Grancentral, Panamericana |
| 14 | **Carpeta tipo legajador** (gancho legajador), oficio, cualquier color | `tipo=legajador`, `tamano=oficio` | C011 | 1#17, 2#47, 3#67, 6#15, 11#14 | Éxito, Grancentral |
| 15 | **Sobre de acetato grueso**, tamaño oficio (suelto o en paquete pequeño) | `tamano=oficio`, `grosor=grueso` | C106 | 1#11, 1#57, 2#36, 3#20, 4#19, 5#27 | Grancentral, Panamericana |
| 16 | **Portabasura** (bolsa o caneca pequeña de pupitre). Antes, confirmar con el colegio qué es | Ninguno (concepto nuevo, sin discriminantes) | C149 | 1#64 | Éxito |
| 16b | **Acetato en hojas, tamaño oficio**, o confirmar el tamaño del acetato calibre 10 x5 hojas (`TK-C030-CON`), que no lo dice | `tamano=oficio` | C030 | 4#55 (2 hojas) | Grancentral, Panamericana |

## 2. Cartulinas, cartones y papeles

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 17 | Cartulina blanca en **pliego** (paquete pequeño o por unidad) | `color=blanco`, `tamano=pliego`, `acabado` vacío | C010 | J#40 (2) | Panamericana, Grancentral |
| 18 | Cartulina blanca en **cuartos** (1/4) | `color=blanco`, `tamano=cuarto` | C010 | 1#39 (2), 2#67 (2) | Panamericana, Grancentral |
| 19 | Cartulina **fluorescente** en octavos, colores surtidos, paquete | `acabado=fluorescente`, `tamano=octavo`, `color=surtido` | C010 | J#38 (3), T#34 (2) | Panamericana, Grancentral |
| 20 | **Cartón paja blanco** en octavos, paquete x10 | `color=blanco`, `tamano=octavo`; "x10" en el nombre | C041 | J#41 (10 octavos), T#39 (3 octavos) | Grancentral, Panamericana |
| 21 | **Papel celofán** en pliegos, cualquier color | `tipo=celofan`, `tamano=pliego` | C014 | T#77 (2) | Panamericana, Grancentral |
| 22 | **Papel de lija** (hoja) | `tipo=lija` | C014 | 2#90 | Éxito |
| 23 | **Papel bond en octavos**, paquete pequeño (10–50 hojas) | Ninguno; el nombre debe decir el empaque. Hoy solo hay resma de 500 carta en C031 | C129 | J#71 (10 hojas) | Grancentral, Panamericana |

## 3. Escritura y geometría

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 24 | **Lápiz rojo** delgado (unidad o caja) | `color=rojo`, `grosor=delgado` | C002 | T#62, 1#61, 2#39, 3#24, 4#22, 5#31 | Éxito, Panamericana, Grancentral |
| 25 | **Lápiz rojo grueso** (triangular jumbo) | `color=rojo`, `grosor=grueso` | C002 | J#60 (2) | Éxito, Panamericana |
| 26 | **Marcadores acrílicos** (paint markers) doble punta, estuche de 12 o 18 | `tipo=acrilico`; "x12" o "x18" en el nombre | C006 | 4#54, 6#34, 7#41, 9#54, 10#56, 11#54 | Panamericana, Éxito |
| 27 | **Micropunta negro** (estilógrafo o fineliner 0,1–0,5) | `punta=micropunta`, `color=negro` | C006 | 7#55, 8#54, 9#50, 10#57 | Panamericana, Éxito, Grancentral |
| 28 | **Regla de acero inoxidable** de 30 cm | `material=acero`, `longitud=30 cm` | C008 | 7#31, 8#37, 9#33, 10#40, 11#36 | Panamericana, Éxito |
| 29 | **Tijeras de 8,5 pulgadas** | `longitud=8.5 in` | C013 | 10#59, 11#56 | Éxito, Panamericana |
| 30 | **Cinta métrica de 1 m** (de costura) | Ninguno | C145 | 2#19, 3#38 | Éxito |

## 4. Pegantes

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 31 | **Pegante en barra de 125 g** (o la barra más grande que exista). Antes, verificar que exista: la mayor del catálogo es de 40 g | `gramaje=125 g` (vale uno mayor) | C016 | T#67, 1#67, 2#44, 3#31, 4#29, 5#38 | Éxito, Panamericana, Grancentral |

## 5. Arte

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 32 | **Pincel plano #10** | `forma=plano`, `grosor=n10` | C021 | T#40 | Panamericana, Grancentral |
| 33 | **Pincel plano de pelo de camello** (opcional: hoy se cobra un plano de nylon, que sirve como sustituto) | `forma=plano`. El pelo no es atributo: si se quiere exigir, agregar `pelo` a C021 | C021 | J#42 (2), J#43 | Panamericana |
| 34 | **Lienzo con bastidor de 25×25 cm** (opcional: hoy lo cubre el de 20 x 30, dentro de la tolerancia por lado) | `tamano=25 x 25 cm` | C050 | 1#25, 2#73, 3#60 (2), 4#45 (2), 5#53 (2), 6#33 (2) | Panamericana, Éxito |
| 35 | **Lienzo con bastidor de 30×40 cm** | `tamano=30 x 40 cm` | C050 | 7#36, 8#34, 9#36, 10#43, 11#39 | Panamericana, Éxito |
| 36 | **Lienzo para pintar por números** (libre elección) | `tipo=por numeros` | C050 | 7#37, 8#35, 9#37, 10#44, 11#40 | Panamericana, Éxito |
| 37 | **Pintura acrílica en tubo de 45 ml (≈45 cc)**: cian, magenta, amarillo, blanco, negro, azul primario y rojo primario (un producto por color) | `tipo=acrilico`, `color=<el color>` | C027 | Cian: 7#43, 8#42, 9#39, 10#45, 11#41 · Magenta: 7#44, 8#43, 9#40, 10#46, 11#42 · Amarillo: 7#45, 8#44, 9#41, 10#47, 11#43 · Blanco: 7#46 · Negro: 7#47 · Azul primario: 7#48, 8#46, 9#43, 10#49, 11#45 · Rojo primario: 7#49, 8#47, 9#44, 10#50, 11#46 · "Blanco negro" (los dos en el mismo renglón): 8#45, 9#42, 10#48, 11#44 | Panamericana |
| 38 | **Estuche de pinturas acrílicas** (set de tubos) | `tipo=acrilico`, `color=surtido` | C027 | 5#61 | Panamericana, Éxito |
| 39 | **Acuarelas en tubo** (set) | `presentacion=tubo` | C065 | 8#39 | Panamericana |
| 40 | **Ecoline** (acuarela líquida) blanco y negro | `color=blanco` / `color=negro` | C143 | 9#46 (blanco), 9#47 (negro) | Panamericana |
| 41 | **Figuras de foami** (paquete de figuras troqueladas) | `acabado=figuras` | C029 | J#49 | Grancentral, Panamericana |
| 42 | **Palos de pincho largos** (de madera, paquete) | `tipo=pincho` | C033 | J#45 (5), T#43 (2) | Éxito, Grancentral |
| 43 | **Palos de paleta de colores** (paquete) | `tipo=paleta`, `color=surtido` | C033 | J#47, T#45 | Grancentral, Éxito |
| 44 | **Piedras decorativas**: de bisutería pequeñas y de colores para jardinería | Ninguno; con un producto de cada uno basta para empezar | C144 | 2#71 (bisutería), 2#91 (jardinería) | Éxito |

## 6. Aseo, cocina y laboratorio

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 45 | **Pañuelos faciales**, caja | `tipo=panuelo` (hoy cobra pañitos húmedos) | C040 | J#67, T#57 | Éxito |
| 46 | **Toalla pequeña** de tela (de manos) | `tipo=tela` | C040 | 3#57, 4#51, 5#56, 7#52, 8#49, 9#53, 10#53, 11#51 | Éxito |
| 47 | **Plato plástico** reutilizable | `tipo=plato`, `material=plastico` | C057 | 3#90, 4#82, 5#85 (renglones partidos de 3#56, 4#50 y 5#55) | Éxito |
| 48 | **Vaso plástico pequeño** reutilizable, sin personaje (opcional) | `tipo=vaso`, `material=plastico` | C057 | 7#53, 9#51 | Éxito |
| 49 | **Bata de laboratorio antifluido**, manga larga, tallas infantiles y juveniles | `material=antifluido`, `manga=larga`, `color=blanco` | C024 | 3#41, 4#38, 5#47, 6#25, 7#24, 8#22, 9#22, 10#29, 11#26 | Éxito |
| 50 | **Antifaz de dormir** | Ninguno | C135 | J#56, T#54 | Éxito |
| 51 | **Juego de mesa didáctico para 9–11 años** (Quinto) | ⚠ sin discriminantes: agregar `edad` a C054 | C054 | 5#10 | Éxito, Panamericana |

## 7. Electrónica

La única tienda registrada que trae algo de esto es el marketplace de Éxito (de ahí venían los productos de C071, hoy desactivado). Conviene registrar una tienda de electrónica. C121 ya filtra por `tipo` y `longitud`; los demás conceptos (marcados ⚠) todavía no tienen discriminantes: sin ellos, el kit no distingue una resistencia de 330 Ω de una de 1 kΩ.

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 52 | **Cables caimanes** (paquete de 10, de unos 15–30 cm) | ⚠ agregar `longitud` | C108 | 1#44 (4), 2#82 (4), 3#77 (2), 4#71 (4), 5#73 (4) | Éxito marketplace, tienda de electrónica |
| 53 | **Jumpers de 10 cm, x10**: macho-macho y hembra-macho | `tipo=macho-macho` o `macho-hembra`, `longitud=10 cm`; "x10" en el nombre | C121 | M-M: 6#48, 7#74 · H-M: 6#49, 7#75 | Éxito marketplace, tienda de electrónica |
| 54 | **Jumpers de 20 cm, x10**: macho-hembra y hembra-hembra | `tipo=macho-hembra` o `hembra-hembra`, `longitud=20 cm` | C121 | M-H: 8#63 (10), 9#66 (10) · H-H: 8#64 (10) | Éxito marketplace, tienda de electrónica |
| 55 | **LEDs de 5 mm surtidos**, paquete x10 | ⚠ agregar `color`; "x10" en el nombre | C122 | 1#45 (4), 2#83 (3), 3#74 (2), 4#72 (3), 5#74 (6), 6#50, 7#76, 8#65 (10), 9#67 (10) | Éxito marketplace, tienda de electrónica |
| 56 | **Arduino Uno R3** (la placa sola, con cable USB) | Ninguno. Hoy solo existe un kit de 220 piezas a $386.980 en C071 | C123 | 8#61, 9#64 | Éxito marketplace, tienda de electrónica |
| 57 | **Interruptor de balancín** (rocker) | ⚠ agregar `tipo` | C124 | 1#41, 5#70 | Éxito marketplace, tienda de electrónica |
| 58 | **Interruptor** sencillo y **switch de dos posiciones (2 pines)** | `tipo=sencillo` / `tipo=2 posiciones` | C124 | 2#78, 3#71, 4#67 · 2 posiciones: 6#52 (2) | Éxito marketplace, tienda de electrónica |
| 59 | **Resistencias de 330 Ω y de 1 kΩ, 1/4 W** (sueltas o en bolsa pequeña) | ⚠ agregar `valor` | C125 | 1#46 (2), 2#84 (3), 3#75 (2), 4#73 (3), 5#75 (3) | Tienda de electrónica |
| 60 | **Kit de 20 resistencias surtidas de 1/4 W** | `valor=surtido`; "x20" en el nombre | C125 | 6#51, 7#77, 8#66, 9#68 (20) | Tienda de electrónica |
| 61 | **Cable estañado calibre 22**, por metro | ⚠ agregar `calibre` | C138 | 5#76 | Tienda de electrónica |
| 62 | **Servomotor** (tipo SG90) | Ninguno | C140 | 9#69 (2) | Éxito marketplace, tienda de electrónica |
| 63 | **Motor DC pequeño** (motor generador escolar de 3–6 V, rectangular) | ⚠ agregar `tipo` (`motor`, `motorreductor`) | C141 | 2#79, 4#68, 9#70 | Éxito marketplace, tienda de electrónica |
| 64 | **Motorreductor** (amarillo tipo TT, con rueda) | `tipo=motorreductor` | C141 | 6#53, 7#79 | Éxito marketplace, tienda de electrónica |

## 8. Libros

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 65 | **Diccionario inglés-inglés (monolingüe)** escolar: Oxford, Longman o Cambridge learner's | `idioma=ingles-ingles` | C034 | 7#12, 8#13, 9#12, 10#12, 11#11 | Panamericana, Librería Nacional, Buscalibre |

## 9. No se venden (decisión del 2026-10-11)

Son tipo `otro` o `texto` (ADR 0027) y llegan como "Lo consigues por tu cuenta". El usuario confirmó que **no se venden**: componentes electrónicos especializados (C142), audífonos (C110) y textos con título (C134). Quedan aquí como referencia por si la decisión cambia.

### 9.1 Componentes electrónicos (C142)

El módulo L298N, el sensor MQ135, el kit de circuitos y el kit Arduino se movieron de C071 (desactivado) a C142, y no se ofrecen.

| Qué buscar | Renglones |
| --- | --- |
| Buzzer | 3#72 |
| Broche para batería de 9 V | 6#45, 7#71 |
| Pulsadores de 4 pines | 7#78 (4) |
| Sensor de movimiento PIR HC-SR501 | 8#67 |
| Sensor de proximidad ultrasónico HC-SR04 | 8#68 |
| Sensor de proximidad IR | 8#69 |
| Módulo relé de 1 canal, 5 V | 9#71 |
| Joystick analógico KY-023 | 9#73 (2) |
| Módulo puente H L298N (está en C142, no se ofrece) | 9#72 |

### 9.2 Audífonos de diadema (C110)

Diadema con cable, conector de 3,5 mm o USB, no de celular: 1#7, 2#14, 3#13, 4#13, 5#14, 6#16, 7#15, 8#14, 8#59, 9#15, 9#62, 10#15, 11#16.

### 9.3 Textos con título (C134)

Por diseño son "Lo consigues por tu cuenta". Cuatro de los títulos que piden las listas ya están en el catálogo, en C044 (`8#7` *Puñales en la niebla*, `8#8` *El mensajero de Agartha 6*, `11#6` *Orgullo y prejuicio*, `11#7` *Aquiles en TikTok*); con la decisión de no vender textos, esos renglones siguen como "por su cuenta". Si Tukit decide surtirlos, se buscan en Panamericana, Librería Nacional y Buscalibre por título y editorial, y se cargan con su ISBN.

| Título · autor · editorial | Renglones |
| --- | --- |
| Entre amigos C Lenguaje (cuaderno letra script) · Norma | T#1 |
| Yo soy yo (con cuaderno de actividades) · Gabriela Peyron · Norma | 2#5 |
| Bobot (con cartilla) · Cecilia Eudave · Castillo | 2#6 |
| Antología de cuentos para leer · Jorge A. Jiménez R. · Palbooks | 2#7 |
| La familia más rica del mundo · Enlace | 3#5 |
| El país más hermoso del mundo · Norma | 3#6 |
| Detective Equis · Antonia Sanín · Castillo | 3#7 |
| Alpha Mathematics On-Level Practice Book 3 | 3#32 |
| Un regalo inesperado · María García Esperón · Enlace | 4#5 |
| ¿De dónde vienen los perros? · Francisco Leal Quevedo · Panamericana | 4#6 |
| De taquito, antología de cuentos futboleros · Diego F. Barros · Planeta | 4#7 |
| Competencias y habilidades del siglo XXI, grados 4, 5, 6 y 7 · Libros y Libros | 4#30, 5#39, 6#17, 7#16 |
| La llave de las estrellas · Malena Salazar Murcia · Enlace | 5#5 |
| La teoría de los colibríes · Michelle Kadarusman · Norma | 5#6 |
| La palabra más hermosa · Jordi Sierra i Fabra · Algar | 5#7 |
| Lectura Multidimensional Método 84H (Octavo aparte) | 6#4, 7#4, 8#5, 9#3, 10#4, 11#4 |
| Danny, el campeón del mundo · Roald Dahl · Loqueleo | 6#6 |
| El pan de la guerra · Deborah Ellis · Castillo | 6#7 |
| Mi hermano el genio · Rodrigo Muñoz Avia · Edebé | 6#8 |
| Gateway to the World A2 Student's Book · Macmillan | 6#11, 6#72 |
| Gateway to the World B1 Student's Book · Macmillan | 7#11, 7#96, 8#11 |
| Gateway to the World B2 Student's Book · Macmillan | 9#11, 9#91 |
| Gateway to the World B2+ Workbook · Macmillan | 10#11, 10#81 |
| Biology, 14.ª ed. · Mader y Windelspecht · McGraw Hill | 6#23, 7#22 |
| Biology, 13.ª ed. · Mader y Windelspecht · McGraw Hill | 6#71, 8#20, 9#20, 9#90 |
| Los secretos de Hafiz Mustafá · Francisco Leal Quevedo · Norma | 7#6 |
| Sherlock, Lupin y yo: Último acto en el teatro de la Ópera · Irene Adler · Planeta | 7#7 |
| Valeria en el reino de Malagana · Albeiro Echeverría · Panamericana | 7#8 |
| Te amo, peladita · Albeiro Echavarría · Norma | 8#9 |
| Matemáticas Jenga 8 · Ediciones Milenio | 8#16 |
| Química general, orgánica y biológica, 4.ª ed. · Karen C. Timberlake · Pearson | 8#23, 9#23, 10#26, 11#23 |
| Física, 6.ª ed. · Wilson, Buffa y Lou · Pearson | 8#27, 9#24, 10#23, 11#20 |
| Las claves de la argumentación · Anthony Weston · Planeta Lector | 9#5 |
| La noche en que Frankenstein leyó el Quijote · Santiago Posteguillo · Planeta | 9#6 |
| Montes de María · Daniel Ángel · Algar | 9#7 |
| Cien años de soledad · Gabriel García Márquez · cualquier edición | 9#8 |
| Meditaciones del gato Aurelio · Planeta | 10#6 |
| Humanos púrpura · Fredy Pedraza Cuevas · autopublicada | 10#7 |
| En los pliegues del aire · Daniel Hernández Chambers · Algar | 10#8 |
| Fundamentos de Física, 2.ª ed. · Ruelas y Velásquez · McGraw Hill | 10#79, 11#81 |
| Fundamentos de Química, 15.ª ed. · Hein, Arena y Willard · Cengage | 10#80, 11#82 |
| Gabriel García Márquez, un genio de muchos rostros · Orlando Oliveros · Algar | 11#8 |

## 10. Ya resuelto con curaduría, sin el scraper

En la versión anterior de esta lista estaban como "ya en el catálogo"; el afinamiento del 2026-10-11 los resolvió:

- **Productos en el concepto equivocado:** la protoboard de 400 puntos (`TK-REV-101119299`) pasó a C102 y el kit de 40 jumpers macho-macho (`TK-REV-102561087`), a C121. Hoy se cobran en `6#47`, `7#73`, `8#60`, `8#62` y `9#65`.
- **Productos a los que les faltaba un atributo:** las Biblias (`edicion`, leída del título), la carpeta de fuelle (`tamano=oficio`, **por confirmar con la ficha**), los vinilos (`presentacion=frasco`), los marcadores (`punta`) y los diccionarios bilingües (`idioma`).

Quedan dos por confirmar, sin tener que buscar nada:

- **Acetato calibre 10 x5 hojas** (`TK-C030-CON`): si es oficio, basta con declararlo y `4#55` deja de ser hueco (fila 16b).
- **Cuaderno argollado multimaterias de Spiderman** (`TK-C001-CON-SPIDERMAN`): declara `materias=multiple`, que no cumple ni 3 ni 5. Con el número real de materias, cubre las filas 2 o 3 como último recurso (es de personaje).
