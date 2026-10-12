# Qué buscar con el scraper: huecos reales del Colegio Agustiniano (2026)

- **Fuente:** los kits canónicos de las 13 listas del colegio, medidos con `ensayos/kits_offline.py` sobre `datos/` y comprobados contra la base: los dos dan **72 renglones en HUECO_CATALOGO** y los mismos totales ($9.723.617 el Ahorrador y $17.245.198 el Premium).
- **Fecha:** 2026-10-12. Reemplaza la versión del 2026-10-11, que salía de la [auditoría v2](auditoria-huecos-agustiniano/v2-d4ea7cb.md) y cubría 220 huecos. Entre las dos versiones se aprobó en la cola de revisión el surtido que trajo esa lista y se afinó la curaduría de los renglones; la sección 4 dice qué se resolvió.
- **Para qué:** la lista de búsqueda del scraper. Cada fila es un producto que el catálogo no tiene y que alguna lista del colegio pide. Las filas cubren los 72 renglones: 27 de papelería, arte y laboratorio, y 45 de electrónica.
- **Lo que esta lista no ve:** solo cuenta los renglones que el sistema declara hueco. Un renglón resuelto con un producto que no es lo pedido (A🔴 o C en las auditorías) no aparece aquí. Eso lo mide la siguiente auditoría.

## Cómo leer esta lista

- **Qué buscar:** la especificación mínima que tiene que cumplir el producto. Para el Premium conviene traer de cada cosa una opción económica y otra de buena marca.
- **Atributos al cargarlo:** los que el filtro por renglón le va a exigir (`_cumple` en `consulta.py`; cómo compara cada uno, en la §5.5 de la [guía de curaduría](../guias/GUIA_CONCEPTOS_Y_PRODUCTOS.md)). Un producto que no los declare, o que los declare con otro valor, queda fuera aunque sea el correcto.
- **⚠ sin discriminantes:** el concepto no tiene atributos discriminantes. Cargar el producto no basta: el Ahorrador toma el más barato del concepto. Primero hay que agregarle al concepto el discriminante que se indica.
- **Empaque:** el nombre tiene que decir el empaque ("x 10", "x 20 hojas"), porque de ahí lo saca `enriquecer`. Sin eso, el kit compra un paquete por cada unidad pedida.
- **Renglones:** `grado#orden` (J Jardín, T Transición, 1–11). Entre paréntesis, la cantidad cuando es mayor que 1.
- **Dónde:** tiendas ya registradas (`datos/catalogo/tiendas.csv`): Éxito (incluido su marketplace), Papelería Grancentral, Panamericana, Librería Nacional y Buscalibre. Lo que no tenga precio o esté agotado no se propone.

## 1. Papelería, arte y laboratorio (27 renglones)

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 1 | Cuaderno **3 materias** cuadriculado, grande | `materias=3`, `rayado=cuadriculado` | C001 | 10#17, 10#24, 10#27, 11#21, 11#24 | Éxito, Panamericana, Grancentral |
| 2 | **Papel iris en octavos** (paquete o block de papel, no cartulina). La cartulina iris en octavos ya está en C010, pero el renglón pide papel | `tamano=octavo`, `tipo=iris` | C113 | 10#61, 11#58 | Panamericana, Grancentral |
| 3 | **Libro para colorear** infantil, de dibujos pequeños | `tipo=colorear` | C044 | T#55 | Panamericana, Éxito |
| 4 | **Pintura acrílica cian** (tarro o tubo de unos 45–60 ml). Los demás colores de la serie ya los cubre el tarro Destellos de 60 cc; sirve el cian de esa línea u otro equivalente | `tipo=acrilico`, `color=cian` | C027 | 7#43, 8#42, 9#39, 10#45, 11#41 | Panamericana, Éxito |
| 5 | **Ecoline** (acuarela líquida) blanco y negro | `color=blanco` / `color=negro` | C143 | 9#46 (blanco), 9#47 (negro) | Panamericana |
| 6 | **Piedras decorativas**: de bisutería pequeñas y de colores para jardinería | Ninguno; con un producto de cada uno basta para empezar | C144 | 2#71 (bisutería), 2#91 (jardinería) | Éxito |
| 7 | **Bata de laboratorio antifluido**, manga larga, tallas infantiles y juveniles | `material=antifluido`; si la ficha lo dice, `manga=larga` y `color=blanco` | C024 | 3#41, 4#38, 5#47, 6#25, 7#24, 8#22, 8#26, 9#22, 10#29, 11#26 | Éxito |

## 2. Electrónica (45 renglones)

La única tienda registrada que trae algo de esto es el marketplace de Éxito. Conviene registrar una tienda de electrónica. C121 ya filtra por `tipo` y `longitud`; los demás conceptos marcados ⚠ todavía no tienen discriminantes: sin ellos, el kit no distingue una resistencia de 330 Ω de una de 1 kΩ.

