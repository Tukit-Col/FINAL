# Propuesta de atributos obligatorios — conceptos de la lista de Séptimo (Agustiniano Salitre)

Complementa [auditoria-kits-agustiniano-septimo.md](auditoria-kits-agustiniano-septimo.md). Para confirmar antes de implementar.

## Cómo funciona hoy (verificado en código)

- Cada concepto ya parte sus atributos en dos listas:
  - **Discriminantes** (= *obligatorios*): filtran. Un producto que no declara el valor pedido se descarta. Si ninguno cumple, la línea queda como hueco, **sin sustituto**.
  - **Descriptivos**: se muestran al acudiente y no descartan nada.
- **Obligatorio no significa "siempre se exige".** Solo se exige **cuando el renglón lo dice**. "Cuaderno" a secas no filtra por rayado; "cuaderno cuadriculado" sí.
- La extracción ya existe (`extraer_atributos`, [enriquecer.py:609](../servicios/catalogo/tukit_catalogo/enriquecer.py#L609)) y el filtro también (`emparejar`, [consulta.py:120](../servicios/catalogo/tukit_catalogo/consulta.py#L120)).
- **El bug:** la ruta rápida que arma los kits canónicos de listas revisadas no usa nada de eso. Toma los candidatos **por concepto** y marca todos como `cumple: True` ([routers/admin.py:276](../servicios/catalogo/tukit_catalogo/routers/admin.py#L276)). Por eso los 7 acrílicos reciben el mismo tubo.

Con tu definición, **Ahorrador = el más barato que cumple** y **Premium = el más caro que cumple**.

## Requisito aparte: cobertura del catálogo

Un atributo obligatorio solo funciona si los **productos** lo declaran. Si se exige y ningún producto lo declara, la línea queda como hueco aunque el producto correcto exista. La columna "Cobertura" muestra cuántos productos activos del concepto lo declaran hoy. Las coberturas bajas hay que enriquecerlas (lo puedo hacer desde los nombres con el mismo extractor) antes de activar el filtro.

## Leyenda de la propuesta

- **OBL**: obligatorio (discriminante).
- **DESC**: descriptivo.
- **NUEVO**: el atributo no existe hoy y hay que crearlo.
- **=**: sin cambio.

---

## Tabla por concepto

| Concepto | Atributo | Hoy | Cobertura | Valores en catálogo | Lo que pide Séptimo | Propuesta |
|---|---|---|---|---|---|---|
| **C001 Cuaderno** | rayado | OBL | 26/40 | cuadriculado, rayado, doble línea, ferrocarril | cuadriculado (#3, 14, 23, 25, 28, 29, 69) | **OBL =** |
| | hojas | OBL | 30/40 | 40, 50, 80, 100 | 100, y 50 en #29 | **OBL =** (exacto) |
| | materias | OBL | 40/40 | 1, múltiple | — | OBL = |
| | encuadernación | — | 0/40 | — | cosido (#10, 17, 29), argollado (#14, 23, 25, 28) | **NUEVO, OBL** ❓ |
| | tamaño | — | 0/40 | — | grande | **NUEVO, DESC** |
| **C003 Block** | tipo | OBL | 9/12 | cuadriculado, argollado, cartulina, origami | cuadriculado (#18) | **OBL =** |
| | tamano | OBL | 9/12 | carta, media carta, 15×15 | carta | **OBL =** |
| | hojas | OBL | 4/12 | 40–80 | — | **DESC** (baja cobertura; descartaría blocks válidos) |
| **C034 Diccionario** | idioma | OBL | 4/7 | español, español-alemán, español-inglés | español (#5) | **OBL =** |
| **dic-ingles** | idioma | — | 0/3 | — | inglés–inglés (#12) | **NUEVO, OBL** (monolingüe ≠ bilingüe) |
| **C048 Biblia** | edición | — | 0/8 | — | Biblia católica (#1) | **NUEVO, OBL**: completa / infantil-selección ❓ |
| | versión | DESC | — | — | — | DESC = |
| **C008 Regla** | longitud | OBL | 4/5 | 30 cm | 30 cm (#21, 31) | **OBL =** |
| | material | OBL | 1/5 | plástico | acero inoxidable (#31) | **OBL =** (requiere enriquecer) |
| **C018 Compás** | tipo | OBL | 2/3 | escolar, precisión | precisión (#32) | **OBL =** ("escolar" ya no se exige) |
| **C023 Transportador** | grados | DESC | 0/3 | — | 360 (#20) | **OBL** (requiere enriquecer) |
| | material | DESC | — | — | — | DESC = |
| **C036 Juego geometría** | piezas | DESC | 2/3 | 3, 4 | — | DESC = |
| **C024 Bata laboratorio** | color | OBL | 1/3 | blanco | blanca (#54) | OBL = |
| | material | — | 0/3 | — | antifluido (#24) | **NUEVO, DESC** ❓ |
| | manga, talla | DESC | — | — | — | DESC = |
| **C025 Tabla periódica** | tamano | OBL | 3/3 | carta, mediano, grande | grande (#26) | **OBL =** |
| | vigencia | DESC | — | — | — | DESC = |
| **C112 Papel durex** | tamano | — | 0/1 | — | carta (#33), 1/8 (#57) | **NUEVO, OBL** |
| | formato | — | 0/1 | — | sketchbook/block (#33) vs hojas (#57) | **NUEVO, OBL** ❓ |
| **C120 Papel pergamino** | tamano | — | 0/2 | — | 1/8 (#56) | **NUEVO, OBL** |
| **C114 Lápices dibujo** | — | — | — | — | serie H a B | sin atributo |
| **C115 Limpiatipos** | — | — | — | — | — | sin atributo |
| **C050 Lienzo** | dimensiones | DESC | 0/2 | — | ~30×40 (#36) | **DESC =** (dice "aproximadamente") |
| **C093 Tinta china** | color | OBL | 3/3 | negro, dorado, rojo | negra (#38) | **OBL =** |
| **C021 Pincel** | forma | OBL | 3/6 | plano, redondo | "delgados, planos, redondos y abanico" (#39) | ⚠️ ver nota 1 |
| | grosor | OBL | 4/6 | delgado, n5, n6 | delgados | ⚠️ nota 1 |
| | unidades | — | — | — | kit de 12 | **NUEVO, OBL** |
| **C116 Pluma** | puntas intercambiables | — | 0/3 | — | sí (#40) | **NUEVO, OBL** ❓ |
| **C006 Marcador** | tipo | OBL | 9/14 | borrable, permanente, punta fina, punta pincel | acrílico (#41) | **OBL**, agregar valor `acrilico`; ver nota 2 |
| | punta | OBL | 9/14 | (mismos valores que tipo) | micropunta (#55) | **OBL**, valores: fina, pincel, micropunta, biselada |
| | colores | OBL | 6/14 | 4, 12, 20 (cantidad) | — | **DESC** |
| | color | — | 0/14 | — | negro (#55) | **NUEVO, OBL** |
| **C117 Paleta de pintura** | — | — | — | — | paleta mezcladora (#42) | sin atributo; revisar qué productos tiene el concepto ❓ |
| **C027 Pintura** | tipo | OBL | **1/31** (y dice "permanente") | — | acrílica (#43–49) | **OBL** (enriquecer los 31: casi todos son óleo) |
| | color | — | 0/31 | — | cian, magenta, amarillo, blanco, negro, azul, rojo | **NUEVO, OBL** |
| | presentación | — | — | — | tubo | **NUEVO, DESC** |
| | volumen | — | — | — | 45 cc | **NUEVO, DESC** (37–75 ml son equivalentes) |
| | colores | DESC | 1/31 | 12 | — | DESC = |
| **C118 Frascos pintura** | material | — | 0/1 | — | transparente (#50) | **NUEVO, DESC** |
| **C033 Palitos** | unidades | OBL | 2/2 | 10, 500 | — | **DESC** |
| | tipo | DESC | — | — | palos de paleta vs balso (#51) | **OBL** |
| **C040 Toallas y pañitos** | tipo | DESC | — | — | toalla de tela (#52) | **OBL** (tela / húmedo) |
| | unidades | OBL | 2/4 | 72, 100 | — | **DESC** |
| **C057 Vaso o plato** | material | OBL | 6/7 | plástico | plástico (#53) | OBL = |
| | tipo | — | — | — | vaso | **NUEVO, OBL** (vaso / plato) |
| | capacidad | — | — | — | pequeño | **NUEVO, DESC** |
| **C028 Silicona** | presentacion | OBL | 3/3 | barra, líquido | líquida (#60) | **OBL =** |
| | grosor | OBL | 2/3 | delgado, grueso | — | OBL = (solo aplica a barras) |
| **C015 Cinta adhesiva** | tipo | OBL | 6/6 | enmascarar, transparente, doble faz, aislante | enmascarar (#61, 66) | **OBL =** |
| | ancho | DESC | — | — | 2 cm | **DESC =** (18 mm sirve) |
| | largo | DESC | — | — | — | DESC = |
| **C113 Papel iris** | colores | — | 0/11 | — | paquete (surtido) | **NUEVO, DESC** |
| **C041 Cartón** | tamano | OBL | 2/3 | octavo, pliego | octavos (#63, 68) | **OBL =** |
| | color | — | 0/3 | — | de colores (#68) | **NUEVO, OBL** (crema / colores) |
| | tipo | DESC | — | — | — | DESC = |
| **C016 Pegante en barra** | gramaje | OBL | 5/5 | 15 g, 40 g | — | **DESC** |
| **C013 Tijeras** | punta | OBL | 2/3 | punta roma | — | OBL = |
| | tamano | DESC | — | — | — | DESC = |
| **C004 Colores** | unidades | OBL | 20/26 | 6–24 | — | OBL = |
| | forma | OBL | 1/26 | triangular | — | OBL = |
| **C002 Lápiz** | dureza | OBL | 3/5 | HB | — | OBL = |
| | forma | OBL | — | — | — | OBL = |
| | grosor | — | — | — | — (Premium dio jumbo, #83) | ver nota 3 |
| **C005 Borrador** | tipo | OBL | 1/3 | nata | — | OBL = |
| **C007 Tajalápiz** | depósito, orificios | OBL | 2/4, 1/4 | — | — | OBL = |
| **C009 Cartuchera** | tamaño, compartimentos | OBL | 0/16, 7/16 | — | — | OBL = |
| **C012 Esfero** | tinta, color | OBL | 11/15 | azul, negro, rojo, surtido | — | quitar `tinta` (duplica a `color`) |
| **C039 Resaltador** | colores | DESC | 13/21 | 2–8 | — | DESC = |
| **C045 Notas adhesivas** | tamaño, colores | DESC | 0/3 | — | — | DESC = |
| **C032 Hojas** | tipo | OBL | 1/2 | examen | examen (#92) | **OBL =** (enriquecer el otro producto) |
| | tamano | OBL | 1/2 | carta | — | OBL = |
| **C102 Protoboard** | puntos | — | — | — | 400 (#73) | **NUEVO, DESC** |
| **C103 Batería 9V** | recargable | — | — | — | "se sugiere" (#72) | **NUEVO, DESC** |

Sin atributos ni cambios (libros, textos, uniformes): C044 Libro, C134, C133, C137, C110 Audífonos, C131 Uniformes y los conceptos de electrónica en hueco.

---

## Notas

1. **Renglones con varios valores** ("delgados, planos, redondos y abanico"). El extractor toma el primero que encuentra (*plano*) y exigiría pinceles planos, lo contrario de lo pedido. Propongo que, si el renglón enumera varios valores del mismo atributo, ese atributo **no se exija** y en su lugar se exijan las unidades (kit de 12).
2. **C006 tiene `tipo` y `punta` con los mismos valores** en los productos: el dato está duplicado. Propongo que `tipo` = tinta (permanente, borrable, acrílico, agua) y `punta` = forma (fina, micropunta, pincel, biselada), y re-enriquecer los 14 productos.
3. **Lápiz jumbo en Premium (#83):** ningún filtro lo evita, porque el colegio no escribió "delgado". Como Premium es "el más caro que cumple", un jumbo sigue cumpliendo. Si no lo quieres, la salida es un atributo `grosor` con valor por omisión "estándar" para grados ≥ 3.º. Eso ya sería una regla de negocio nueva.

## Decisiones que necesito de ti (marcadas ❓)

1. **Encuadernación de cuaderno (cosido / argollado) obligatoria.** Hoy ningún cuaderno la declara. Si la activo sin enriquecer, todos los cuadernos de Séptimo quedan como hueco. Si la activo después de enriquecer desde los nombres, quedarán como hueco solo los que de verdad no existan. Mi recomendación: obligatoria, enriqueciendo primero.
2. **Biblia: ¿completa obligatoria?** Es decir, que no se acepte "Lecturas de la Biblia para niños" cuando la lista dice "Biblia".
3. **Bata antifluido: ¿obligatoria o descriptiva?** Recomiendo descriptiva: una bata de tela sirve y ninguna del catálogo declara el material.
4. **Durex "sketchbook carta" vs hojas sueltas en octavos.** ¿Obligatorio el formato? Si sí, #33 queda como hueco (no hay sketchbook en el catálogo).
5. **Pluma con puntas intercambiables: ¿obligatorio?** Si sí, la Pilot Parallel del Ahorrador sale y queda solo la Speedball.
6. **Paleta mezcladora (C117):** el concepto contiene "sets de herramientas" Art Rangers que quizá no son paletas. ¿Los reviso y los muevo de concepto si no lo son?
7. **Origen del valor exigido:** propongo extraerlo automáticamente del texto del renglón, con el mismo extractor que ya usa `emparejar`, y dejar el campo `atributos` de la curaduría solo para que el revisor corrija la extracción. La alternativa es llenar a mano los atributos de cada renglón en la curaduría.