| # | Qué buscar | Atributos al cargarlo | Concepto | Renglones | Dónde |
| --- | --- | --- | --- | --- | --- |
| 8 | **Cables caimanes** (paquete de 10, de unos 15–30 cm) | ⚠ agregar `longitud` | C108 | 1#44 (4), 2#82 (4), 3#77 (2), 4#71 (4), 5#73 (4) | Éxito marketplace, tienda de electrónica |
| 9 | **Jumpers de 10 cm, x10**: macho-macho y hembra-macho | `tipo=macho-macho` o `macho-hembra`, `longitud=10 cm`; "x10" en el nombre | C121 | M-M: 6#48, 7#74 · H-M: 6#49, 7#75 | Éxito marketplace, tienda de electrónica |
| 10 | **Jumpers de 20 cm, x10**: macho-hembra y hembra-hembra | `tipo=macho-hembra` o `hembra-hembra`, `longitud=20 cm` | C121 | M-H: 8#63 (10), 9#66 (10) · H-H: 8#64 (10) | Éxito marketplace, tienda de electrónica |
| 11 | **LEDs de 5 mm surtidos**, paquete x10 | ⚠ agregar `color`; "x10" en el nombre | C122 | 1#45 (4), 2#83 (3), 3#74 (2), 4#72 (3), 5#74 (6), 6#50, 7#76, 8#65 (10), 9#67 (10) | Éxito marketplace, tienda de electrónica |
| 12 | **Arduino Uno R3** (la placa sola, con cable USB) | Ninguno | C123 | 8#61, 9#64 | Éxito marketplace, tienda de electrónica |
| 13 | **Interruptor de balancín** (rocker) | ⚠ agregar `tipo` | C124 | 1#41, 5#70 | Éxito marketplace, tienda de electrónica |
| 14 | **Interruptor** sencillo y **switch de dos posiciones (2 pines)** | `tipo=sencillo` / `tipo=2 posiciones` | C124 | 2#78, 3#71, 4#67 · 2 posiciones: 6#52 (2) | Éxito marketplace, tienda de electrónica |
| 15 | **Resistencias de 330 Ω y de 1 kΩ, 1/4 W** (sueltas o en bolsa pequeña) | ⚠ agregar `valor` | C125 | 1#46 (2), 2#84 (3), 3#75 (2), 4#73 (3), 5#75 (3) | Tienda de electrónica |
| 16 | **Kit de 20 resistencias surtidas de 1/4 W** | `valor=surtido`; "x20" en el nombre | C125 | 6#51, 7#77, 8#66, 9#68 (20) | Tienda de electrónica |
| 17 | **Cable estañado calibre 22**, por metro | ⚠ agregar `calibre` | C138 | 5#76 | Tienda de electrónica |
| 18 | **Servomotor** (tipo SG90) | Ninguno | C140 | 9#69 (2) | Éxito marketplace, tienda de electrónica |
| 19 | **Motor DC pequeño** (motor generador escolar de 3–6 V, rectangular) | ⚠ agregar `tipo` (`motor`, `motorreductor`) | C141 | 2#79, 4#68, 9#70 | Éxito marketplace, tienda de electrónica |
| 20 | **Motorreductor** (amarillo tipo TT, con rueda) | `tipo=motorreductor` | C141 | 6#53, 7#79 | Éxito marketplace, tienda de electrónica |

## 3. No se venden (decisión del 2026-10-11)

Son tipo `otro` o `texto` (ADR 0027) y llegan como "Lo consigues por tu cuenta". El usuario confirmó que **no se venden**: componentes electrónicos especializados (C142), audífonos (C110) y textos con título (C134). Quedan aquí como referencia por si la decisión cambia.

### 3.1 Componentes electrónicos (C142)

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

### 3.2 Audífonos de diadema (C110)

Diadema con cable, conector de 3,5 mm o USB, no de celular: 1#7, 2#14, 3#13, 4#13, 5#14, 6#16, 7#15, 8#14, 8#59, 9#15, 9#62, 10#15, 11#16.

### 3.3 Textos con título (C134)

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

## 4. Resuelto desde la versión anterior

De 220 renglones en hueco se pasó a 72. Las filas de la versión del 2026-10-11 que ya no tienen ningún renglón en hueco son estas (el número es el de esa versión):

- **Con productos aprobados en la cola** (surtido del 2026-10-12, cada oferta verificada contra la API de la tienda): cuaderno de cuadros de 1 cm (1), 5 materias (3), blocks rayados, blancos y milimetrado (6–10), sketchbook durex (11), carpetas legajadoras por color y de gancho (13, 14), sobre de acetato grueso (15), cartulinas en pliego, cuartos y fluorescente (17–19), cartón paja (20), celofán y lija (21, 22), papel bond en octavos (23), lápiz rojo delgado y grueso (24, 25), marcadores acrílicos (26), micropunta (27), regla de acero (28), tijeras de 8,5 in (29), metro de costura (30), pinceles (32, 33), lienzos (34–36), acrílicos por color salvo el cian y su estuche (37, 38), acuarelas en tubo (39), figuras de foami (41), palos de pincho y de paleta (42, 43), pañuelos, toalla, plato y vaso (45–48), antifaz (50), juego de mesa (51) y diccionario inglés-inglés (65).
- **Con curaduría, sin producto nuevo:** el block de cartulina iris carta (12) se cobra con el block de cartulina multicolor A4 de $3.900 en vez del paquete iris x100 de $63.800; los marcadores acrílicos «de 12 o 18 unidades» aceptan el estuche de 12; la barra de 125 g (31) se tomó como mal pedida por el colegio y se cura a la más grande que existe, de 40 g.
- **Ya no se compran:** el portabasura (16) pasó a «no comprar», y `1#57` (acetato) y `1#53` (papel crepe) repiten otro renglón de la misma lista.
- **Acetato en hojas de oficio** (16b): `4#55` se cobra con un acetato de laminación de oficio x10 aprobado en la cola; ya no depende del acetato calibre 10, cuyo tamaño sigue sin confirmar.
