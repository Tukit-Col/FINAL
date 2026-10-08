# Reporte de huecos de catálogo (curaduría)

Consolidado de renglones de listas escolares que **no** quedaron reconocidos tras percepción (Gemini) + parseo + emparejamiento contra el catálogo local. Los reconocidos no aparecen en el cuerpo; sí en el resumen por archivo.

## Resumen por PDF

| Archivo | Págs | Grados | ¿Papá rechazado? | Rec | Abst | Sin | Hueco | Fuera | Fallidas |
|---|---:|---|---|---:|---:|---:|---:|---:|---|
| alamei.pdf | 13 | Once, Noveno, Decimo, Octavo, Sexto, Septimo, Quinto, Cuarto, Tercero, Primero, Segundo, Transicion, Jardin | sí | 134 | 64 | 28 | 2 | 0 | — |
| bahiasolano.pdf | 12 | Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 131 | 56 | 19 | 0 | 0 | — |
| JARDÍN_merged.pdf | 13 | Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 103 | 53 | 0 | 0 | 52 | — |
| LISTA-DE-TEXTOS-Y-UTILES-2021.pdf | 11 | Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 118 | 66 | 23 | 6 | 22 | — |
| LISTA-DE-ÚTILES-2026.pdf | 14 | Prejardin, Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 168 | 64 | 53 | 1 | 34 | — |
| Listas 2026.pdf.pdf | 14 | Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 154 | 77 | 41 | 19 | 63 | — |
| LISTAS-DE-TEXTOS-ESCOLARES-COLEGIO-SAN-JOSE-DE-FONTIBON.pdf | 14 | Prejardin, Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 208 | 76 | 22 | 3 | 49 | — |
| LISTAS-DE-UTILES-2025-ACT.pdf | 15 | Prejardin, Jardin, Preescolar, Primaria, Bachillerato, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 182 | 65 | 52 | 1 | 79 | — |
| LISTAS-TEXTOS-UTILES-2026.pdf | 4 | Transicion, Jardin, Prejardin, Parvulos | sí | 53 | 20 | 3 | 7 | 6 | — |
| matilde.pdf | 11 | Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Primer Ano, Tercer Ano | sí | 169 | 29 | 83 | 0 | 25 | — |
| modelia.pdf | 14 | Prejardin, Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 194 | 59 | 42 | 6 | 120 | — |
| ositodemiel.pdf | 3 | Prejardin, Jardin, Transicion | sí | 53 | 25 | 7 | 3 | 15 | — |
| san pedro.pdf | 22 | Once, Decimo, Noveno, Octavo, Septimo, Sexto, Quinto, Cuarto, Tercero, Segundo, Primero, Transicion, Jardin, Prejardin | sí | 131 | 61 | 103 | 6 | 22 | — |
| TEXTOS-Y-UTILES-ESCOLARES-2026-CACS.docx-1.pdf | 39 | Jardin, Transicion, Primero, Segundo, Tercero, Cuarto, Quinto, Sexto, Septimo, Octavo, Noveno, Decimo, Once | sí | 404 | 211 | 150 | 12 | 107 | — |

- **ositodemiel.pdf**: Reutilizado /tmp/ositodemiel-fase1.json (sin llamar a Gemini). (fuente: cache_ositodemiel)

## Faltantes únicos (1397)

Agrupados por acción sugerida. Clave de deduplicación: texto normalizado + estado + concepto + atributos impuestos.

### agregar concepto (386)

- **`Martes de Prueba Milton Ochoa`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (17×): Alamei, Bahía Solano · grados: Cuarto, Decimo, Jardin, Noveno, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`caja de 12 Colores ecológicos. (sugerido Faber Castell y/o Pelikan).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (11×): Listas de útiles 2025 ACT · grados: Cuarto, Decimo, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero

- **`Audífonos estilo diadema (headphones, no earbuds) con conector tipo auxiliar o usb.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): CACS · grados: Decimo, Noveno, Octavo, Once, Segundo, Septimo, Sexto, Tercero

- **`Franela: blanca con logotipo impreso.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Sexto, Tercer Ano

- **`Mono deportivo: mono de algodón a la cintura holgado con corte recto, color azul marino.`** → *corregido:* `Mono deportivo: mono de algodón a la cintura holgado con corte recto, color azul marina.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Sexto, Tercer Ano

- **`Sweater: color azul marino con insignia cosida o bordada, cuello redondo sin capucha.`** → *corregido:* `Sweater: color azul marina con insignia cosido o bordada, cuello redondo sin capucha.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Sexto, Tercer Ano

- **`Zapatos: deportivos de color negro. (Sin colores ni adornos)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Sexto, Tercer Ano

- **`Zapatos: negros. (Sin adornos blanco, ni suelas de colores)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (8×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Sexto, Tercer Ano

- **`Cartilla Agustiniana (medio virtual en la página del colegio, no se debe comprar).`** → *corregido:* `Cartilla Agustiniana (media virtual en la página del colegio, no se debe comprar).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (7×): CACS · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto, Tercero

- **`Será entregada en el colegio.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (7×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Diseño gráfico`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (6×): Alamei, Bahía Solano · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`Martes de Prueba Milton Ochoa - Prueba importante que permite evaluar el progreso académico de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales.`** → *corregido:* `Martes de Prueba Milton Ochoa - Prueba importante que permite evaluar el progreso academica de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (6×): Alamei, Bahía Solano · grados: Cuarto, Noveno, Octavo, Quinto, Sexto, Tercero

- **`Pantalón: Azul marino de tela, de corte recto y con ruedo cosido a la altura de los talones. (No se permitirá el uso de pantalones strech, ni lycra, ni leggins)`** → *corregido:* `Pantalón: Azul marina de tela, de corte recto y con ruedo cosido a la altura de los talones. (No se permitirá el uso de pantalones strech, ni lycra, ni leggins)`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (6×): Matilde · grados: Cuarto, Primer Ano, Segundo, Sexto, Tercer Ano

- **`Cable usb tipo c de un metro`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (5×): San Pedro · grados: Decimo, Noveno, Octavo

- **`Modulo microcontrolador ESP32 de 30 pines con conector usb tipo C`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (5×): San Pedro · grados: Decimo, Noveno, Octavo

- **`Salidas Pedagógicas (Asistencia Voluntaria): $101.000`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (5×): Lista de útiles 2026 · grados: Decimo, Octavo, Once, Septimo, Sexto

- **`Shield de conexiones para esp32 de 30 pines`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (5×): San Pedro · grados: Decimo, Noveno, Octavo

- **`Botones para protoboard`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): San Pedro · grados: Decimo, Noveno, Octavo, Sexto

- **`Guías pedagógicas $118.160 (Ítem a cobrar incluido en el recibo de matrícula)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): Lista de útiles 2026 · grados: Decimo, Octavo, Septimo, Sexto

- **`Modulo buzzer pasivo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): San Pedro · grados: Decimo, Noveno, Octavo

- **`Modulo led RGB`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): San Pedro · grados: Decimo, Noveno, Octavo

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS, una por periodo.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): Listas 2026 · grados: Cuarto, Quinto, Segundo, Tercero

- **`Salidas Pedagógicas (Asistencia Voluntaria): $90.000`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): Lista de útiles 2026 · grados: Cuarto, Primero, Quinto, Segundo

- **`SERVO MOTOR SG90`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): San Pedro · grados: Decimo, Noveno

- **`Un compás de precisión`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (4×): Lista de útiles 2026 · grados: Decimo, Once, Septimo, Sexto

- **`*En el mes de ENERO 2026 se enviará una circular con las instrucciones, fechas y medios de pago. Les agradecemos esperar la información institucional.`** → *corregido:* `*En el mes de ENERO 2026 se enviará una circular con las instrucciones, fichas y medios de pago. Les agradecemos esperar la información institucional.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Octavo, Quinto, Sexto

- **`1 batería de 9V con adaptador`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Arreglo de leds de 8 canales`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Decimo, Noveno

- **`Audífonos estilo diadema (headphones, no earbuds) con conector tipo auxiliar o usb`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): CACS · grados: Cuarto, Primero, Quinto

- **`Calendario Programador año 2026 (según indicación de orientación escolar)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Listas 2026 · grados: Decimo, Noveno, Once

- **`Cepillo de dientes`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`CEPILLOS DENTALES CON PROTECTOR INDIVIDUAL`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Chemise: Azul de acuerdo al nivel, con insignia cosida o bordada.`** → *corregido:* `Chemise: Azul de acuerdo al nivel, con insignia cosido o bordada.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Matilde · grados: Primer Ano, Segundo, Tercer Ano

- **`Chemise: Blanca de acuerdo al nivel, con insignia cosida o bordada.`** → *corregido:* `Chemise: Blanca de acuerdo al nivel, con insignia cosido o bordada.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Matilde · grados: Cuarto, Segundo, Sexto

- **`Dibujo - Block DIN A4 horizontal, Carpeta plastificada con gancho legajador.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Alamei · grados: Cuarto, Quinto, Tercero

- **`Fotorresistencias de 5mm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Guías pedagógicas $102.980 (Ítem a cobrar incluido en el recibo de matrícula)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Lista de útiles 2026 · grados: Jardin, Prejardin, Transicion

- **`Guías pedagógicas $73.194 (Ítem a cobrar incluido en el recibo de matrícula)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Lista de útiles 2026 · grados: Cuarto, Primero, Segundo

- **`Headphones for some activities in the English Lab room`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Listas 2026 · grados: Noveno, Octavo, Septimo

- **`Leds de colores variados (5 rojos, 5 amarillos, 5 azules, 5 verdes, 5 blancos)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Noveno, Octavo, Sexto

- **`Pantalla OLED 128 x 64`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Decimo, Noveno

- **`Peinilla o cepillo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`Pliegos Grandes de Papel Bond Blanco. (Sin identificar)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Matilde · grados: Cuarto, Quinto, Sexto

- **`Protoboard 830 puntos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Noveno, Octavo, Sexto

- **`Salidas Pedagógicas (Asistencia Voluntaria) $90.000`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Lista de útiles 2026 · grados: Jardin, Prejardin, Transicion

- **`Se realizará una convivencia y una salida pedagógica interdisciplinar.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Sensor de distancia infrarrojo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Octavo

- **`sensor de temperatura DHT 11`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Decimo, Noveno

- **`Sensor de temperatura y humedad DHT11`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Octavo

- **`trasportador`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San José de Fontibón · grados: Decimo, Noveno, Once

- **`Un vaso plástico`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`Una colonia.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`una muda de ropa marcada.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Una RESMA DE PAPEL TAMAÑO OFICIO y 08 ROLLOS DE PAPEL SANITARIO`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Matilde · grados: Cuarto, Quinto, Tercer Ano

- **`1 switch o interruptor`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`10 cables de macho- macho de 10cm, 10 cables macho-macho de 20cm y 10 cables macho hembra de 20cm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Arduino Uno`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Batería de 9V (se sugiere recargable)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Biology - Miller Edición 2019 Ed Savvas ( 6° a 11°)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Modelia · grados: Septimo, Sexto

- **`Biology - Miller Edición 2019 Ed Savvas (6° a 11°)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Modelia · grados: Octavo, Once

- **`Broche de batería de 9V`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`caja de 12 Colores Jumbo Triangular. (sugerido Faber Castell y/o Pelikan).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas de útiles 2025 ACT · grados: Prejardin, Transicion

- **`Camisa blanca manga larga`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Chemise: Beige de acuerdo al nivel, con insignia cosida o bordada.`** → *corregido:* `Chemise: Beige de acuerdo al nivel, con insignia cosido o bordada.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Matilde · grados: Cuarto, Quinto

- **`juego de 12 Plumones. (sugerido Faber Castell y/o Pelikan).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas de útiles 2025 ACT · grados: Prejardin, Transicion

- **`Juego geométrico (regla, escuadra, transportador)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Lista textos y útiles 2021 · grados: Cuarto, Quinto

- **`Melódica de 2 octavas, de cualquier marca.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Cuarto, Quinto

- **`MODULO DE SENSOR DE LUZ`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Decimo

- **`Pantalón: Azul marino de tela, de corte recto y con ruedo cosido a la altura de los talones.`** → *corregido:* `Pantalón: Azul marina de tela, de corte recto y con ruedo cosido a la altura de los talones.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Matilde · grados: Cuarto, Quinto

- **`paquete base ten blocks Smart pack. método Singapur (se utiliza en transición, 1°, 2°, 3° 4° y 5°). (solo deben comprar los estudiantes nuevos).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Modelia · grados: Cuarto, Tercero

- **`Paquete de Jumpers x 10 unidades de 10cm de largo (hembra - macho)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de leds x 10 unidades (diferentes colores)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de resistencias x 20 unidades 1/4W de diferentes valores`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`paquete de sobres de acetato tamaño carta`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas 2026 · grados: Cuarto, Quinto

- **`Paquete multivariado Manitas Creativas Ref. PM 1014`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Lista de útiles 2026 · grados: Jardin, Prejardin

- **`paquetes de Fomi en Octavos.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas de útiles 2025 ACT · grados: Prejardin, Transicion

- **`Pre-cuadritos de 100 cuaderno grande`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Alamei · grados: Jardin, Transicion

- **`Protoboard de 400 puntos mediana`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Resistencias de alta potencia 2W y precisión del 1% (220,1k,10k,4.7k) 10 de cada una`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Saco naranja institucional en hilo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Salidas Pedagógicas (Asistencia Voluntaria)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Lista de útiles 2026 · grados: Noveno, Tercero

- **`Se realizará una convivencia y una salida pedagógica interdisciplinar`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Sensor de distancia laser VL53L0x con patas a 90° soldadas`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Decimo

- **`Será entregada en el colegio`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Textos : Educación Artística.`** → *corregido:* `Textos : Educación Artistico.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Matilde · grados: Primer Ano, Segundo

- **`Todo debidamente marcado`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Un potenciómetro de 10k y uno de 100k con tapa`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Noveno, Octavo

- **`Una almohada pequeña con su respectiva funda dentro de una bolsa plástica tipo ziploc`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Jardin, Prejardin

- **`Una muda de ropa de cambio en caso de necesidad.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Una sábana encauchada con medidas de 130 x 70 cm.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): San Pedro · grados: Jardin, Prejardin

- **`Xilófono de 8 placas con baquetas debidamente marcado`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): CACS · grados: Primero, Transicion

- **`(Actualización) Kit de robótica básica 11°. RobotSchool`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Once

- **`(Actualización) Kit de robótica básica 6°. RobotSchool`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Sexto

- **`(Actualización) Kit de robótica básica 7°. RobotSchool`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Septimo

- **`(Actualización) Kit de robótica básica 8°. RobotSchool`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Octavo

- **`(Actualización) Kit de robótica básica 9º. RobotSchool`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Noveno

- **`-Certificación de lengua: Examen de certificación del idioma inglés de acuerdo con los niveles del Marco Común Europeo de referencia para las lenguas, avalado según resolución 12730 del 2017 del MEN.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Once

- **`-Dos obras literarias en inglés. Se enviará el nombre al inicio del curso.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`-Headphones for some activities in the English Lab room`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`-Headphones for some activities in the English Lab room.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Once

- **`1 batería de 9V`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 buzzer`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 caja de counters x 100 método Singapur (jardín, Transición y 1°) (solo deben comprar los estudiantes nuevos).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Primero

- **`1 Juego didáctico de mesa acorde a la edad`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Primero

- **`1 metro de cable estañado calibre 22`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 motor generador proyecto escolar`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 motoreductor`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 motorreductor`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Septimo

- **`1 paquete base ten blocks Smart pack. método Singapur (se utiliza en transición, 1°, 2° y 3°) (solo deben comprar los estudiantes nuevos).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Primero

- **`1 paquete base ten blocks Smart pack. método Singapur (se utiliza en transición, 1°, 2°, 3° 4° y 5°). (solo deben comprar los estudiantes nuevos).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Quinto

- **`1 Protoboard Genérica MB-102 400 puntos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 sensor de proximidad HCSR04`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 sensor de proximidad IR`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 switch o interruptor tipo balancín`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 switch o interruptor tipo balancín.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 Un cuaderno cuadriculado grande cosido de 100 hojas.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Segundo

- **`10 cables de macho-macho de 10cm, 10 cables macho-macho de 20cm y 10 cables macho hembra de 20cm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Noveno

- **`10 jumpers hembra-hembra 20cm de largo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`10 jumpers macho-hembra 20cm de largo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`10 LEDs de diferentes colores`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 cables caimanes`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 leds`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 resistencias de 330 ohm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 resistencias de 330 ohm o 1k Ohm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 switch de dos posiciones (2 pines)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`3 leds`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`3 resistencias de 330 ohm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`3 resistencias de 330 ohm o 1k 0hm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`30 jumpers macho-macho 20cm de largo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`4 caimanes eléctricos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`4 caimanes eléctricos (15-20 cm de longitud)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`4 caimanes eléctricos cortos (15 cm) de longitud`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`4 leds`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`4 pulsadores de 4 pines`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Septimo

- **`6 leds`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Adiós, Oscurita.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Sexto

- **`Atlas Universal y de Colombia`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Audífonos Convencionales de casco alámbricos jack 3.5 mm, recomendable cable largo y no de celular.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Audífonos Convencionales de casco alámbricos jack 3.5mm, recomendable cable largo y no de celular.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Baletas para Danzas o Gimnasia negras (Que no sean de disfraz) Marcadas, para niños y niñas.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Baletas para Danzas o Gimnasias negras (Que no sean de disfraz) marcadas.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`batería de 9V con adaptador`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Biology - Miller Edición 2019 Ed Savvas`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Decimo

- **`Biology - Miller Edición 2019 Ed Savvas (6º a 11º)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Noveno

- **`CABELLO ORGANIZADO SIN PEINADOS NI COLORES EXTRAVAGANTES Y CORTE CLÁSICO`** → *corregido:* `CAMELLO ORGANIZADO SIN PEINADOS NI COLORES EXTRAVAGANTES Y CORTE CLÁSICO`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Cabello organizado sin peinados ni colores extravagantes y corte clásico. Para niñas cabello recogido, accesorios blancos o azul oscuro.`** → *corregido:* `Camello organizado sin peinados ni colores extravagantes y corte clásico. Para niñas camello recogido, accesorios blancos o azul oscuro.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Cabello recogido sin peinados ni colores extravagantes, accesorios blancos azul oscuro.`** → *corregido:* `Camello recogido sin peinados ni colores extravagantes, accesorios blancos azul oscuro.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Cable mini usb`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cables dupont hembra- hembra de 10 cm y 20 cm. 20 unidades de cada uno`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Decimo

- **`Cables macho a caimán de 20cm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`caimanes eléctricos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Caja de 12 Colores Jumbo Triangular Delgados`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`Caja de 12 crayolas`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`Camiseta blanca según modelo.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Sexto

- **`Cartilla Agustiniana`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto

- **`Cartilla Agustiniana (medio digital en la página del colegio, no se debe comprar)`** → *corregido:* `Cartilla Agustiniana (media digital en la página del colegio, no se debe comprar)`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Primero

- **`Cartilla Agustiniana (medio digital en la página del colegio, no se debe comprar).`** → *corregido:* `Cartilla Agustiniana (media digital en la página del colegio, no se debe comprar).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Segundo

- **`Cartilla Agustiniana (medio virtual en la página del colegio, no se debe comprar)`** → *corregido:* `Cartilla Agustiniana (media virtual en la página del colegio, no se debe comprar)`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Quinto

- **`CARTILLA DE GUIAS PREJARDIN G.M.R`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`CARTILLA DE GUIAS TRANSICION G.M.R`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Cartilla de Pruebas Saber (se publicará en el classroom de inglés al iniciar clase, para ser impresa por los estudiantes como parte de la preparación para las pruebas Saber 11)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Once

- **`Cartillade Guias Jardin G.M.R`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`Clues All Around 1. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Primero

- **`Clues All Around 2. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Segundo

- **`Clues All Around 3. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Tercero

- **`Clues All Around 4. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Cuarto

- **`Clues All Around 5. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Quinto

- **`Clues All Around 6. McGraw Hill. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Sexto

- **`Corbata azul a cuadros`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Corbata azul oscuro`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Crimen y castigo - Fiódor Dostoievski`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Decimo

- **`Crónica de una muerte Anunciada - Gabriel García Márquez`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Septimo

- **`Crónica de una muerte anunciada. Autor: Gabriel García Márquez. Cualquier editorial`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Noveno

- **`Cuerno: Empastado grande de una línea. (no espiral).`** → *corregido:* `Cuerpo: Empastado grande de una línea. (no espiral).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Quinto

- **`Dibujo - Lápices Mirado 2, borrador miga de pan, colores de buena calidad, tajalápiz con recipiente, Block Dian A4 Horizontal, carpeta plastificada con gancho legajador.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Sexto

- **`Dibujo - Lápices Mirado 2, borrador miga de pan, colores de buena calidad, tajalápiz con recipiente, Block Din A4 Horizontal, carpeta plastificada con gancho legajador.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Octavo

- **`Dibujo: Block DIN A4 horizontal, Carpeta plastificada con gancho legajador.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Segundo

- **`Dinosaurios`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Diseño gráfico - Lápices HB, 2H, 2B, 6B, borrador miga de pan, escuadras 30° y 45°, tabla de diseño de formato 1/4 (Se puede mandar a hacer en una carpintería)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Bahía Solano · grados: Noveno

- **`Diseño gráfico Lápices Mirado 2, borrador miga de pan, colores de buena calidad, tajalápiz con recipiente, Block Dian A4 Horizontal`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Once

- **`Display 8 segmentos con cátodo común`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Noveno

- **`Doce cuentos peregrinos - Gabriel García Márquez`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Octavo

- **`Ecolines de colores primarios, blanco y negro.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`El cetro del niño rey.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Sexto

- **`El coronel no tiene quien le escriba. Autor: Gabriel García Márquez. Cualquier editorial`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Octavo

- **`El cromosoma de Beatriz`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`El niño que pasaba desapercibido.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`El paseador de perros`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Quinto

- **`El Principito`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`El soldadito de plomo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`El viejo y el mar`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Quinto

- **`El Zoro`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`ESPAÑOL EL QUE TENGA ENCASA`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`EXPRESATE CIENCIAS SOCIALES 2`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Segundo

- **`Fábulas de Esopo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`Falda azul gallineto a la rodilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscura, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo`** → *corregido:* `Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscuro, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierda`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`FILOSOFIA EL QUE TENGA ENCASA.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`Fuente de alimentación 12V 1.5A`** → *corregido:* `Fuerte de alimentación 12V 1.5A`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Fuente de alimentación para protoboard`** → *corregido:* `Fuerte de alimentación para protoboard`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Guía de Matemática 1° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Primero

- **`Guía de Matemática 2° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Segundo

- **`Guía de Matemática 3° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Tercero

- **`Guía de Matemática 4° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Cuarto

- **`Guía de Matemática 5° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Quinto

- **`Guía de Matemática 6° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Sexto

- **`Guías pedagógicas`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Noveno

- **`Guías pedagógicas $118.160`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Once

- **`Guías pedagógicas $73.194`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`Guías pedagógicas (Ítem a cobrar incluido en el recibo de matrícula)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Guitarra (opcional).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Noveno

- **`Headphones for some activities in the English Lab room.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Inglés: Cambridge Pippa and pop 1 Workbook - American English`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Prejardin

- **`Inglés: Cambridge Pippa and pop 2 Student Book American English`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Jardin

- **`Inglés: Cambridge Pippa and Pop 3 Student Book American English.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Transicion

- **`Inglés: English i-World A1 University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`Ingles: English i-World A1+ University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Ingles: English i-World A2 Students Book University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Inglés: English i-World B1 Students Book University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`Inglés: English i-World B1+ Students Book University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Inglés: English i-World B2 Students Book University of Dayton`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Once

- **`Interruptor para protoboard`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Sexto

- **`joystick Analógico para Arduino (KY-023)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Juego de 12 Plumones. (sugerido Faber Castell y/o Pelikan)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`juego de mesa.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Juego de precostura.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Juego didáctico de lectura y escritura. Opciones: Rompecabezas, loterías, juegos ABC. (Solo se requiere uno).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Transicion

- **`Juego didáctico de mesa acorde a su edad`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Quinto

- **`juego Didáctico de mesa, se sugiere rompecabezas, lotería, parques, etc`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Jardin

- **`Juego Didáctico en inglés (animales, frutas, números)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`juego didáctico en inglés (animales, frutas, partes del cuerpo)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Juego didáctico que se indicará en la primera reunión de padres.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`Juego geométrico (escuadra, regla y transportador)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`jumpers macho-hembra`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`jumpers macho-macho`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`La casa de los espíritus. Autor: Isabella Allende. Cualquier editorial`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Noveno

- **`La Odisea - Homero`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Once

- **`Las venas abiertas de América latina, Eduardo Galeano, -`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Noveno

- **`LEARNING LANDS STUDENTS BOOK LEVEL 2 + WORBOOK`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Segundo

- **`Lecto Escritura: Cuadernillo ALFA Y BETA programa letras edición Golden.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Jardin

- **`Lecto Escritura: Cuadernillo ELFO Programa Letras Golden Edición.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Prejardin

- **`Lecto Escritura: Cuadernillo Gamma y Decodifica programa letras edición Golden.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Transicion

- **`Lectura autónoma`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Lectura autónoma: (los estudiantes llevan al aula su texto favorito para compartirlo con el grupo)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Septimo

- **`Lectura Multidimensional Método 84H`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Sexto

- **`Lectura Multidimensional Método 84H - Grado Octavo.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Octavo

- **`leds`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`leds diferentes colores`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Level Up 3 Student´s Book and Workbook. E. Cambridge.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Tercero

- **`Level Up 4 Student´s Book and Workbook - Cambridge.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Cuarto

- **`Level Up 5 Student´s Book and Workbook - Cambridge.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Quinto

- **`Martes de Prueba Milton Ochoa - Prueba importante que permite evaluar el progreso académico de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales`** → *corregido:* `Martes de Prueba Milton Ochoa - Prueba importante que permite evaluar el progreso academica de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Masculino: Pantaloneta de ba%f1o (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de nataci%f3n.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Quinto

- **`Masculino: Pantaloneta de baño (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de natación.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Sexto

- **`Matemáticas Jenga 8. Ediciones Milenio S.A.S.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Octavo

- **`Matemáticas: Animaplanos 7`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Matemáticas: Cartilla animaplanos 6`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`Matemáticas: Math in focus edition (KB) Singapur math by Marshal Cavendish.`** → *corregido:* `Matemáticas: Math in focus edicion (KB) Singapur math by Marshal Cavendish.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Jardin

- **`Matemáticas: Math in focus Student edition 1A Y 1B Singapur math by Marshal Cavendish.`** → *corregido:* `Matemáticas: Math in focus Student edicion 1A Y 1B Singapur math by Marshal Cavendish.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Transicion

- **`Math in Focus: Singapore Math - English Student Edition set course 1. A Y B.`** → *corregido:* `Math in Focus: Singapore Math - English Student Edicion set course 1. A Y B.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Quinto

- **`Math in Focus: Singapore Math - Spanish Student Edition set course 2. (A&B).`** → *corregido:* `Math in Focus: Singapore Math - Spanish Student Edicion set course 2. (A&B).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Sexto

- **`Mi universo lector. Grado 5. Grupo Educativo Calidad SAS. Bogotá Colombia.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`módulo Puente H (L298N recomendado)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`módulo RELAY de 1 canal 5V`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Módulos de aventuras de aprendizaje Cantorín`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Motor dc con hélice y base`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`motor DC rectangular`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`motor generador proyecto escolar`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Motorreductor amarillo con rueda`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Música: Elegir una de las opciones: "Flauta, melódica, guitarra"`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Música: Elegir una de las opciones: "Flauta, melódica, guitarra, organeta o xilófono"`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`Música: Elegir una de las opciones: "Organeta, melódica, Flauta o guitarra"`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`Novela: El gigante egoísta. (Óscar Wilde)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Segundo

- **`Novela: Relato de un Náufrago. (Gabriel G. Márquez)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Segundo

- **`obligatorio para ingreso a laboratorios de ciencias naturales.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Panchoneta azul oscuro según modelo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Pantalón azul Oscuro en lino O gabardina, manga recta según modelo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`paquete base ten blocks Smart pack. método Singapur (se utiliza en transición, 1°, 2° y 3°). (solo deben comprar los estudiantes nuevos).`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`paquete de 20 resistencias surtidas a 1/4 W)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de Jumpers x 10 unidades de 10cm de largo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de Jumpers x 10 unidades de 10cm de largo (macho - macho)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de pañuelitos húmedos por 100 unidades.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Paquetes de (1/8 cartulina) color (amarillo, azul, verde, agua marina o similares)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Quinto

- **`Para las niñas: una falda de rotonda y larga. Para los niños: un sombrero y pañoleta para ensayo. Los mismos del año anterior. Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Para las niñas: una falda rotonda y larga`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Para las niñas: una falda rotonda y larga. Para los niños: un sombrero y una pañoleta para ensayo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Primero

- **`Para las niñas: una falda rotonda y larga. Para los niños: un sombrero y una pañoleta para ensayo. Los mismos del año anterior.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Para las niñas: una falda rotonda y larga. Para los niños: un sombrero y una pañoleta para ensayo. Los mismos del año anterior. Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Para los niños: un sombrero y pañoleta para ensayo. Los mismos del año anterior`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Phenomenal Science 2 Student Book. Ed Pearson.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Phenomenal Science 6 Student book. Ed Pearson.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Quinto

- **`Pre- cuadritos de 100 cuaderno grande`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Jardin, Transicion

- **`Pre-cuadritos de 100 cuaderno grande - Dimensión Lógico Matemática`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Precuadritos de 100 cuaderno grande`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Alamei · grados: Transicion

- **`Prepare Level 3 Second Edition Student's Book and Workbook with digital pack – Cambridge.`** → *corregido:* `Prepare Level 3 Second Edicion Student's Book and Workbook with digital pack – Cambridge.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Sexto

- **`Prepare Level 4 (B1) o Prepare Level 5 (B1+) Second Edition Student’s Book and Workbook with digital pack – Cambridge. (El texto se debe comprar de acuerdo con la clasificación del estudiante, según la información compartida por VPS).`** → *corregido:* `Prepare Level 4 (B1) o Prepare Level 5 (B1+) Second Edicion Student’s Book and Workbook with digital pack – Cambridge. (El texto se debe comprar de acuerdo con la clasificación del estudiante, según la información compartida por VPS).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Octavo

- **`Prepare Level 4 Second Edition Student´s Book and Workbook with digital pack – Cambridge.`** → *corregido:* `Prepare Level 4 Second Edicion Student´s Book and Workbook with digital pack – Cambridge.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Septimo

- **`Prepare Level 5 (B1+) / Prepare Level 6 (B2) Second Edition Student’s Book and Workbook with digital pack – Cambridge. (El texto se debe comprar de acuerdo con la clasificación del estudiante, según la información compartida por VPS).`** → *corregido:* `Prepare Level 5 (B1+) / Prepare Level 6 (B2) Second Edicion Student’s Book and Workbook with digital pack – Cambridge. (El texto se debe comprar de acuerdo con la clasificación del estudiante, según la información compartida por VPS).`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Noveno

- **`Prepare Level 7 Second Edition Student's Book and Workbook with digital pack - Cambridge.`** → *corregido:* `Prepare Level 7 Second Edicion Student's Book and Workbook with digital pack - Cambridge.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Decimo

- **`Prepare Level 8 Second Edition Student’s Book and Workbook with digital pack – Cambridge.`** → *corregido:* `Prepare Level 8 Second Edicion Student’s Book and Workbook with digital pack – Cambridge.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Modelia · grados: Once

- **`Primer periodo: - Libro prescrito: material en el colegio - Lectura autónoma: Hamlet. Autor: William Shakespeare. Editorial: Cualquier editorial.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Once

- **`Primer periodo: - Libro prescrito: material en el colegio. - Lectura autónoma: Edipo Rey. Autor: Sófocles. Cualquier editorial.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`PRIMER SEMESTRE: Cuentos de la Selva (Horacio Quiroga) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Sexto

- **`PRIMER SEMESTRE: Cuentos de Unamuno, El espejo de la muerte (Miguel de Unamuno) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Decimo

- **`PRIMER SEMESTRE: Cuentos del Olimpo (María García)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`PRIMER SEMESTRE: El mago de oz (Lyman Frank)`** → *corregido:* `PRIMER SEMESTRE: El mago de oz (Lyman Franz)`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`PRIMER SEMESTRE: Ensayos - Antología (Varios) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Once

- **`PRIMER SEMESTRE: Jerónimo y los siete sabios (María García Esperón)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`PRIMER SEMESTRE: La carta robada y otros cuentos (Edgar Allan Poe) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Septimo

- **`PRIMER SEMESTRE: Voces Anónimas - Preludio (Guillermo Lockhart) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Octavo

- **`Protoboard Genérica MB-102 830 puntos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Prueba importante que permite evaluar el progreso académico de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales.`** → *corregido:* `Prueba importante que permite evaluar el progreso academica de los estudiantes, fortalecer sus habilidades de razonamiento y prepararlos con anticipación para los desafíos de las pruebas nacionales.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Bahía Solano · grados: Octavo

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Septimo

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS, un simulacro por periodo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS, un simulacro por periodo.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Once

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS, una por periodo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Octavo

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS, uno por periodo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Noveno

- **`Pruebas del proyecto USO PEDAGÓGICO DE LOS RESULTADOS.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Querido dragón.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Ramón y Julieta.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 10`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 11`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Once

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 2`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 3`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 4`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 5`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 6`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 7`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 8`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Religión: EMAUS Camino de esperanza RELIGIÓN CATÓLICA 9`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`Religión: EMAUS Camino de esperanza. RELIGIÓN CATÓLICA 1`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San José de Fontibón · grados: Primero

- **`resistências de 330 ohm o 1k Ohm`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Resistencias de alta potencia 2W (220, 1k, 10k, 4.7k) 5 de cada una`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Noveno

- **`resistencias diferente amperaje`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`SCIENCE ADVENTURE 2`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Segundo

- **`Se desarrollarán guías para fotocopiar que servirán de apoyo académico.`** → *corregido:* `Se desarrollarán guías para fotocopiar que servirán de apoyo academica.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Segundo

- **`Se realizará una convivencia y una salida pedagógica interdisciplinaria.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Se realizará una convivencia y una salida pedagógica interdisciplinaria. Se realizará dos simulacros de pruebas SABER 11`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Se realizará una convivencia y una salida pedagógica interdisciplinaria. Se realizará un simulacro de pruebas SABER. Se realizará una prueba de aptitudes e intereses profesionales. (orientación profesional)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Se sugiere comprar una maleta grande de rodachines, donde se puedan guardar las carpetas y materiales de uso diario. Por favor marcarla en un lugar visible.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Transicion

- **`Segundo periodo: - Libro prescrito: Cien años de soledad. Autor: Gabriel García Márquez. Editorial: cualquier editorial. - Lectura autónoma: material en el colegio`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Once

- **`SEGUNDO SEMESTRE: 97 horas de la tierra a la luna (Julio Verne) con cartilla`** → *corregido:* `SEGUNDO SEMESTRE: 97 hojas de la tierra a la luna (Julio Verde) con cartilla`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Sexto

- **`SEGUNDO SEMESTRE: Aventura de Sherlock (Arthur Conan)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`SEGUNDO SEMESTRE: El estudiante y otros Cuentos (Antón Chejov) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Once

- **`SEGUNDO SEMESTRE: El jardín secreto (Frances Hodgson)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`SEGUNDO SEMESTRE: Isu, el tiburón desdentado (Seve Calleja)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`SEGUNDO SEMESTRE: Metamorfosis (Frank Kafka) con cartilla`** → *corregido:* `SEGUNDO SEMESTRE: Metamorfosis (Franz Kafka) con cartilla`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Decimo

- **`SEGUNDO SEMESTRE: Nínive y el crucero de la muerte (Francisco Rengifo) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Octavo

- **`SEGUNDO SEMESTRE: Vuelven las leyendas (Celso Román) con cartilla`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista de útiles 2026 · grados: Septimo

- **`Sensor de distancia infrarojo`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Noveno

- **`Sensor de movimiento PIR HCSR501`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`servo Motor`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Share it 2. Student Book and Share Book. Nave PK 2.Placement Test. For el proceso de compra seguir instrucciones que se socializarán iniciando el año 2026.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`Share it 3. Student Book and Share Book. Nave PK 3. Placement Test. Para el proceso de compra se darán las directrices al iniciar 2026.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`Share it 4. Student Book and Share Book. Nave PK 4. Placement test.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`Share it 5. Student Book and Share Book. Nave PK 5. Placement Test.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`Sobres de manila blanco tamaño oficio`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`sobres de manila blanco tamaño oficio.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`Sudadera azul claro. (martes y jueves)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Sudadera azul oscura (Lunes, miércoles y viernes)`** → *corregido:* `Sudadera azul oscuro (Lunes, miércoles y viernes)`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Sudadera azul oscura institucional según modelo.`** → *corregido:* `Sudadera azul oscuro institucional según modelo.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`switch o interruptor`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Tenis completamente blancos de amarrar`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Tenis de cordón totalmente blancos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Tercer período: Libro prescrito: material en el colegio -Lectura autónoma: La rebelión de la granja. Autor George Orwell. Cualquier editorial`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`Texto: Cuaderno de actividades Castellano 1.`** → *corregido:* `Texto: Cuaderno de actividades Castellana 1.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Primer Ano

- **`títere correspondiente algún personaje (Persona), (animal) o rol. Ejemplo: Mujer, hombre, niño, niña bombero(a), enfermera(a), cocodrilo, tigre etc.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`títere correspondiente algún personaje (Persona), (animal) o rol. Ejemplo: Mujer, hombre, niño, niña bombero(a), enfermera(o), cocodrilo, tigre etc.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Jardin

- **`Todo debidamente marcado.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Un lazo o cuerda para saltar.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`Un potenciómetro de 1k, uno de 2,5k y uno de 5k con tapa`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Sexto

- **`Una caja de pasteles secos`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Una cartuchera dotada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con`** → *corregido:* `Una cartuchera dorada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Una cartuchera dotada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, esfero negro, resaltadores, tijeras y 1 pegante en barra 125 gr`** → *corregido:* `Una cartuchera dorada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, esfero negro, resaltadores, tijeras y 1 pegante en barra 125 gr`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto

- **`Una cartuchera dotada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, esfero negro, resaltadores, tijeras y 1 pegante en barra 125 gr.`** → *corregido:* `Una cartuchera dorada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, esfero negro, resaltadores, tijeras y 1 pegante en barra 125 gr.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Tercero

- **`Una cartuchera dotada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, tijeras punta roma y 1 pegante en barra 125 gr. Todo marcado con nombre y apellido, no iniciales. De uso diario. Mantener dotada todo el año. Se utilizará en el salón en las diferentes clases.`** → *corregido:* `Una cartuchera dorada con: 1 lápiz negro delgado, 1 lápiz rojo delgado, 1 borrador de nata, 1 tajalápiz con portabasura, colores delgados X12, tijeras punta roma y 1 pegante en barra 125 gr. Todo marcado con nombre y apellido, no iniciales. De uso diario. Mantener dorada todo el año. Se utilizará en el salón en las diferentes clases.`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Una RESMA DE PAPEL TAMAÑO OFICIO`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Segundo

- **`UNA RESMA DE PAPEL TAMAÑO OFICIO y 08 ROLLOS DE PAPEL SANITARIO, (deben ser entregado al docente guía en su primer encuentro)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Primer Ano

- **`Unidad Lupita.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`Valores. Catequesis 4° Grado. (Se venderá en el colegio)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Matilde · grados: Cuarto

- **`Xilófono de una octava (8 notas), puede ser de madera o pasta. Importante: que no sea de juguete`** → *corregido:* `Xilófono de una octavo (8 notas), puede ser de madera o pasta. Importante: que no sea de juguete`
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): San Pedro · grados: Transicion

- **`Y de regalo... ¡superpoderes!`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`Zapato colegial azul en material`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Zapato colegial negro en material`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

### agregar producto (42)

- **`Monogafas`**
  - estado: `hueco_catalogo` · concepto: monogafas · attrs: —
  - motivo: Entendimos monogafas y el catalogo no tiene producto.
  - colegios (6×): Lista textos y útiles 2021 · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Muda de ropa marcada`**
  - estado: `hueco_catalogo` · concepto: muda de ropa · attrs: —
  - motivo: Entendimos muda de ropa y el catalogo no tiene producto.
  - colegios (4×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`Bolsa negra de basura`**
  - estado: `hueco_catalogo` · concepto: bolsa de basura · attrs: —
  - motivo: Entendimos bolsa de basura y el catalogo no tiene producto.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`frasco de jabón líquido.`**
  - estado: `hueco_catalogo` · concepto: jabon · attrs: presentacion=liquido
  - motivo: Entendimos jabon y el catalogo no tiene producto.
  - colegios (3×): Listas 2026 · grados: Quinto, Segundo, Tercero

- **`Muda de ropa (short, camiseta, medias y ropa interior), dentro de una bolsa plástica para utilizarla cuando se requiera.`**
  - estado: `hueco_catalogo` · concepto: muda de ropa · attrs: —
  - motivo: Entendimos muda de ropa y el catalogo no tiene producto.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`Plato y vaso de plástico`**
  - estado: `hueco_catalogo` · concepto: vaso o plato · attrs: material=plastico
  - motivo: Entendimos vaso o plato y el catalogo no tiene producto.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Bolsa de jabón líquido de manos por 500 ml.`**
  - estado: `hueco_catalogo` · concepto: jabon · attrs: presentacion=liquido
  - motivo: Entendimos jabon y el catalogo no tiene producto.
  - colegios (2×): Listas 2026 · grados: Jardin, Transicion

- **`Dibujo`**
  - estado: `hueco_catalogo` · concepto: tablero de dibujo · attrs: —
  - motivo: Entendimos tablero de dibujo y el catalogo no tiene producto.
  - colegios (2×): Alamei · grados: Primero, Septimo

- **`Flauta dulce`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (2×): San Pedro · grados: Primero, Segundo

- **`flauta dulce se sugiere Yamaha.`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (2×): Listas 2026 · grados: Primero, Tercero

- **`Flauta dulce soprano, se sugiere de marca Yamaha referencia YRS23 con forro`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=soprano
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Flauta dulce.`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (2×): Modelia · grados: Quinto, Sexto

- **`frasco de gel de manos.`**
  - estado: `hueco_catalogo` · concepto: gel antibacterial · attrs: presentacion=gel
  - motivo: Entendimos gel antibacterial y el catalogo no tiene producto.
  - colegios (2×): Listas 2026 · grados: Cuarto, Quinto

- **`Pelota fuchi`**
  - estado: `hueco_catalogo` · concepto: balon · attrs: —
  - motivo: Entendimos balon y el catalogo no tiene producto.
  - colegios (2×): Listas 2026 · grados: Jardin, Transicion

- **`1 juego de baquetas.`**
  - estado: `hueco_catalogo` · concepto: instrumento de percusion · attrs: —
  - motivo: Entendimos instrumento de percusion y el catalogo no tiene producto.
  - colegios (1×): Modelia · grados: Octavo

- **`baquetas.`**
  - estado: `hueco_catalogo` · concepto: instrumento de percusion · attrs: —
  - motivo: Entendimos instrumento de percusion y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Primero

- **`Flauta dulce o Melódica de 2 octavas, de cualquier marca.`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): San Pedro · grados: Tercero

- **`Flauta dulce se recomienda (Yamaha) o pianola de viento melódica.`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Flauta dulce se sugiere marca (Yamaha, Honner o Herbal).`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`flauta dulce se sugiere Yamaha o Honner.`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`flauta dulce, preferiblemente marca (Yamaha, Honner o Herbal).`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: tipo=dulce
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`flauta, 1 resaltador`**
  - estado: `hueco_catalogo` · concepto: flauta · attrs: —
  - motivo: Entendimos flauta y el catalogo no tiene producto.
  - colegios (1×): Lista de útiles 2026 · grados: Transicion

- **`gel de manos`**
  - estado: `hueco_catalogo` · concepto: gel antibacterial · attrs: presentacion=gel
  - motivo: Entendimos gel antibacterial y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Primero

- **`Instrumentos de trazo.`**
  - estado: `hueco_catalogo` · concepto: instrumento de percusion · attrs: —
  - motivo: Entendimos instrumento de percusion y el catalogo no tiene producto.
  - colegios (1×): CACS · grados: Once

- **`jabón líquido de manos`**
  - estado: `hueco_catalogo` · concepto: jabon · attrs: presentacion=liquido
  - motivo: Entendimos jabon y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Primero

- **`Juego de enfermería`**
  - estado: `hueco_catalogo` · concepto: juego didactico · attrs: —
  - motivo: Entendimos juego didactico y el catalogo no tiene producto.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`Juego de mesa`**
  - estado: `hueco_catalogo` · concepto: juego didactico · attrs: —
  - motivo: Entendimos juego didactico y el catalogo no tiene producto.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`Juego didáctico que será asignado en la primera reunión`**
  - estado: `hueco_catalogo` · concepto: juego didactico · attrs: —
  - motivo: Entendimos juego didactico y el catalogo no tiene producto.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Muda de ropa para pintar`**
  - estado: `hueco_catalogo` · concepto: muda de ropa · attrs: —
  - motivo: Entendimos muda de ropa y el catalogo no tiene producto.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`PLANTILLA ENHEBRADO ( CUERPO HUMIANNO/ VOCALES/ NUMEROS/ FIGURAS GEOMETRICAS)`**
  - estado: `hueco_catalogo` · concepto: plantilla · attrs: —
  - motivo: Entendimos plantilla y el catalogo no tiene producto.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`regleta del mapa de Colombia`**
  - estado: `hueco_catalogo` · concepto: plantilla del mapa de colombia · attrs: —
  - motivo: Entendimos plantilla del mapa de colombia y el catalogo no tiene producto.
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`ROMPECABEZAS DE MADERA ( DE 24 A 32 PIEZAS)`**
  - estado: `hueco_catalogo` · concepto: rompecabezas · attrs: material=madera, piezas=32
  - motivo: Entendimos rompecabezas y el catalogo no tiene producto.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`ROMPECABEZAS DE MADERA ( DE 32 A 48 PIEZAS)`**
  - estado: `hueco_catalogo` · concepto: rompecabezas · attrs: material=madera, piezas=48
  - motivo: Entendimos rompecabezas y el catalogo no tiene producto.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`rompecabezas de ocho cortes.`**
  - estado: `hueco_catalogo` · concepto: rompecabezas · attrs: —
  - motivo: Entendimos rompecabezas y el catalogo no tiene producto.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin

- **`rompecabezas en madera de 15 piezas marcado.`**
  - estado: `hueco_catalogo` · concepto: rompecabezas · attrs: material=madera, piezas=15
  - motivo: Entendimos rompecabezas y el catalogo no tiene producto.
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`rompecabezas en madera de 9 piezas marcado.`**
  - estado: `hueco_catalogo` · concepto: rompecabezas · attrs: material=madera, piezas=9
  - motivo: Entendimos rompecabezas y el catalogo no tiene producto.
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`tabla para dibujo técnico formato A3 (10º y 11º).`**
  - estado: `hueco_catalogo` · concepto: tablero de dibujo · attrs: —
  - motivo: Entendimos tablero de dibujo y el catalogo no tiene producto.
  - colegios (1×): Modelia · grados: Decimo

- **`tabla para dibujo técnico formato A3.`**
  - estado: `hueco_catalogo` · concepto: tablero de dibujo · attrs: —
  - motivo: Entendimos tablero de dibujo y el catalogo no tiene producto.
  - colegios (1×): Modelia · grados: Once

- **`Tambor lúdico con baquetas.`**
  - estado: `hueco_catalogo` · concepto: instrumento de percusion · attrs: —
  - motivo: Entendimos instrumento de percusion y el catalogo no tiene producto.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Vaso pequeño de plástico`**
  - estado: `hueco_catalogo` · concepto: vaso o plato · attrs: material=plastico
  - motivo: Entendimos vaso o plato y el catalogo no tiene producto.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Vaso pequeño de plástico.`**
  - estado: `hueco_catalogo` · concepto: vaso o plato · attrs: material=plastico
  - motivo: Entendimos vaso o plato y el catalogo no tiene producto.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Vaso plástico`**
  - estado: `hueco_catalogo` · concepto: vaso o plato · attrs: material=plastico
  - motivo: Entendimos vaso o plato y el catalogo no tiene producto.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

### declarar atributo (498)

- **`Diccionario de inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (17×): Alamei, Bahía Solano, Jardín (merged), Lista textos y útiles 2021 · grados: Cuarto, Decimo, Octavo, Once, Primero, Quinto, Segundo, Sexto, Tercero

- **`block Cuadriculado tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (12×): Jardín (merged), Lista de útiles 2026 · grados: Cuarto, Decimo, Noveno, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero

- **`cuadernos de 50 hojas cuadriculados`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (12×): Jardín (merged), San José de Fontibón · grados: Decimo, Noveno, Octavo, Once, Primero, Segundo, Septimo, Sexto

- **`Cuadernos cuadriculados de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (9×): Lista de útiles 2026, Lista textos y útiles 2021, Listas de útiles 2025 ACT · grados: Decimo, Noveno, Octavo, Once, Primero, Septimo, Sexto, Transicion

- **`calculadora científica`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (8×): CACS, San José de Fontibón, San Pedro · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Calculadora científica y tabla periódica plastificada`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (8×): Alamei, Bahía Solano · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`Cuadriculado 50 hojas grande Educación Ética y en Valores Humanos`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (8×): Alamei, Bahía Solano · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Cuadriculado 50 hojas grande Química`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (8×): Alamei, Bahía Solano · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Cuadriculado de 50 hojas argollado Línea de investigación`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (8×): Alamei, Bahía Solano · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Diccionario de inglés y lista de verbos irregulares.`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (8×): Alamei, Bahía Solano · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`block cuadriculado tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (7×): CACS, Jardín (merged), Lista de útiles 2026, Lista textos y útiles 2021, Listas 2026 · grados: Decimo, Noveno, Octavo, Once, Quinto, Septimo

- **`Ferrocarril de 100 cuaderno grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (7×): Alamei, Bahía Solano · grados: Cuarto, Jardin, Segundo, Transicion

- **`Block cuadriculado tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (6×): CACS, Lista textos y útiles 2021, Listas 2026 · grados: Cuarto, Octavo, Quinto, Septimo, Sexto, Tercero

- **`Block de Dibujo Caribe Pequeño con espiral (29,8 x 22,5 cm).`**
  - estado: `abstencion` · concepto: block · attrs: tamano=29.8 x 22.5 cm
  - motivo: El renglon pide block con tamano=29.8 x 22.5 cm y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (6×): Matilde · grados: Cuarto, Primero, Quinto, Segundo, Sexto, Tercero

- **`Block Oficio Rayado (Hojas de trabajo)`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (6×): San Pedro · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`Carpeta de Liga tamaño Carta de material resistente, para llevar siempre dentro del bulto.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta
  - motivo: El renglon pide carpeta con tamano=carta y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (6×): Matilde · grados: Cuarto, Primero, Quinto, Segundo, Sexto, Tercero

- **`diccionario de inglés y francés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles-frances
  - motivo: El renglon pide diccionario con idioma=ingles-frances y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (6×): Jardín (merged) · grados: Cuarto, Noveno, Octavo, Quinto, Septimo, Sexto

- **`lápices 2H. (sugerido Faber Castell y/o Pelikan).`**
  - estado: `abstencion` · concepto: lapiz · attrs: dureza=2h
  - motivo: El renglon pide lapiz con dureza=2h y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (6×): Listas de útiles 2025 ACT · grados: Decimo, Noveno, Octavo, Once, Septimo, Sexto

- **`1 calculadora científica`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (5×): CACS · grados: Decimo, Once

- **`Block cuadriculado oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (5×): San José de Fontibón · grados: Cuarto, Primero, Quinto, Segundo, Tercero

- **`Calculadora Cinetífica.`** → *corregido:* `Calculadora Cientifica.`
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (5×): Matilde · grados: Cuarto, Quinto, Tercer Ano

- **`carpeta con gancho legajador.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Decimo, Noveno, Octavo, Septimo, Sexto

- **`carpeta tipo folder tamaño oficio.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (5×): Modelia · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`carpetas plásticas oficio con gancho`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (5×): San José de Fontibón · grados: Noveno, Octavo, Once, Septimo, Sexto

- **`Cinta de enmascarar ancha`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): Lista de útiles 2026, Lista textos y útiles 2021, Listas textos útiles 2026 · grados: Cuarto, Prejardin, Primero, Segundo, Tercero

- **`cuaderno Ferrocarril de 100 Hojas (cocido).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Cuarto, Prejardin, Quinto, Segundo, Tercero

- **`cuadernos cuadriculados de 50 hojas (Cocido).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Cuarto, Primero, Quinto, Segundo, Tercero

- **`Cuadernos cuadriculados de 50 hojas grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (5×): Lista textos y útiles 2021 · grados: Decimo, Octavo, Once, Septimo, Sexto

- **`cuadernos cuadriculados de 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`Escuadras de 45° y 60° X 32cm`**
  - estado: `abstencion` · concepto: escuadra · attrs: longitud=32 cm
  - motivo: El renglon pide escuadra con longitud=32 cm y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): Lista de útiles 2026 · grados: Decimo, Noveno, Once, Septimo, Sexto

- **`esferos de tinta negra.`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=negro
  - motivo: El renglon pide esfero con tinta=negro, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Decimo, Noveno, Octavo, Septimo, Sexto

- **`Estuche de lápices para dibujo artístico (serie H a la B)`**
  - estado: `abstencion` · concepto: lapiz · attrs: dureza=h
  - motivo: El renglon pide lapiz con dureza=h y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Ferrocarril de 100 cuaderno grande - Español Lengua Castellana`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (5×): Alamei, Bahía Solano · grados: Cuarto, Primero, Quinto, Segundo

- **`pliegos de papel Kraft café`**
  - estado: `abstencion` · concepto: papel · attrs: color=cafe, tipo=kraft
  - motivo: El renglon pide papel con tipo=kraft, color=cafe y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Regla Plástica Transparente de 30 cm (No metálica).`**
  - estado: `abstencion` · concepto: regla · attrs: longitud=30 cm, material=plastico
  - motivo: El renglon pide regla con longitud=30 cm, material=plastico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): Matilde · grados: Cuarto, Quinto, Segundo, Sexto, Tercero

- **`rollo de cinta de enmascarar grande.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (5×): Listas de útiles 2025 ACT · grados: Decimo, Noveno, Octavo, Once, Septimo

- **`Sketchbook de papel durex 50 hojas tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: hojas=50, tamano=carta
  - motivo: El renglon pide block con hojas=50, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (5×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Tabla periódica laminada tamaño carta`**
  - estado: `abstencion` · concepto: tabla periodica · attrs: tamano=carta
  - motivo: El renglon pide tabla periodica con tamano=carta y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (5×): San Pedro · grados: Decimo, Noveno, Octavo, Septimo, Sexto

- **`1 block cuadriculado tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (4×): CACS · grados: Segundo, Tercero

- **`Block de hojas blancas tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (4×): Lista textos y útiles 2021, San José de Fontibón · grados: Cuarto, Primero, Quinto, Sexto

- **`carpeta plástica tamaño oficio con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas 2026 · grados: Decimo, Noveno, Octavo, Septimo

- **`cinta de enmascarar gruesa.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas de útiles 2025 ACT · grados: Cuarto, Quinto, Segundo, Tercero

- **`cuaderno cuadriculado Cosido 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cuaderno ferrocarril de 100 hojas grande cosido`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): Lista textos y útiles 2021 · grados: Cuarto, Quinto, Segundo, Tercero

- **`cuadernos cuadriculados grandes cosidos de 50 hojas (Ética, Religión, Estadística-geometría, Democracia y Urbanidad)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): Jardín (merged) · grados: Cuarto, Quinto, Sexto, Tercero

- **`cuadernos grandes cuadriculados cosidos de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): Lista de útiles 2026 · grados: Primero, Quinto, Segundo, Tercero

- **`Cuadriculado 50 hojas grande - Educación Ética y en Valores Humanos`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): Alamei, Bahía Solano · grados: Decimo, Once, Septimo, Sexto

- **`Cuadriculado 50 hojas grande - Química`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (4×): Alamei, Bahía Solano · grados: Decimo, Once, Septimo, Sexto

- **`Esferos (rojo y negro)`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (4×): Modelia · grados: Decimo, Once, Septimo, Sexto

- **`folder tamaño carta`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta
  - motivo: El renglon pide carpeta con tamano=carta y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas 2026 · grados: Decimo, Noveno, Octavo, Septimo

- **`paquete de hojas cuadriculadas tamaño carta`**
  - estado: `abstencion` · concepto: hojas · attrs: tamano=carta
  - motivo: El renglon pide hojas con tamano=carta y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas 2026 · grados: Decimo, Noveno, Octavo, Septimo

- **`paquetes de octavos de Papel silueta.`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=octavo
  - motivo: El renglon pide papel con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas de útiles 2025 ACT · grados: Cuarto, Quinto, Segundo, Tercero

- **`pincel grueso`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=grueso
  - motivo: El renglon pide pincel con grosor=grueso y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (4×): Listas textos útiles 2026, Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`ROLLO DE CINTA DE ENMASCARAR ANCHA`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (4×): CACS, Osito de Miel · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Prejardin, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 block cuadriculado tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno 3 materias cuadriculado grande.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=3, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con rayado=cuadriculado, materias=3 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Decimo

- **`1 marcador borrable para uso del estudiante.`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=borrable, tipo=borrable
  - motivo: El renglon pide marcador con punta=borrable, tipo=borrable y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Archivador de fuelle, oficio, 13 bolsillos, tipo maleta.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=fuelle
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=fuelle y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`bitácora o Sketchbook para arte tamaño octavo, argollada. (Verificar que las hojas tengan calibre grueso, tipo cartulina, tapa dura para facilitar su trabajo y manipulación, ninguna marca específica. La bitácora puede ser armada de la siguiente manera: 15 hojas de cartulina blanca tamaño octavo 10 hojas papel bond tamaño octavo 10 hojas papel acuarela tamaño octavo)`** → *corregido:* `bitácora o Sketchbook para arte tamaño octavo, argollado. (Verificar que las hojas tengan calibre grueso, tipo cartulina, tapa dura para facilitar su trabajo y manipulación, ninguna marca específica. La bitácora puede ser armada de la siguiente madera: 15 hojas de cartulina blanca tamaño octavo 10 hojas papel bond tamaño octavo 10 hojas papel acuarela tamaño octavo)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=15, materias=1, rayado=blanco
  - motivo: El renglon pide cuaderno con hojas=15, rayado=blanco, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`block cuadriculado tamaño oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Decimo, Noveno, Once

- **`Block de hojas blancas carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`Block Oficio Carta (Hojas de trabajo)`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`Block oficio cuadriculado (Hojas de trabajo)`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`borrador miga de pan.`**
  - estado: `abstencion` · concepto: borrador · attrs: tipo=miga de pan
  - motivo: El renglon pide borrador con tipo=miga de pan y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Calculadora científica (Biología, Física y Química)`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`Calculadora científica y tabla periódica plastificada - La calculadora científica es importante porque facilita la resolución de problemas matemáticos complejos, fomenta el razonamiento lógico y ayuda a los estudiantes a comprender mejor los procesos y resultados instrumentos trabajo geométrico.`** → *corregido:* `Calculadora científica y tabla periódica plastificada - La calculadora científica es importante parque facilita la resolución de problemas matemáticos complejos, fomenta el razonamiento lógico y ayuda a los estudiantes a comprender mejor los procesos y resultados instrumentos trabajo geométrico.`
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (3×): Alamei, Bahía Solano · grados: Noveno, Octavo, Sexto

- **`CARPERTAS PLASTIFICADAS TAMAÑO OFICIO`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`carpeta de sobre (fuelle) tamaño oficio plástica.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=fuelle
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=fuelle y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Ciencias Sociales, Lengua Castellana, ERE, Filosofía, Inglés, Artística, Proyecto Interdisciplinar, Física, Química y Tecnología-Informática)`** → *corregido:* `Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Ciencias Sociales, Lengua Castellana, ERE, Filosofía, Inglés, Artistico, Proyecto Interdisciplinar, Física, Química y Tecnología-Informática)`
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`Carpeta tipo legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cartulinas en octavos: colores pasteles, blancas y neón`**
  - estado: `abstencion` · concepto: cartulina · attrs: color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`cintas de enmascarar`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS, Listas textos útiles 2026 · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`COLBON CON PICO 225 GRAMOS`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: gramaje=225 g
  - motivo: El renglon pide pegante liquido con gramaje=225 g y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`cuadernos grandes cuadriculados cosidos de 50 hojas (Geometría, Estadística, Cultura Religiosa-Ética, y Danzas).`** → *corregido:* `cuadernos grandes cuadriculados cosidos de 50 hojas (Geometría, Estadóstick, Cultura Religiosa-Ética, y Danzas).`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Noveno, Once, Septimo

- **`Cuadriculado de 50 hojas argollado - Línea de investigación`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (3×): Alamei, Bahía Solano · grados: Once, Septimo, Sexto

- **`DELANTAL PLASTICO`**
  - estado: `abstencion` · concepto: delantal · attrs: material=plastico
  - motivo: El renglon pide delantal con material=plastico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Diccionario de inglés - El diccionario de inglés es una herramienta clave para que su hijo(a) aprenda, descubra nuevas palabras y mejore cada día en el dominio del idioma.`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (3×): Alamei · grados: Cuarto, Quinto, Tercero

- **`Diccionario de inglés y lista de verbos irregulares. - El diccionario de inglés es una herramienta clave para que su hijo(a) aprenda, descubra nuevas palabras y mejore cada día en el dominio del idioma.`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (3×): Alamei, Bahía Solano · grados: Noveno, Octavo, Sexto

- **`Diccionario Escolar Inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`Diccionario Inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (3×): Lista textos y útiles 2021 · grados: Decimo, Noveno, Septimo

- **`Diccionario Inglés- inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Noveno, Octavo, Once

- **`Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera), adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y creyones de madera (no de cera). Todo identificado con el nombre del estudiante. No se aceptan portaminas.`** → *corregido:* `Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera), adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y crayones de madera (no de cera). Todo identificado con el nombre del estudiante. No se aceptan portaminas.`
  - estado: `abstencion` · concepto: cartuchera · attrs: tamano=pequeno
  - motivo: El renglon pide cartuchera con tamano=pequeno y ninguno de los 15 productos lo declara. No ofrezco otro.
  - colegios (3×): Matilde · grados: Segundo, Sexto, Tercero

- **`Lapicero Negro, Azul y de colores`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`lápiz negro triangular jumbo.`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`lápiz rojo triangular jumbo.`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Lápiz, Lapicero Negro, Azul y otros colores`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`paquete de cartulina blanca por octavos X 10 unidades`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de cartulina iris en octavos`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris, tamano=octavo
  - motivo: El renglon pide cartulina con tamano=octavo, acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Lista textos y útiles 2021 · grados: Cuarto, Primero, Segundo

- **`paquete de cartulina iris.`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris
  - motivo: El renglon pide cartulina con acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San José de Fontibón · grados: Jardin, Prejardin, Transicion

- **`Paquete de octavos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`Paquete de octavos de cartulina colores neón`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=neon, tamano=octavo
  - motivo: El renglon pide cartulina con color=neon, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`paquete de pañitos x100.`**
  - estado: `abstencion` · concepto: toallas y panitos · attrs: unidades=100
  - motivo: El renglon pide toallas y panitos con unidades=100 y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Paquete de paños húmedos x 100 und.`**
  - estado: `abstencion` · concepto: toallas y panitos · attrs: unidades=100
  - motivo: El renglon pide toallas y panitos con unidades=100 y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`paquete de papel silueta en octavos.`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=octavo
  - motivo: El renglon pide papel con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San José de Fontibón · grados: Jardin, Prejardin, Transicion

- **`PEGA STICK 22 gramos`**
  - estado: `abstencion` · concepto: pegante en barra · attrs: gramaje=22 g
  - motivo: El renglon pide pegante en barra con gramaje=22 g y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`pincel de cerdas suaves redondo, Pelo Nylon Mango de Madera # 5 o # 6`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo
  - motivo: El renglon pide pincel con forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Pincel plano N° 10`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=plano, grosor=n10
  - motivo: El renglon pide pincel con grosor=n10, forma=plano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Lista textos y útiles 2021 · grados: Decimo, Noveno, Once

- **`Protectores de acetato tamaño carta`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San José de Fontibón · grados: Decimo, Noveno, Once

- **`Regla de 15 cm`**
  - estado: `abstencion` · concepto: regla · attrs: longitud=15 cm
  - motivo: El renglon pide regla con longitud=15 cm y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): San Pedro · grados: Decimo, Noveno, Once

- **`Rollo de cinta de enmascarar de 2 cm de ancho`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`sobre de acetatos tamaño carta`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Listas 2026 · grados: Noveno, Octavo, Septimo

- **`sobre de acetatos tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (3×): Listas 2026 · grados: Noveno, Octavo, Septimo

- **`1 block de papel iris.`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 carpeta tamaño oficio con gancho legajador.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Once, Sexto

- **`1 carpeta tipo folder tamaño oficio.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Octavo

- **`1 cuaderno cuadriculado cosido 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 Cuaderno ferrocarril cosido de 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Primero

- **`1 paquete de cartulina blanca Bristol.`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 sobre de acetato grueso tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Primero

- **`1 sobre de acetato grueso tamaño oficio.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 tabla periódica Walter (grande)`**
  - estado: `abstencion` · concepto: tabla periodica · attrs: tamano=grande
  - motivo: El renglon pide tabla periodica con tamano=grande y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Decimo, Once

- **`Agenda escolar Año 2026.`**
  - estado: `abstencion` · concepto: agenda · attrs: ano=2026
  - motivo: El renglon pide agenda con ano=2026 y ninguno de los 6 productos lo declara. No ofrezco otro.
  - colegios (2×): San Pedro · grados: Octavo, Septimo

- **`Archivador de fuelle, oficio, 13 bolsillos, tipo maleta`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=fuelle
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=fuelle y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Quinto

- **`Block de hojas cuadriculado tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021 · grados: Quinto, Segundo

- **`Block de papel iris`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021, Listas 2026 · grados: Primero, Segundo

- **`block hojas blancas oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): San José de Fontibón · grados: Noveno, Octavo

- **`Carpeta legajadora tamaño oficio con gancho`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): Listas textos útiles 2026 · grados: Jardin, Prejardin

- **`carpeta tipo folder tamaño oficio (Inglés, Ciencias Sociales).`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Cuarto, Quinto

- **`carpetas legajadoras plásticas traslucidas tamaño oficio con gancho legajador. Colores: Amarillo, Azul, Rojo, Verde (Unidades de indagación PEP)`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=rojo, tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador, color=rojo y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Jardin, Transicion

- **`Cartulina paquete arte, calipso, blanco y de colores`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Jardín (merged) · grados: Jardin, Transicion

- **`cinta de enmascarar de 24 mm.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cinta delgada de enmascarar (1 cm)`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`cinta enmascarar ancha`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Cuarto, Quinto

- **`Cintas de enmascarar anchas`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021, Listas textos útiles 2026 · grados: Quinto, Transicion

- **`cuaderno 5 materias cuadriculado grande.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=5, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con rayado=cuadriculado, materias=5 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Noveno, Octavo

- **`cuaderno cosido grande de 50 hojas cuadriculado cuadros grandes. (matemáticas)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Jardin, Transicion

- **`cuaderno cuadriculado cosido de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS, Listas 2026 · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`cuaderno ferrocarril tipo B, cosido de 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): San José de Fontibón · grados: Jardin, Prejardin

- **`Cuaderno Grande de 50 hojas cuadriculado (Química)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): San Pedro · grados: Decimo, Noveno

- **`Cuadernos cuadriculados de 50 hojas grande cosido`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021 · grados: Cuarto, Quinto

- **`cuadernos cuadriculados grandes cosidos de 50 hojas (Ética, Religión, Estadística-geometría y Urbanidad)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Jardín (merged) · grados: Primero, Segundo

- **`cuadernos de 50 hojas cuadriculados cosidos`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): San José de Fontibón · grados: Cuarto, Tercero

- **`cuadernos grandes cosidos cuadriculados de 50 hojas (Cultura Religiosa, Ética y Exp. Corporal).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Cuarto, Jardin, Primero, Segundo, Tercero, Transicion

- **`Cuadriculado 50 hojas grande - Ciencias Políticas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande - Economía`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande - Filosofía`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande argollado - Física`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande argollado Física`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Bahía Solano · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande Ciencias Políticas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Bahía Solano · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande Economía`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Bahía Solano · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande Filosofía`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Bahía Solano · grados: Decimo, Once

- **`Cuadriculado 50 hojas grande Geometría y estadística`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei, Bahía Solano · grados: Noveno

- **`Esferos (rojo y negro).`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Noveno, Octavo

- **`ESTUCHE DE PLASTILINA EN BLOQUE X 4`**
  - estado: `abstencion` · concepto: plastilina · attrs: unidades=4
  - motivo: El renglon pide plastilina con unidades=4 y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Ferrocarril 100 hojas grande - Lectoescritura y aprestamiento`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Cuarto, Quinto

- **`Ferrocarril de 50 cuaderno grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (2×): Alamei · grados: Jardin, Transicion

- **`Folder legajador tamaño carta con sus hojas de repuesto cuadriculadas. (Campo PCT)`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=carta, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (2×): Listas 2026 · grados: Cuarto, Quinto

- **`Frasco de colbón grande`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: presentacion=frasco
  - motivo: El renglon pide pegante liquido con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021 · grados: Primero, Tercero

- **`frasco de vinilo blanco y negro`**
  - estado: `abstencion` · concepto: vinilo · attrs: presentacion=frasco
  - motivo: El renglon pide vinilo con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`fundas de acetato tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Listas 2026 · grados: Cuarto, Quinto

- **`Kit de 12 pinceles sintéticos (delgados, planos redondos y abanico)`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=abanico
  - motivo: El renglon pide pincel con forma=abanico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera, adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y creyones de madera (no de cera). Todo identificado con el nombre del estudiante. No se aceptan portaminas.`** → *corregido:* `Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera, adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y crayones de madera (no de cera). Todo identificado con el nombre del estudiante. No se aceptan portaminas.`
  - estado: `abstencion` · concepto: cartuchera · attrs: tamano=pequeno
  - motivo: El renglon pide cartuchera con tamano=pequeno y ninguno de los 15 productos lo declara. No ofrezco otro.
  - colegios (2×): Matilde · grados: Cuarto, Quinto

- **`Lápiz 2H-6B`**
  - estado: `abstencion` · concepto: lapiz · attrs: dureza=2h
  - motivo: El renglon pide lapiz con dureza=2h y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`marcador borrable para uso del estudiante`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=borrable, tipo=borrable
  - motivo: El renglon pide marcador con punta=borrable, tipo=borrable y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Octavos de papel pergamino`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=octavo
  - motivo: El renglon pide papel con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Papel iris octavos.`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=octavo, tipo=iris
  - motivo: El renglon pide papel con tipo=iris, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquete de hojas iris`**
  - estado: `abstencion` · concepto: hojas · attrs: tipo=iris
  - motivo: El renglon pide hojas con tipo=iris y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`paquetes de foamy liso tamaño octavo colores surtidos`**
  - estado: `abstencion` · concepto: foamy · attrs: color=surtido, tamano=octavo
  - motivo: El renglon pide foamy con color=surtido, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`paquetes de octavos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Jardin, Transicion

- **`paquetes de octavos de cartulina fluorescente colores surtidos`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=surtido, tamano=octavo
  - motivo: El renglon pide cartulina con color=surtido, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`pegante en barra.`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: presentacion=barra
  - motivo: El renglon pide pegante liquido con presentacion=barra y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Modelia · grados: Jardin, Noveno, Primero, Segundo, Tercero, Transicion

- **`pincel de cerdas suaves plano, Pelo Nylon Mango de Madera # 5 o # 6`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=plano
  - motivo: El renglon pide pincel con forma=plano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`pincel delgado`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=delgado
  - motivo: El renglon pide pincel con grosor=delgado y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026, Listas textos útiles 2026 · grados: Cuarto, Prejardin

- **`pincel delgado.`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=delgado
  - motivo: El renglon pide pincel con grosor=delgado y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): San José de Fontibón · grados: Jardin, Transicion

- **`Pincel grueso y 1 delgado`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=grueso
  - motivo: El renglon pide pincel con grosor=grueso y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Listas textos útiles 2026 · grados: Jardin, Transicion

- **`Pinceles de punta plana y redonda`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo
  - motivo: El renglon pide pincel con forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`pliego de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=pliego
  - motivo: El renglon pide cartulina con color=blanco, tamano=pliego, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Primero, Segundo

- **`pliego de cartulina negra`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=negro, tamano=pliego
  - motivo: El renglon pide cartulina con color=negro, tamano=pliego, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Jardin, Tercero

- **`pliego de papel crepe, 1 pliego de papel seda cualquier color`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=pliego
  - motivo: El renglon pide papel con tamano=pliego y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Primero, Tercero

- **`pliego de papel kraft`**
  - estado: `abstencion` · concepto: papel · attrs: color=kraft, tamano=pliego, tipo=kraft
  - motivo: El renglon pide papel con tipo=kraft, tamano=pliego, color=kraft y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Primero, Tercero

- **`Pliegos de papel kraff`** → *corregido:* `Pliegos de papel kraft`
  - estado: `abstencion` · concepto: papel · attrs: color=kraft, tipo=kraft
  - motivo: El renglon pide papel con tipo=kraft, color=kraft y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista textos y útiles 2021 · grados: Quinto, Segundo

- **`pliegos de papel Kraft`**
  - estado: `abstencion` · concepto: papel · attrs: color=kraft, tipo=kraft
  - motivo: El renglon pide papel con tipo=kraft, color=kraft y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): Lista de útiles 2026 · grados: Prejardin, Tercero

- **`rollo de cinta de enmascarar gruesa.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): San José de Fontibón · grados: Jardin, Prejardin

- **`Sketch book tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Sketch book tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`sobre de acetato grueso tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 bitácora o Sketchbook para arte tamaño octavo, argollada. (Verificar que las hojas tengan calibre grueso, tipo cartulina, tapa dura para facilitar su trabajo y manipulación, ninguna marca específica. La bitácora puede ser armada de la siguiente manera: 15 hojas de cartulina blanca tamaño octavo 10 hojas papel bond tamaño octavo 10 hojas papel acuarela tamaño octavo)`** → *corregido:* `1 bitácora o Sketchbook para arte tamaño octavo, argollado. (Verificar que las hojas tengan calibre grueso, tipo cartulina, tapa dura para facilitar su trabajo y manipulación, ninguna marca específica. La bitácora puede ser armada de la siguiente madera: 15 hojas de cartulina blanca tamaño octavo 10 hojas papel bond tamaño octavo 10 hojas papel acuarela tamaño octavo)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=15, materias=1, rayado=blanco
  - motivo: El renglon pide cuaderno con hojas=15, rayado=blanco, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 block cuadriculado carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto

- **`1 block de cartulinas iris`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Tercero

- **`1 block de hojas blancas (Tamaño carta).`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 Block de hojas blancas tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto

- **`1 block de hojas blancas tamaño oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Segundo

- **`1 block de hojas cuadriculadas tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Sexto

- **`1 block de hojas iris tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Tercero

- **`1 block de papel milimetrado tamaño carta, regla, 1 regla de 30 cm`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=milimetrado
  - motivo: El renglon pide block con tipo=milimetrado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Decimo

- **`1 block iris tamaño carta de colores`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 block rayado tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto

- **`1 block rayado tamaño oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 calculadora científica.`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Decimo

- **`1 carpeta plástica tamaño oficio con gancho legajador.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Once

- **`1 carpeta tipo folder tamaño oficio (Inglés, Ciencias Naturales, Ciencias Sociales).`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Primero

- **`1 cinta de enmascarar de 24 mm.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno 5 materias cuadriculado grande.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=5, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con rayado=cuadriculado, materias=5 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Once

- **`1 cuaderno cuadriculado cosido de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno cuadriculado, cosido 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno cuadriculado, cosido 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno ferrocarril cosido 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Primero

- **`1 cuaderno ferrocarril cosido de 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Segundo

- **`1 cuaderno ferrocarril de 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Primero

- **`1 cuaderno ferrocarril de 100 hojas grande (cosido). Castellano`** → *corregido:* `1 cuaderno ferrocarril de 100 hojas grande (cosido). Castellana`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 cuaderno ferrocarril de 100 hojas grandes (cosido). Inglés`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 cuaderno ferrocarril de 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Segundo

- **`1 cuaderno ferrocarril de 50 hojas grande (cosido). Ciencias naturales`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 cuaderno ferrocarril de 50 hojas grande (cosido). Ciencias sociales`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 cuaderno ferrocarril de 50 hojas grande (cosido). Ética-Religión`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 cuaderno ferrocarril grande cosido 80 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=80, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=80, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Primero

- **`1 cuaderno grande cosido ferrocarril de 100 hojas (Lengua Castellana).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Primero

- **`1 cuaderno grande ferrocarril de 100 hojas cosido.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Tercero

- **`1 cuaderno pequeño cosido cuadriculado de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Primero

- **`1 escuadra de 20 cm.- 45 grados, 1 regla de 30 cm., un compás`**
  - estado: `abstencion` · concepto: escuadra · attrs: longitud=20 cm
  - motivo: El renglon pide escuadra con longitud=20 cm y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto

- **`1 folder tamaño carta.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta
  - motivo: El renglon pide carpeta con tamano=carta y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Once

- **`1 lápiz negro triangular`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Primero

- **`1 lápiz rojo triangular`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Primero

- **`1 marcador borrable para uso del estudiante`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=borrable, tipo=borrable
  - motivo: El renglon pide marcador con punta=borrable, tipo=borrable y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto

- **`1 paquete de fomi en octavos de colores.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 paquete de octavos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 rollo de cinta de enmascarar ancha y 1 rollo de cinta transparente ancha.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`1 rollo de cinta de enmascarar ancha.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 rollo de cinta de enmascarar de 1cm`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 sobre de acetatos tamaño carta.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Once

- **`1. Pincel de cerdas suaves redondo, Pelo Nylon Mango de Madera # 5 o # 6`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo
  - motivo: El renglon pide pincel con forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`10 hojas de papel durex tamaño octavo`**
  - estado: `abstencion` · concepto: hojas · attrs: tamano=octavo
  - motivo: El renglon pide hojas con tamano=octavo y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 blocks de hojas blancas tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Tercero

- **`2 hojas de acetato tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2 pliegos de papel Kraft café`**
  - estado: `abstencion` · concepto: papel · attrs: color=cafe, tipo=kraft
  - motivo: El renglon pide papel con tipo=kraft, color=cafe y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2. cuartos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2. Paquete de cartulina blanca por octavos X 10 unidades`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`3 cuadernos grandes cosidos cuadriculados de 50 hojas (Cultura Religiosa, Ética y Danzas).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Quinto

- **`3 cuadernos grandes cosidos cuadriculados de 50 hojas (Cultura Religiosa, Ética y Exp. Corporal).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Primero

- **`5 cuadernos grandes cuadriculados cosidos de 50 hojas (Geometría, Estadística, Cultura Religiosa-Ética, y Danzas).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Octavo

- **`6 hojas Papel acuarela tamaño octavo`**
  - estado: `abstencion` · concepto: hojas · attrs: tamano=octavo
  - motivo: El renglon pide hojas con tamano=octavo y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Acetatos tamaño carta.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Acuarelas en tubo,`**
  - estado: `abstencion` · concepto: acuarela · attrs: presentacion=tubo
  - motivo: El renglon pide acuarela con presentacion=tubo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Agenda escolar Año 2026`**
  - estado: `abstencion` · concepto: agenda · attrs: ano=2026
  - motivo: El renglon pide agenda con ano=2026 y ninguno de los 6 productos lo declara. No ofrezco otro.
  - colegios (1×): San Pedro · grados: Sexto

- **`Block cartulina iris tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`block cuadriculados oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`block de hojas blancas tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`Block de hojas blancas tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Quinto

- **`Block de hojas cuadriculadas tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`block de hojas cuadriculado tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`block de hojas iris tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Block de hojas iris tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`block de hojas rayada tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`block de hojas tamaño carta cuadriculada`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Noveno

- **`Block de papel iris carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`Block de papel iris para plegado 20x20`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Block de papel iris tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`block de papel iris.`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`block DIN A4 con formato tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`block DIN A4 con formato, tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`block DIN A4 cuadriculado`**
  - estado: `abstencion` · concepto: block · attrs: tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`block hojas blancas tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`block hojas cuadriculadas oficio.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`block hojas cuadriculadas para portafolio carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Block hojas Iris. Tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`block hojas oficio cuadriculado.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Once

- **`block iris`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Block iris para plegado 20x20.`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`block iris tamaño carta de colores`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`Block iris tamaño carta.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`block oficio cuadriculado.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=cuadriculado
  - motivo: El renglon pide block con tipo=cuadriculado, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`block oficio hojas blancas`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Block oficio papel iris`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Primero

- **`block oficio papel iris colores`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`block oficio papel iris colores.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Block papel iris`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Quinto

- **`Block papel iris de 20 x 20`**
  - estado: `abstencion` · concepto: block · attrs: tipo=iris
  - motivo: El renglon pide block con tipo=iris y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`Block papel iris oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Quinto

- **`block papel iris tamaño carta`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`block papel iris tamaño carta , 1 pliego papel periódico`**
  - estado: `abstencion` · concepto: block · attrs: tamano=pliego, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=pliego y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`Block papel iris tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`block papel mantequilla tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`Block rayado tamaño oficio`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Quinto

- **`Block tamaño carta a rayas`**
  - estado: `abstencion` · concepto: block · attrs: tamano=carta
  - motivo: El renglon pide block con tamano=carta y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Segundo

- **`Block Tamaño Oficio de Papel Iris`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`block Tamaño Oficio de Papel Iris.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio, tipo=iris
  - motivo: El renglon pide block con tipo=iris, tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`block Tamaño Oficio de Papellris.`**
  - estado: `abstencion` · concepto: block · attrs: tamano=oficio
  - motivo: El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`bolsa de pompones de algodón`**
  - estado: `abstencion` · concepto: algodon · attrs: presentacion=bolsa
  - motivo: El renglon pide algodon con presentacion=bolsa y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin

- **`Borrador miga de pan, tajalápiz, colores, lápiz y plumones`**
  - estado: `abstencion` · concepto: borrador · attrs: tipo=miga de pan
  - motivo: El renglon pide borrador con tipo=miga de pan y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Borrador miga de pan, tajalápiz, lápiz, plumones`**
  - estado: `abstencion` · concepto: borrador · attrs: tipo=miga de pan
  - motivo: El renglon pide borrador con tipo=miga de pan y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Once

- **`caja de colores grande triangular de 12 unidades`**
  - estado: `abstencion` · concepto: colores · attrs: forma=triangular, unidades=12
  - motivo: El renglon pide colores con unidades=12, forma=triangular y ninguno de los 4 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Jardin

- **`calculadora científica.`**
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Noveno

- **`Carpeta 3 aros tamaño carta, con 10 acetatos`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Once

- **`carpeta con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`Carpeta de acetato tamaño oficio con gancho legajador y cauchos de cierre.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`carpeta de cartón tamaño carta con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=carta, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`carpeta de cartón tamaño oficio con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`carpeta plástica carta con gancho`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta
  - motivo: El renglon pide carpeta con tamano=carta y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`carpeta plástica con gancho legajador color azul.`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=azul, tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador, color=azul y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Transicion

- **`Carpeta plástica oficio - hojas cuadriculadas Educación física`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Octavo

- **`Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ethics, Inglés, Artística, Proyecto Interdisciplinar, Global Perspective, Física-Química y Tecnología-Informática)`** → *corregido:* `Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ethics, Inglés, Artistico, Proyecto Interdisciplinar, Global Perspective, Física-Química y Tecnología-Informática)`
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San Pedro · grados: Sexto

- **`Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ética, Inglés, Artística, Proyecto Interdisciplinar, Física-Química y Tecnología-Informática)`** → *corregido:* `Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ética, Inglés, Artistico, Proyecto Interdisciplinar, Física-Química y Tecnología-Informática)`
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San Pedro · grados: Octavo

- **`Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ética, Inglés, Artística, Proyecto Interdisciplinar, Global Perspective, Física-Química y Tecnología-Informática)`** → *corregido:* `Carpeta plástica oficio con gancho plástico: (Matemáticas, Biología, Sociales, Lengua C, ERE, Ética, Inglés, Artistico, Proyecto Interdisciplinar, Global Perspective, Física-Química y Tecnología-Informática)`
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San Pedro · grados: Septimo

- **`carpeta plástica ROJA con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=rojo, tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador, color=rojo y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`carpeta plástica tamaño octavo tipo sobre`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=octavo
  - motivo: El renglon pide carpeta con tamano=octavo y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`carpeta plástica tamaño oficio con gancho legajador.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`carpeta Plástica tipo sobre tamaño oficio`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`carpeta Plástica tipo sobre tamaño oficio.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`carpeta plastificada color amarillo oficio`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=amarillo, tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio, color=amarillo y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`carpeta plastificada oficio azul`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=azul, tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio, color=azul y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`Carpeta plastificada tamaño oficio`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`carpeta plastificada tamaño oficio con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Carpeta tamaño oficio con caucho`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`Carpeta tamaño oficio con caucho sin gancho`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Carpeta tamaño oficio con gancho de cartón.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`carpeta tamaño oficio plastificada, con gancho legajador (NO estilo sobre).`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Prejardin

- **`carpeta tipo folder tamaño oficio (Inglés y Ciencias Sociales).`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Tercero

- **`carpeta tipo folder tamaño oficio (Inglés, Ciencias Naturales, Ciencias Sociales).`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`carpetas plástica tamaño octavo tipo sobre`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=octavo
  - motivo: El renglon pide carpeta con tamano=octavo y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`carpetas plásticas NEGRAS con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=negro, tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador, color=negro y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`carpetas plásticas oficio con gancho (una verde oscuro)`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=verde, tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio, color=verde y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`carpetas plásticas transparentes con legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`carpetas plásticas VERDES con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=verde, tipo=legajador
  - motivo: El renglon pide carpeta con tipo=legajador, color=verde y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`carpetas plásticas, con legajador tamaño oficio`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`carpetas tamaño oficio con gancho legajador`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio, tipo=legajador
  - motivo: El renglon pide carpeta con tamano=oficio, tipo=legajador y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`cinta de enmascarar`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`cinta de enmascarar de 24 mm`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cinta de enmascarar grande`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Colbón universal de 225 g`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: gramaje=225 g
  - motivo: El renglon pide pegante liquido con gramaje=225 g y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Cuaderno 5 materias`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=5
  - motivo: El renglon pide cuaderno con materias=5 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Decimo

- **`Cuaderno 5 materias preferiblemente empastado.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=5
  - motivo: El renglon pide cuaderno con materias=5 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Once

- **`cuaderno cosido grande de 50 hojas cuadros grandes para preescolar. (Lecto - Escritura)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Prejardin

- **`cuaderno cosido grande de 50 hojas ferrocarril. (lecto escritura)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Jardin

- **`cuaderno Cosido Rengloncitos C Ferrocarril de 100 hojas. Duralink.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`Cuaderno cuadriculado cuadro pequeños, 50 hojas grande cosido. Forro en acetato verde.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`cuaderno cuadriculado de 50 hojas (pueden continuar con el cuaderno de IYC y EXC del año anterior)`** → *corregido:* `cuaderno cuadriculado de 50 hojas (puedan continuar con el cuaderno de IYC y EXC del año anterior)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`cuaderno cuadriculado de 50 hojas (se sugiere usar el del año pasado de IYC).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`cuaderno cuadriculado de 50 hojas grande (cosido). (Dimensión Afectiva - ERE)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`cuaderno cuadriculado de 50 hojas grande (cosido). (Dimensión Cognitiva - Ciencias naturales)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`cuaderno cuadriculado de 50 hojas grande (cosido). (Dimensión Cognitiva - Ciencias sociales)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`cuaderno cuadriculado de 50 hojas para el campo IYC.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Primero

- **`cuaderno cuadriculado de 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`cuaderno de 50 hojas cuadriculado`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Cuaderno ferrocarril (tamaño de renglón normal) de 100 hojas, grande, cosido (Forro amarillo) para Comunicación y Lectura Crítica.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Cuaderno ferrocarril 100 hojas cosido, sin espacio de muestra, 12 renglones a espacio normal y con forro en acetato amarillo.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`cuaderno ferrocarril 50 hojas (cocido)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`cuaderno ferrocarril cosido 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`Cuaderno ferrocarril de 100 hojas grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`cuaderno Ferrocarril de 100 hojas Grande, cosido Duralink`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`cuaderno Ferrocarril de 100 hojas únicamente (Tamaño Grande)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Prejardin

- **`cuaderno ferrocarril de 50 hojas grande (cosido). (Dimensión Comunicativa - Castellano)`** → *corregido:* `cuaderno ferrocarril de 50 hojas grande (cosido). (Dimensión Comunicativa - Castellana)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=50, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`cuaderno ferrocarril grande cosido 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Primero

- **`cuaderno ferrocarril grande de 100 hojas cosido (Castellano)`** → *corregido:* `cuaderno ferrocarril grande de 100 hojas cosido (Castellana)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Primero

- **`cuaderno ferrocarril grande de 100 hojas cosidos (Castellano)`** → *corregido:* `cuaderno ferrocarril grande de 100 hojas cosidos (Castellana)`
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Segundo

- **`cuaderno Ferrocarril grande, con renglones enumerados de 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Transicion

- **`cuaderno ferrocarril, cosido de 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`cuaderno grande Ferrocarril cosido de 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Jardin

- **`cuaderno grande ferrocarril cosido de 100 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`Cuaderno grande ferrocarril sin recuadro de dibujo de 100 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`Cuaderno grande ferrocarril sin recuadro de dibujo de 80 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=80, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=80, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin

- **`Cuaderno grande rayado sin recuadro de dibujo de 80 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=80, materias=1, rayado=rayado
  - motivo: El renglon pide cuaderno con hojas=80, rayado=rayado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`CUADERNO MI PRIMER CUADERNO MITAD CON RECUADRO MITAD HOJA EN BLANCO ( OSITO DE MIEL) 100 HOJAS`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=blanco
  - motivo: El renglon pide cuaderno con hojas=100, rayado=blanco, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cuaderno pequeño cosido cuadriculado de 50 hojas del año anterior.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Cuadernos cuadriculados de 50 hojas grades cosidos`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`Cuadernos cuadriculados de 50 hojas grandes`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Noveno

- **`Cuadernos cuadriculados de 50 hojas grandes cosidos`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`cuadernos cuadriculados grandes, cosidos de 50 hojas.`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`cuadernos de 50 hojas cuadriculados cosidos grandes`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`cuadernos de cuadricula grande de 100 Hojas (cocidos).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=cuadricula grande
  - motivo: El renglon pide cuaderno con hojas=100, rayado=cuadricula grande, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`Cuadernos Ferrocarril de 100 Hojas (cocido)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`cuadernos Ferrocarril de 100 Hojas (cocido).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`cuadernos grandes cosidos cuadriculados de 50 hojas (Cultura Religiosa, Ética y Danzas).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Tercero

- **`cuadernos grandes cuadriculados cosido de 50 hojas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`cuadernos grandes cuadriculados cosidos de 50 hojas (Geometría, Estadística, Cultura Religiosa, Ética, Danzas).`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Sexto

- **`cuadernos grandes cuadriculados cosidos de 50 hojas (Geometría, Estadística, Cultura Religiosa-Ética, y Danzas)`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Decimo

- **`Cuadriculado 50 hojas grande - Tecnología Informática`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Once

- **`Cuadriculado 50 hojas grande - Tecnología Informática, con todas las paginas enumeradas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Decimo

- **`Cuadriculado 50 hojas grande Danzas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Sexto

- **`Cuadriculado 50 hojas grande Tecnología Informática`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Once

- **`Cuadriculado 50 hojas grande Tecnología Informática, con todas las paginas enumeradas`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Decimo

- **`Cuadriculado de 50 hojas argollado Teatro`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=50, materias=1, rayado=cuadriculado
  - motivo: El renglon pide cuaderno con hojas=50, rayado=cuadriculado, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Octavo

- **`Cuarto periodo: -Cada estudiante elige una obra de la lista prescrita para leer en clase`**
  - estado: `abstencion` · concepto: cartulina · attrs: tamano=cuarto
  - motivo: El renglon pide cartulina con tamano=cuarto y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`cuartos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`delantal manga larga en tela antifluido una talla más grande de la acostumbrada. (Para pintar)`**
  - estado: `abstencion` · concepto: delantal · attrs: material=tela
  - motivo: El renglon pide delantal con material=tela y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Diccionario Inglés - Inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Septimo

- **`Diccionario Inglés – inglés`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Decimo

- **`El diccionario de inglés es una herramienta clave para que su hijo(a) aprenda, descubra nuevas palabras y mejore cada día en el dominio del idioma.`**
  - estado: `abstencion` · concepto: diccionario · attrs: idioma=ingles
  - motivo: El renglon pide diccionario con idioma=ingles y ninguno de los 7 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Octavo

- **`Escuadras de 30 y 60 cm`**
  - estado: `abstencion` · concepto: escuadra · attrs: longitud=60 cm
  - motivo: El renglon pide escuadra con longitud=60 cm y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Escuadras de 45º y 60º X 32cm`**
  - estado: `abstencion` · concepto: escuadra · attrs: longitud=32 cm
  - motivo: El renglon pide escuadra con longitud=32 cm y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Octavo

- **`esferos de mina negra.`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=negro
  - motivo: El renglon pide esfero con tinta=negro, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`Esferos negro y rojo`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Cuarto

- **`esferos negros y rojos`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`Esferos Rojo y negro`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Modelia · grados: Quinto

- **`esferos rojos y negros`**
  - estado: `abstencion` · concepto: esfero · attrs: color=negro, tinta=surtido
  - motivo: El renglon pide esfero con tinta=surtido, color=negro y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`ESTUCHE DE PLASTILINA EN BLOQUE X 6`**
  - estado: `abstencion` · concepto: plastilina · attrs: unidades=6
  - motivo: El renglon pide plastilina con unidades=6 y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`ESTUCHE X 2 LAPIZ ROJO TRIANGULAR`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`ESTUCHE X 3 LAPICES N. 2 HB mi primer lápiz TRIANGULAR`**
  - estado: `abstencion` · concepto: lapiz · attrs: dureza=hb, forma=triangular
  - motivo: El renglon pide lapiz con dureza=hb, forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`ESTUCHE X 3 LAPIZ ROJO TRIANGULAR`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Ferrocarril 100 hojas - Lecto escritura y aprestamiento`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Primero

- **`Ferrocarril 100 hojas grande - Lectoescritura`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Tercero

- **`Ferrocarril cuaderno grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Tercero

- **`Ferrocarril cuaderno grande - Español Lengua Castellana`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Tercero

- **`Ferrocarril de 100 cuaderno grande - Dimensión Biológico Ambiental`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Ferrocarril de 100 cuaderno grande - Dimensión Comunicativa`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Ferrocarril de 100 cuaderno grande - Inglés`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Ferrocarril de 100 cuaderno grande, Español Lengua Castellana`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Quinto

- **`Ferrocarril de 50 cuaderno grande - Dimensión Ética y valores`**
  - estado: `abstencion` · concepto: cuaderno · attrs: materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`Ferrocarril normal 100 hojas grande`**
  - estado: `abstencion` · concepto: cuaderno · attrs: hojas=100, materias=1, rayado=ferrocarril
  - motivo: El renglon pide cuaderno con hojas=100, rayado=ferrocarril, materias=1 y ninguno de los 17 productos lo declara. No ofrezco otro.
  - colegios (1×): Alamei · grados: Segundo

- **`folder tamaño carta.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=carta
  - motivo: El renglon pide carpeta con tamano=carta y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Frasco de colbón`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: presentacion=frasco
  - motivo: El renglon pide pegante liquido con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`frasco de pintura escolar de 100 ml de color fluorescente con tapa dosificadora.`**
  - estado: `abstencion` · concepto: pintura · attrs: tipo=escolar
  - motivo: El renglon pide pintura con tipo=escolar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`frasco de vinilo de 125 gramos color azul.`**
  - estado: `abstencion` · concepto: vinilo · attrs: presentacion=frasco
  - motivo: El renglon pide vinilo con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Primero

- **`frasco de vinilo de 125 gramos color blanco`**
  - estado: `abstencion` · concepto: vinilo · attrs: presentacion=frasco
  - motivo: El renglon pide vinilo con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`frasco de vinilo de 125 gramos color negro`**
  - estado: `abstencion` · concepto: vinilo · attrs: presentacion=frasco
  - motivo: El renglon pide vinilo con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`frasco de vinilo de 125 gramos de color amarillo.`**
  - estado: `abstencion` · concepto: vinilo · attrs: presentacion=frasco
  - motivo: El renglon pide vinilo con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`Frasco grande de pegante`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: presentacion=frasco
  - motivo: El renglon pide pegante liquido con presentacion=frasco y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`frasco mediano de silicona líquida 100ml.`**
  - estado: `abstencion` · concepto: silicona · attrs: grosor=mediano, presentacion=liquido
  - motivo: El renglon pide silicona con presentacion=liquido, grosor=mediano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`hojas Durex tamaño octavo`**
  - estado: `abstencion` · concepto: hojas · attrs: tamano=octavo
  - motivo: El renglon pide hojas con tamano=octavo y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Hojas iris`**
  - estado: `abstencion` · concepto: hojas · attrs: tipo=iris
  - motivo: El renglon pide hojas con tipo=iris y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Kit de 12 pinceles sintéticos, delgados, planos redondos y abanico.`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=abanico
  - motivo: El renglon pide pincel con forma=abanico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Kit de 12 pinceles sintéticos. (delgados, planos redondos y abanico etc.)`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=abanico
  - motivo: El renglon pide pincel con forma=abanico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Kit de 12 pinceles sintéticos. (delgados,planos redondos y abanico etc.)`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=abanico
  - motivo: El renglon pide pincel con forma=abanico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera, adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y creyones de madera (no de cera). Todo identificado con el nombre del estudiante. Se aceptan portaminas.`** → *corregido:* `Koala para ser usado como cartuchera (no se aceptará ningún otro tipo de cartuchera, adaptado a la medida de la cintura del estudiante (estando sentado) y que contenga en todo momento: suficientes lápices y bicolores, regla no metálica de 15 cm para subrayar, sacapuntas con depósito grande y tapa de rosca, goma de borrar Nata grande, tijera punta roma, pega de barrita pequeña y crayones de madera (no de cera). Todo identificado con el nombre del estudiante. Se aceptan portaminas.`
  - estado: `abstencion` · concepto: cartuchera · attrs: tamano=pequeno
  - motivo: El renglon pide cartuchera con tamano=pequeno y ninguno de los 15 productos lo declara. No ofrezco otro.
  - colegios (1×): Matilde · grados: Primero

- **`La calculadora científica es importante porque facilita la resolución de problemas matemáticos complejos, fomenta el razonamiento lógico y ayuda a los estudiantes a comprender mejor los procesos y resultados instrumentos trabajo geométrico.`** → *corregido:* `La calculadora científica es importante parque facilita la resolución de problemas matemáticos complejos, fomenta el razonamiento lógico y ayuda a los estudiantes a comprender mejor los procesos y resultados instrumentos trabajo geométrico.`
  - estado: `abstencion` · concepto: calculadora · attrs: tipo=cientifica
  - motivo: El renglon pide calculadora con tipo=cientifica y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (1×): Bahía Solano · grados: Octavo

- **`lápiz Negro grueso triangular y 1 delgado triangular`**
  - estado: `abstencion` · concepto: lapiz · attrs: forma=triangular
  - motivo: El renglon pide lapiz con forma=triangular y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Prejardin

- **`maleta con capacidad para llevar una carpeta tamaño oficio. Para uso diario.`**
  - estado: `abstencion` · concepto: carpeta · attrs: tamano=oficio
  - motivo: El renglon pide carpeta con tamano=oficio y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`marcador negro grueso permanente`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=permanente, tipo=permanente
  - motivo: El renglon pide marcador con punta=permanente, tipo=permanente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Marcador negro permanente. Cartulina negra en octavos. (3 ⅛)`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=permanente, tipo=permanente
  - motivo: El renglon pide marcador con punta=permanente, tipo=permanente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Marcador permanente`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=permanente, tipo=permanente
  - motivo: El renglon pide marcador con punta=permanente, tipo=permanente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`marcador permanente negro.`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=permanente, tipo=permanente
  - motivo: El renglon pide marcador con punta=permanente, tipo=permanente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`marcadores permanente.`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=permanente, tipo=permanente
  - motivo: El renglon pide marcador con punta=permanente, tipo=permanente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`Metro de Papel Contac Transparente. (Sin identificar)`**
  - estado: `abstencion` · concepto: papel · attrs: tipo=transparente
  - motivo: El renglon pide papel con tipo=transparente y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Matilde · grados: Tercero

- **`Muda de ropa completa (marcada), 1 Pincel #10`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=n10
  - motivo: El renglon pide pincel con grosor=n10 y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Prejardin

- **`octavos de foami escarchado`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Octavos de fomy escarchado`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`paquete cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`paquete cartulina iris`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris
  - motivo: El renglon pide cartulina con acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`paquete cartulina iris, 1 paquete de cartulina Bristol`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris
  - motivo: El renglon pide cartulina con acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`paquete de bajalenguas x50`**
  - estado: `abstencion` · concepto: palitos · attrs: unidades=50
  - motivo: El renglon pide palitos con unidades=50 y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`paquete de bolas de algodón de colores`** → *corregido:* `paquete de bolsa de algodón de colores`
  - estado: `abstencion` · concepto: algodon · attrs: presentacion=bolsa
  - motivo: El renglon pide algodon con presentacion=bolsa y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Paquete de cartulina por 1/8 color blanco`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Paquete de foamy por octavos.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`paquete de fomi en octavos escarchado.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`paquete de fomi en octavos surtido.`**
  - estado: `abstencion` · concepto: foamy · attrs: color=surtido, tamano=octavo
  - motivo: El renglon pide foamy con color=surtido, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`paquete de fomi en octavos.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`paquete de Fomi por octavos de colores.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`paquete de hojas cuadriculadas tamaño carta.`**
  - estado: `abstencion` · concepto: hojas · attrs: tamano=carta
  - motivo: El renglon pide hojas con tamano=carta y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Paquete de octavos de cartulina de color blanco`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`paquete de octavos de cartulina iris.`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris, tamano=octavo
  - motivo: El renglon pide cartulina con tamano=octavo, acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`Paquete de pañitos húmedos por 100 unidades.`**
  - estado: `abstencion` · concepto: toallas y panitos · attrs: unidades=100
  - motivo: El renglon pide toallas y panitos con unidades=100 y ninguno de los 2 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`paquete pequeño de ojos móviles decorativos`**
  - estado: `abstencion` · concepto: ojos moviles · attrs: tamano=pequeno
  - motivo: El renglon pide ojos moviles con tamano=pequeno y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Paquetes de cartulina iris en octavos`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris, tamano=octavo
  - motivo: El renglon pide cartulina con tamano=octavo, acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Quinto

- **`paquetes de foami escarchado tamaño octavo colores surtidos`**
  - estado: `abstencion` · concepto: foamy · attrs: color=surtido, tamano=octavo
  - motivo: El renglon pide foamy con color=surtido, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`paquetes de foami liso tamaño octavo colores surtidos`**
  - estado: `abstencion` · concepto: foamy · attrs: color=surtido, tamano=octavo
  - motivo: El renglon pide foamy con color=surtido, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`paquetes de foamy escarchado tamaño octavo colores surtidos`**
  - estado: `abstencion` · concepto: foamy · attrs: color=surtido, tamano=octavo
  - motivo: El renglon pide foamy con color=surtido, tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`Paquetes de Fomi en Octavos`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Jardin, Preescolar, Primaria

- **`paquetes de octavos de cartulina blancas`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`paquetes de octavos de cartulina de color blanco.`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco, tamano=octavo
  - motivo: El renglon pide cartulina con color=blanco, tamano=octavo, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`paquetes de octavos de cartulina Iris`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris, tamano=octavo
  - motivo: El renglon pide cartulina con tamano=octavo, acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`paquetes de octavos de cartulina iris surtidos`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=iris, color=surtido, tamano=octavo
  - motivo: El renglon pide cartulina con color=surtido, tamano=octavo, acabado=iris y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`paquetes de octavos de Papel silueta`**
  - estado: `abstencion` · concepto: papel · attrs: tamano=octavo
  - motivo: El renglon pide papel con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`paquetes de octavos de Papelsilueta.`**
  - estado: `abstencion` · concepto: foamy · attrs: tamano=octavo
  - motivo: El renglon pide foamy con tamano=octavo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`paquetes de papel silueta colores surtidos`**
  - estado: `abstencion` · concepto: papel · attrs: color=surtido
  - motivo: El renglon pide papel con color=surtido y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`pegante en barra 125 gr`**
  - estado: `abstencion` · concepto: pegante en barra · attrs: gramaje=125 g
  - motivo: El renglon pide pegante en barra con gramaje=125 g y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Primero

- **`pincel grueso (redondo o plano)`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo, grosor=grueso
  - motivo: El renglon pide pincel con grosor=grueso, forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`pincel Grueso y 1 Pincel Delgado.`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=grueso
  - motivo: El renglon pide pincel con grosor=grueso y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`pincel grueso.`**
  - estado: `abstencion` · concepto: pincel · attrs: grosor=grueso
  - motivo: El renglon pide pincel con grosor=grueso y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`pincel plano # 10`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=plano
  - motivo: El renglon pide pincel con forma=plano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Pincel plano # 2.`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=plano
  - motivo: El renglon pide pincel con forma=plano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`pincel Redondo`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo
  - motivo: El renglon pide pincel con forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`pincel redondo #3.`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo, grosor=n3
  - motivo: El renglon pide pincel con grosor=n3, forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`Pincel redondo N° 4`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo, grosor=n4
  - motivo: El renglon pide pincel con grosor=n4, forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Septimo

- **`Pincel redondo N° 8`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo, grosor=n8
  - motivo: El renglon pide pincel con grosor=n8, forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Sexto

- **`Pincel redondo N° 9`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=redondo, grosor=n9
  - motivo: El renglon pide pincel con grosor=n9, forma=redondo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista textos y útiles 2021 · grados: Octavo

- **`Plano pelo de Camello`**
  - estado: `abstencion` · concepto: pincel · attrs: forma=plano
  - motivo: El renglon pide pincel con forma=plano y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`pliegos de cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Transicion

- **`pliegos de papel Cartulina blanca`**
  - estado: `abstencion` · concepto: cartulina · attrs: acabado=cartulina, color=blanco
  - motivo: El renglon pide cartulina con color=blanco, acabado=cartulina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`pliegos de papel crepe 1 naranja, 1 morado, 1 verde`**
  - estado: `abstencion` · concepto: papel · attrs: color=verde
  - motivo: El renglon pide papel con color=verde y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Jardin

- **`pliegos de papel crepe colores surtidos`**
  - estado: `abstencion` · concepto: papel · attrs: color=surtido
  - motivo: El renglon pide papel con color=surtido y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`pliegos de papel seda 1 amarillo, 1 azul, 1 rojo.`**
  - estado: `abstencion` · concepto: papel · attrs: color=rojo
  - motivo: El renglon pide papel con color=rojo y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Prejardin

- **`pliegos de papel seda colores surtido`**
  - estado: `abstencion` · concepto: papel · attrs: color=surtido
  - motivo: El renglon pide papel con color=surtido y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Transicion

- **`pliegos de papel seda colores surtidos`**
  - estado: `abstencion` · concepto: papel · attrs: color=surtido
  - motivo: El renglon pide papel con color=surtido y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Jardin

- **`Portafolio Blanco`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=blanco
  - motivo: El renglon pide carpeta con color=blanco y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`portafolio Blanco 2.5”-3"`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=blanco
  - motivo: El renglon pide carpeta con color=blanco y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`portafolio Blanco en buen estado`**
  - estado: `abstencion` · concepto: carpeta · attrs: color=blanco
  - motivo: El renglon pide carpeta con color=blanco y ninguno de los 12 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Once

- **`Protector para ropa (delantal plástico)`**
  - estado: `abstencion` · concepto: delantal · attrs: material=plastico
  - motivo: El renglon pide delantal con material=plastico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`regla plástica de 30 cm.`**
  - estado: `abstencion` · concepto: regla · attrs: longitud=30 cm, material=plastico
  - motivo: El renglon pide regla con longitud=30 cm, material=plastico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`regla plástica no flexible (15 cm)`**
  - estado: `abstencion` · concepto: regla · attrs: longitud=15 cm, material=plastico
  - motivo: El renglon pide regla con longitud=15 cm, material=plastico y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Primero

- **`resma de papel blanco tamaño oficio.`**
  - estado: `abstencion` · concepto: resma · attrs: tamano=oficio
  - motivo: El renglon pide resma con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`Resma de papel Oficio`**
  - estado: `abstencion` · concepto: resma · attrs: tamano=oficio
  - motivo: El renglon pide resma con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Jardin, Parvulos, Prejardin, Transicion

- **`resma de papel tamaño oficio`**
  - estado: `abstencion` · concepto: resma · attrs: tamano=oficio
  - motivo: El renglon pide resma con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Septimo

- **`resma de papel tamaño oficio.`**
  - estado: `abstencion` · concepto: resma · attrs: tamano=oficio
  - motivo: El renglon pide resma con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Resma tamaño oficio`**
  - estado: `abstencion` · concepto: resma · attrs: tamano=oficio
  - motivo: El renglon pide resma con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`rollo de cinta ancha de enmascarar o transparente.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`rollo de cinta de enmascarar delgada.`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`rollo de cinta de enmascarar grande`**
  - estado: `abstencion` · concepto: cinta adhesiva · attrs: tipo=enmascarar
  - motivo: El renglon pide cinta adhesiva con tipo=enmascarar y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`sharpie punta fina`**
  - estado: `abstencion` · concepto: marcador · attrs: punta=punta fina, tipo=punta fina
  - motivo: El renglon pide marcador con punta=punta fina, tipo=punta fina y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`sobre de acetato tamaño carta`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`sobre de acetato tamaño oficio`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`sobre de acetatos tamaño carta.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=carta
  - motivo: El renglon pide acetato con tamano=carta y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`sobre de acetatos tamaño oficio.`**
  - estado: `abstencion` · concepto: acetato · attrs: tamano=oficio
  - motivo: El renglon pide acetato con tamano=oficio y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Tabla periódica Walter (grande)`**
  - estado: `abstencion` · concepto: tabla periodica · attrs: tamano=grande
  - motivo: El renglon pide tabla periodica con tamano=grande y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Noveno

- **`Tabla periódica Walter (grande).`**
  - estado: `abstencion` · concepto: tabla periodica · attrs: tamano=grande
  - motivo: El renglon pide tabla periodica con tamano=grande y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Septimo

- **`tajalápiz doble orificio lápiz grueso y delgado con depósito`**
  - estado: `abstencion` · concepto: tajalapiz · attrs: deposito=True, orificios=2
  - motivo: El renglon pide tajalapiz con deposito=True, orificios=2 y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Tarro de colbón pegante universal 225 gramos.`**
  - estado: `abstencion` · concepto: pegante liquido · attrs: gramaje=225 g, presentacion=tarro
  - motivo: El renglon pide pegante liquido con presentacion=tarro, gramaje=225 g y ninguno de los 3 productos lo declara. No ofrezco otro.
  - colegios (1×): Listas 2026 · grados: Jardin

- **`tinta china negra`**
  - estado: `abstencion` · concepto: tinta china · attrs: color=negro
  - motivo: El renglon pide tinta china con color=negro y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Tinta china negra.`**
  - estado: `abstencion` · concepto: tinta china · attrs: color=negro
  - motivo: El renglon pide tinta china con color=negro y ninguno de los 1 productos lo declara. No ofrezco otro.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

### descartar (5)

- **`Crema dental`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`CREMA DENTAL ( Si su hijo utiliza alguna en especial por favor entregar la adecuada)`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Cartilla Nacho`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (2×): Alamei · grados: Jardin, Transicion

- **`Cartilla Nacho - Fortalecer su proceso de lecto escritura.`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Bahía Solano · grados: Transicion

- **`CARTILLA NACHO LIBRO INICIAL DE LECTURA / SUSAETA`**
  - estado: `sin_match` · concepto: — · attrs: —
  - motivo: No reconocemos que pide este renglon.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

### libro por revisar a mano (380)

- **`PROYECTO READING COMPREHENSION DIGITAL PLATFORM EDITORIAL: B-Readers`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (11×): Jardín (merged) · grados: Cuarto, Decimo, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero

- **`SISTEMA UNO I: EDITORIAL: Santillana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (10×): Jardín (merged) · grados: Cuarto, Decimo, Noveno, Octavo, Once, Primero, Quinto, Septimo, Sexto, Tercero

- **`Atlas Universal y de Colombia (Sugerido: Planeta Azul. Editorial Migema)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (8×): Listas 2026 · grados: Cuarto, Decimo, Noveno, Octavo, Once, Quinto, Septimo, Tercero

- **`Diccionario inglés español – español inglés. Se sugiere cualquiera de las siguientes editoriales (Cambridge, Oxford, Merriam Webster, Longman o Macmillan).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (5×): Modelia · grados: Noveno, Octavo, Once, Septimo, Sexto

- **`Editorial: McGraw Hill.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (5×): Matilde · grados: Cuarto, Primer Ano, Quinto, Segundo, Tercer Ano

- **`Plan Lector: Cada periodo se indicará el título del libro que se necesita.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (5×): San Pedro · grados: Cuarto, Primero, Quinto, Segundo, Tercero

- **`Cuaderno pentagramado Batuta Mágica, ED. Sugerida: Big book publishing.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (4×): Modelia · grados: Decimo, Noveno, Once, Septimo

- **`Diccionario español. Editorial Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (4×): Listas 2026 · grados: Decimo, Noveno, Octavo, Septimo

- **`FRANCÉS (2026-2027) Jeu de Mots Plus A1 1 EDITORIAL: Vinces Vives`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (4×): Jardín (merged) · grados: Octavo, Quinto, Septimo, Sexto

- **`Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (4×): CACS · grados: Decimo, Octavo, Once, Septimo

- **`Diccionario inglés español - español inglés. Se sugiere cualquiera de las siguientes editoriales (Cambridge, Oxford, Merriam Webster, Longman o Macmillan).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (3×): Modelia · grados: Cuarto, Quinto, Tercero

- **`PLAN LECTOR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (3×): Lista de útiles 2026 · grados: Decimo, Octavo, Sexto

- **`Cuaderno pentagramado DO RE MI. Ed. Big book publishing (sugerido).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): Modelia · grados: Cuarto, Tercero

- **`Diccionario español. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): Listas 2026 · grados: Once, Sexto

- **`Editorial: Santillana Conexus.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): Matilde · grados: Primer Ano, Segundo

- **`Mader.Sylvia S. Windelspecht Michael. Biology. fourteenth edition. Ed. Mc Graw Hill Education`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): CACS · grados: Septimo, Sexto

- **`Plan Lector: Traer un cuento de su preferencia de pasta dura.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): Modelia · grados: Jardin, Prejardin

- **`Química, general, orgánica y biológica. Timberlake – Ed. Pearson (7° a- 11°).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): Modelia · grados: Octavo, Septimo

- **`Texto Mader.Sylvia S. Windelspecht Michael. Biology. Thirteenth edition. Ed. Mc Graw Hill Education`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1 cuaderno pentagramado Batuta Mágica, ED. Sugerida: Big book publishing.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`1 cuaderno pentagramado DO RE MI. Ed. Big book publishing (sugerido).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`1984 - George Orwell. Editorial Atenea`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`84 días sin pescar: El viejo y el mar. Autor: Ernest Hemingway. Novela. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Sexto

- **`97 horas de la tierra a la luna. Autor: Julio Verne. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Septimo

- **`Abejitas. Mis Primeras Lecturas. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Primero

- **`Alpha Mathematics On-Level Practice Book. 2. Editorial Libros y Libros. Para compra en línea aparece: Col. Agustiniano Ciudad Salitre Paquete Grado Primero. (ver en NOTA para mayor información)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Primero

- **`Antología del cuento Colombiano. Autor: Recopilación de autores. Editorial Atenea. (primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Sexto

- **`Antología del cuento Latinoamericano. Autor: Recopilación de autores. Ed. Atenea. (segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Aquiles en Tik Tok - Eduardo Infante. Editorial planeta (Ariel).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Aquiles en TikTok: El camino a la virtud. Autor: Eduardo Infante. Editorial: Planeta.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Once

- **`Así es la vida, Lili. - Valérie Dayre. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Septimo

- **`Atchú y otros cuentos. Autor: Irene Vasco. Ed. Enlace (primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`Ciencias Naturales 8 Savia Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Ciencias Naturales 9 Savia Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`CIENCIAS NATURALES PRO XXI 7 EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Septimo

- **`CIENCIAS NATURALES PRO XXI 8 EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`CIENCIAS NATURALES PRO XXI 9 EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Noveno

- **`Ciencias Naturales Savia 6. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`Ciencias Naturales Savia 7. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Competencias y habilidades del siglo XXI.4. Editorial Libros y Libros`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

- **`Competencias y habilidades del siglo XXI.5. Editorial Libros y Libros`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Quinto

- **`Competencias y habilidades del siglo XXI.6. Editorial Libros y Libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`Competencias y habilidades del siglo XXI.7. Editorial Libros y Libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Septimo

- **`Comprensión de Lectura y escritura ENLACES A (Avanzado), Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Primero

- **`Comprensión de Lectura y escritura ENLACES B. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`Comprensión de Lectura y escritura ENLACES C. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Comprensión de Lectura y escritura ENLACES D. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Cuarto

- **`Comprensión de Lectura y escritura ENLACES E. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Quinto

- **`Comprensión de Lectura y escritura ENLACES F. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Sexto

- **`Comprensión de Lectura y escritura ENLACES G. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Septimo

- **`Comprensión de Lectura y escritura ENLACES H. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Octavo

- **`Comprensión de Lectura y escritura ENLACES I. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Noveno

- **`Comprensión de Lectura y escritura ENLACES J. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Decimo

- **`Comprensión de Lectura y escritura ENLACES K. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Once

- **`Comprensión lectora y Plan lector virtual Lengua Castellana RAZ- PLUS`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

- **`Comunicativa: Programa letras texto ELFO Editorial Herramientas y gestión.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Crimen y castigo Fiodor Dostoyevsky. Editorial Atenea`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`Crossover 1 plus (student + reader) + work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Septimo

- **`Crossover 2 plus (student + reader) + work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Octavo

- **`Crossover 3 plus (student + reader) +work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Noveno

- **`Crossover Higher 1 (student + reader) + work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Decimo

- **`Crossover Higher 2 (student + reader) + work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Once

- **`Crossover intro (student + reader) + work book. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Sexto

- **`Cuaderno pentagramado Batuta Mágica, Ed. Big book publishing (sugerido).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Sexto

- **`Cuaderno pentagramado DO RE MI ED. Big book publishing (sugerido).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Cuaderno pentagramado DO RE MI, Ed. Big book publishing (sugerido).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Quinto

- **`cuadernos cosidos grandes de 50 hojas ferrocarril. (lecto y plan lector)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Transicion

- **`Cuentos contados después de la guerra. Autores: Fernando Cely Herrán. Ed. Atenea. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`Cuentos desde el anexo Ana Frank Autor: Ana Frank. Editorial Atenea. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Septimo

- **`De Taquito antología de cuentos futboleros, Diego F. Barros. Editorial Planeta.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

- **`Don Quijote de la Mancha. Autor: Miguel de Cervantes Saavedra. Ed Enlace. (primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Tercero

- **`Donde surgen las sombras. - David Lozano Garbala. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Once

- **`Dulce María y Ernestina. Autora: Ana Alcolea. Torre Azul. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Quinto

- **`Editorial: Actualidad. Serie Eficaz.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Primer Ano

- **`El abuelo rojo. - Isaías Romero Pacheco. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Septimo

- **`El conde de Montecristo (Novela Grafica). Autora: Alejandro Dumas. Ed. Enlace.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`El diario de Ana Frank . Autora: Ana Frank. Ed. Atenea.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`El gran juego. - Carlo Frabetti. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Decimo

- **`El libro de inglés Gateway to the world b1 student's book student's book Editorial Macmillan Education`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`El libro de inglés Gateway to the world b2 student's book. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`El libro de ingles Gateway to the world b2+. Work book Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`El mensajero de Agartha 5. Autor: Mario Mendoza. Editorial: Planeta`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Noveno

- **`El mensajero de Agartha 6. Autor: Mario Mendoza. Editorial: Planeta`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`El mensajero de Agartha 6: Metempsicosis.Mario Mendoza. Editorial Planeta.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`El mundo de los muchos. Autor: Diego Acevedo. Ed. Atenea.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`El origen del Yurupari. Autor: Ermanno Stradelli. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Septimo

- **`El pajarito soplón Autor: Rocío Parra. Ed. Enlace. (tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`El Plan Termita. Autora: María Fernanda Heredia. Torre Azul. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`El príncipe - Nicolás Maquiavelo, Editorial Atenea.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`El robo real que nunca fue. Un caso para detectives con alas. John Fitzgerald Torres. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Quinto

- **`El secreto de Adrián Autor: Rubén Martínez Santana Editorial Enlace. (tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Sexto

- **`El túnel. Autor: Ernesto Sábato. Editorial Planeta`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Noveno

- **`Enciclopedia Didáctica 1. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Primero

- **`Enciclopedia Didáctica 2. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Segundo

- **`Enciclopedia Didáctica 3. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Tercero

- **`Enciclopedia Didáctica 4. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Cuarto

- **`Enciclopedia Didáctica 5. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Quinto

- **`Enciclopedia Didáctica 6. Editorial Santillana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Sexto

- **`ENFOQUE MATEMATICAS 10 EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`English: FERRIS WHEEL 1 Activity book AND Student´s book 1. Editorial Macmillan education`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Entre amigos C Lenguaje (Cuaderno letra Script, editorial Norma)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Transicion

- **`Eskoria. - Alfredo Gómez Cerdá - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Once

- **`Español: español para ti A Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`Español: español para ti B Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`Español: español para ti C Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`EXPRESATE CIENCIAS SOCIALES 1 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`EXPRESATE CIENCIAS SOCIALES 3 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Tercero

- **`EXPRESATE CIENCIAS SOCIALES 4 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Cuarto

- **`EXPRESATE CIENCIAS SOCIALES 5 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Quinto

- **`EXPRESATE CIENCIAS SOCIALES 6 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`EXPRESATE CIENCIAS SOCIALES 7 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Septimo

- **`EXPRESATE CIENCIAS SOCIALES 8 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`EXPRESATE CIENCIAS SOCIALES 9 EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Noveno

- **`Expresiones técnicas A Ed. A & P ediciones`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Quinto

- **`Expresiones Técnicas B - Editorial A & P ediciones.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Sexto

- **`Expresiones Técnicas C - Editorial A & P ediciones.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Septimo

- **`Expresiones Técnicas D - Editorial A & P ediciones.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`Expresiones Técnicas E - Editorial A & P ediciones.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`FÍSICA Y QUIMICA COMPETENCIAS CIENTIFICAS 10 EDITORIAL SANTILLANA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`FÍSICA Y QUIMICA COMPETENCIAS CIENTIFICAS 11 EDITORIAL SANTILLANA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`Física. Wilson, Buffa, Lou. Sexta edición. Editorial Pearson. *`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Decimo

- **`Física. Wilson, Buffa, Lou. Sexta edición. Editorial Pearson. * (Es el mismo de 8° a 11°)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Once

- **`Física. Wilson, Buffa, Lou. Sexta edición. Editorial Pearson. * (Es el mismo de grado 8° a 11°)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`Flores blancas para papá. - Beatriz Helena Robledo. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Octavo

- **`Flores sobre el agua. Autor: John Fitzgerald Torres. Editorial: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`FRANCÉS (2026-2027) Exploits 1 EDITORIAL: Vinces Vives`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Noveno

- **`Fundamentos de Física. Autor Chris Vuille - Serway`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`Fundamentos de Física. Autor Chris Vuille - Serway (7°-11°)- Editorial Cengage.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`Fundamentos de Física. Autor Chris Vuille – Serway (7°-11°) - Editorial Cengage`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Septimo

- **`Fundamentos de Física. Autor Chris Vuille – Serway (7°-11°)- Editorial Cengage`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`Fundamentos de Física. Autor Chris Vuille – Serway (7º-11º)- Editorial Cengage.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Gabriel García Márquez, un genio de muchos rostros. Orlando Oliveros. Editorial Algar.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Once

- **`GATEWAY TO THE WORLD A1 + STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`GATEWAY TO THE WORLD A2 STUDENT'S BOOK. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`GATEWAY TO THE WORLD A2 STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Septimo

- **`GATEWAY TO THE WORLD B1 STUDENT'S BOOK. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Septimo

- **`GATEWAY TO THE WORLD B1 STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`GATEWAY TO THE WORLD B1+ STUDENT'S BOOK. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`GATEWAY TO THE WORLD B1+ STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Noveno

- **`GATEWAY TO THE WORLD B2 STUDENT'S BOOK. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Noveno

- **`GATEWAY TO THE WORLD B2 STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`GATEWAY TO THE WORLD B2+ STUDENTS BOOK WITH STUDENTS APP AND DIGITAL STUDENTS BOOK EDITORIAL MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`GATEWAY TO THE WORLD B2+. WORKBOOK. Editorial Macmillan Education.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Decimo

- **`Go- Getters student's book + Activity Book 1. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Primero

- **`Go- Getters student's book + Activity Book 2. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Segundo

- **`Go- Getters student's book + Activity Book 3. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Tercero

- **`Go- Getters student's book + Activity Book 4. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`Go- Getters student's book + Activity Book 5. Ed. University of Dayton publishing`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Quinto

- **`Grecia para todos. Autor: Carlos García Gual. Editorial Planeta Lector`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Septimo

- **`Inglés: English for you A Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`Inglés: English for you B Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`Inglés: English for you C Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`INGLÉS: Preschool Fly Higher 3 Student's Book + Resoaurce Book EDITORIAL: Richmond`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`Inglés: TRAILS 1 STUDENT BOOK - WORK BOOK ED. DAYTON`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Primero

- **`Ingles: TRAILS 2 STUDENT BOOK - WORK BOOK ED. DAYTON`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`Inglés: TRAILS 3 STUDENT BOOK - WORK BOOK ED. DAYTON`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Inglés: TRAILS 4 STUDENT BOOK - WORK BOOK ED. DAYTON`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`Inglés: TRAILS 5 STUDENT BOOK - WORK BOOK ED. DAYTON`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`KIT COMPRENDER EXPRES@TE A (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`KIT COMPRENDER EXPRES@TE B (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Segundo

- **`KIT COMPRENDER EXPRES@TE C (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Tercero

- **`KIT COMPRENDER EXPRES@TE D (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Cuarto

- **`KIT COMPRENDER EXPRES@TE E (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Quinto

- **`KIT COMPRENDER EXPRES@TE F (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`KIT COMPRENDER EXPRES@TE G (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Septimo

- **`KIT COMPRENDER EXPRES@TE H (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`KIT COMPRENDER EXPRES@TE I (lenguaje, comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Noveno

- **`KIT COMPRENDER EXPRES@TE J (comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`KIT COMPRENDER EXPRES@TE K (comprensión lectora + PIN PLAN LECTOR INGLES Y ESPAÑOL) EDITORIAL EDUCAR`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`KIT EUREKA (ENFOQUE MATEMATICAS 6 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`KIT EUREKA (ENFOQUE MATEMATICAS 7 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Septimo

- **`KIT EUREKA (ENFOQUE MATEMATICAS 8 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`KIT EUREKA (ENFOQUE MATEMATICAS 9 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Noveno

- **`KIT EUREKA (TALLER MATEMATICO PLAN + 1 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`KIT EUREKA (TALLER MATEMATICO PLAN + 2 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Segundo

- **`KIT EUREKA (TALLER MATEMATICO PLAN + 4 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Cuarto

- **`KIT EUREKA (TALLER MATEMATICO PLAN + 5 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Quinto

- **`KIT EUREKA (TALLER MATEMATICO PLAN +3 Y CARTILLA MATEMATICA FINANCIERA) EDITORIAL EUREKA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Tercero

- **`La alegría de querer. Autor: Jairo Aníbal Niño. Editorial Panamericana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Sexto

- **`La casa sonámbula. Autor: Arcamis Quintero. Ed Enlace. (segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Tercero

- **`La creación de un monstruo Frankensteïn. Autor: Mar Shelley. Editorial Enlace. (Tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Septimo

- **`La doctora Cantimplora. Autor: Guillermo Quijano Rueda. Editorial: Atenea. (Segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Quinto

- **`La fuente de los héroes Autor: Homero. Editorial Enlace. (Segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Septimo

- **`La metamorfosis y otros cuentos. Autor: Franz Kafka. Ed. Atenea. (Segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`La rebelión de las ratas. Autor: Fernando Soto Aparicio`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`La tortuga, el muchacho y el escritor. Autor: Albeiro Echavarría. Editorial: Enlace. (Segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Cuarto

- **`La venganza de Nicolás Bravo., Gonzalo España., Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Noveno

- **`LEARNING ENGLISH A/ EDITORIAL ENCUENTRO.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`LEARNING ENGLISH B / EDITORIAL ENCUENTRO.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`LEARNING ENGLISH C / EDITORIAL ENCUENTRO.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`LEARNING LANDS STUDENTS BOOK LEVEL 1 + WORBOOK ED. MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`LEARNING LANDS STUDENTS BOOK LEVEL 3 + WORBOOK ED. MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Tercero

- **`LEARNING LANDS STUDENTS BOOK LEVEL 4 + WORBOOK ED. MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Cuarto

- **`LEARNING LANDS STUDENTS BOOK LEVEL 5 + WORBOOK ED. MACMILLAN`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Quinto

- **`Lectura autónoma: cada estudiante elige una obra de su preferencia de un autor colombiano para leer en clase`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`Lectura autónoma: cada estudiante elige una obra de su preferencia para leer en clase de un autor Latinoamericano`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Noveno

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector "C" EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Tercero

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector "H" EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Octavo

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector "I" EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Noveno

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “A” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Primero

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “B” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Segundo

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “D” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Cuarto

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “E” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Quinto

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “F” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Sexto

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “G” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Septimo

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “J” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Decimo

- **`LECTURA CRITICA- PLAN LECTOR Enlace Lector “K” EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Once

- **`Lecturas Girasol 2. Nueva Edición. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Segundo

- **`Lecturas Girasol 3. Nueva Edición. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Tercero

- **`Lecturas Girasol 4. Nueva Edición. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Cuarto

- **`Lecturas Girasol 5. Nueva Edición. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Quinto

- **`Lecturas Girasol 6. Nueva Edición. Editorial Girasol.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Sexto

- **`Lenguaje 10 Savia Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Lenguaje 11 Savia Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Once

- **`Lenguaje 7 Savia. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Lenguaje 9 Savia. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`Lenguaje Savia 6. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`Lenguaje Savia 8. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Level Up 1 Student´s Book and Workbook. Ed. Cambridge.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`Level Up 2 Student´s Book and Workbook. Ed. Cambridge.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Leyendas y mitos de mi patria Autor: Laura María García. Editorial: Enlace. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Cuarto

- **`Libro Dynamic spaces Elementary 1A student book and tools box Editorial Dinámico pedagogía y diseño. Para el proceso de compra se darán las directrices al iniciar 2026.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Jardin

- **`Libro Dynamic spaces Elementary 1B student book and tools box Editorial Dinámico pedagogía y diseño.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Transicion

- **`Libro Literacy Readers, Scholastic Ed. Título adquirido en el 2025, como parte del proyecto de lectura.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Transicion

- **`LIBRO RAYITAS A / EDITORIAL MUNDO DE NIÑOS.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`LIBRO RAYITAS B / EDITORIAL MUNDO DE NIÑOS.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`LIBRO RAYITAS C / EDITORIAL MUNDO DE NIÑOS.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`Libro: Mi universo lector 2. Editorial: Grupo educativo calidad.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Segundo

- **`Libros: Lectura Multidimensional Método 84H. Diccionario físico cualquier edición. Las claves de la Argumentación. Anthony Weston. Ed. Planeta Lector. (Adquirido en el grado octavo para dar continuidad al proceso). Plan Lector: La noche en que Frankenstein leyó el Quijote. Santiago Posteguillo. Editorial Planeta. Montes de María. Daniel Ángel. Editorial Algar. Cien años de soledad. Autor Gabriel García Márquez, Cualquier edición. Libro de Lectura Libre Guiada: El estudiante debe elegir un libro, teniendo en cuenta las pautas del docente (literatura y autores sugeridos)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Noveno

- **`Lili, libertad. - Gonzalo Moure Trenor. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Octavo

- **`Literacy Readers, Scholastic Ed. Al iniciar el primer periodo académico, se asignará a cada niño un título de la colección, el cual será comunicado a través de Classroom.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Jardin

- **`Los hijos del viento. Autor: Fernando Soto Aparicio. Ed. Atenea. (Tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Lucia, una holandesa en América. Autora: Soledad Acosta de Samper. Editorial: Enlace. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Mader. Sylvia S. Windelspecht Michael. Biology. Thirteenth edition. Ed. Mc Graw Hill Education (Es el mismo de grado 8° a 11°)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Noveno

- **`Mader.Sylvia S. Windelspecht Michael. Biology. Thirteenth edition. Ed. Mc Graw Hill Education (Este es el mismo texto del año anterior)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`Maju iCambia esa cara larga! Autor: Cecilia Curbelo. Ed Enlace (primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`María. Novela gráfica. Autor: Jorge Isaacs adaptado por Óscar Adan y Book and Play. Editorial: Planeta`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`Martín Malapata o el ladrón imposible Autor: Alfredo Alfonso Hincapié. Ed. Atenea (tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Tercero

- **`Matemáticas: Expedición matemática A editorial encuentro`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Prejardin

- **`Matemáticas: Matemáticas para ti A Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Prejardin

- **`Matemáticas: Matemáticas para ti B Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Jardin

- **`Matemáticas: Matemáticas para ti C Ed. B&B`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Transicion

- **`Matemáticas: Proyecto saber. Ser y hacer matemáticas 1. Ed. Santillana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Primero

- **`Matemáticas: Proyecto saber. Ser y hacer matemáticas 2. Ed. Santillana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`Matemáticas: Proyecto saber. Ser y hacer matemáticas 3. Ed. Santillana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Math in Focus Student Edition 2A y 2B. Ed. Marshall Cavendish.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`Math in Focus Student Edition 3A y 3B. Ed. Marshall Cavendish.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Math in Focus Student Edition 4A y 4B. Ed. Marshall Cavendish.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Tercero

- **`Math in Focus Student Edition 5A y 5B. Ed. Marshall Cavendish.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Cuarto

- **`Math: MATHS FOR YOU 1 B&B Editorial.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Prejardin

- **`Meditaciones Metafísicas - Rene Descartes. Editorial Panamericana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Decimo

- **`Medusa Zombie. Autor: Juan Carlos Mojica. Editorial: Atenea. (segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Sexto

- **`Método lúdico de comprensión lectora 84H - Ed. Juegos Lee 2`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`Método lúdico de comprensión lectora 84H - Ed. Juegos Lee 3`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`Método lúdico de comprensión lectora 84H - Ed. Juegos Lee 7`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Septimo

- **`Método lúdico de comprensión lectora 84H - Ed. Juegos Lee 8`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Octavo

- **`Método lúdico de comprensión lectora 84H - Ed. Juegos Lee 9`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Noveno

- **`Método lúdico de comprensión lectora 84H – Ed. Juegos Lee 10`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Decimo

- **`Método lúdico de comprensión lectora 84H – Ed. Juegos Lee 11`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Once

- **`Método lúdico de comprensión lectora 84H – Ed. Juegos Lee 4`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`Método lúdico de comprensión lectora 84H – Ed. Juegos Lee 5`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`Método lúdico de comprensión lectora 84H – Ed. Juegos Lee 6`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Sexto

- **`MI CUADERNO DE TAREAS LETRAS. EDITORIAL SEMILLAS CREATIVAS`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`MI CUADERNO DE TAREAS NUMEROS. EDITORIAL SEMILLAS CREATIVAS`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Mi universo lector 3. Editorial: Grupo educativo calidad.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Tercero

- **`Módulos de aventuras de aprendizaje Cantorín Comunicativa: Programa letras textos GAMMA Y DECODIFICA Editorial Herramientas y gestión.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`Módulos de aventuras de aprendizaje Cantorín English: FERRIS WHEEL 3 Activity book AND Student´s book 3. Editorial Macmillan education`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`Módulos de aventuras de aprendizaje Cantorín Math: MATHS FOR YOU 3 B&B Editorial.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas textos útiles 2026 · grados: Transicion

- **`Once relatos mitológicos y uno más de propina. Autor: Tony Llacay y Monserrat Viladevall. Editorial Planeta Lector`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Orgullo de cacique y otros cuentos latinoamericanos. Autor: Elena Liliana Luchetti. Editorial Planeta Lector`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Septimo

- **`Phenomenal Science 1 Student Book. Ed. Pearson`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`Phenomenal Science 3 - Student Book. Ed. Pearson.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Tercero

- **`Phenomenal Science 4 Student Book. Ed. Pearson.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Cuarto

- **`PLAN LECTOR - PRIMER SEMESTRE: La casa sonámbula (Aramis Quintero)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`PLAN LECTOR - PRIMER SEMESTRE: Puñales en la niebla (Danilo Ramírez) con cartilla`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Noveno

- **`PLAN LECTOR - SEGUNDO SEMESTRE: El último deseo (Enrique Pérez)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`PLAN LECTOR - SEGUNDO SEMESTRE: Esta ciudad entre nosotros (Francisco Rengifo) con cartilla`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Noveno

- **`PLAN LECTOR PRIMER SEMESTRE: Los cuentos de Cata (Graciela Boticiaria)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`PLAN LECTOR SEGUNDO SEMESTRE: La gran barca (Irene Vasco)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista de útiles 2026 · grados: Segundo

- **`Plan lector virtual Inglés RAZ-PLUS`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

- **`Plan lector virtual RAZ- PLUS inglés y lengua castellana, administrada en Colombia por QUOVIX`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Transicion

- **`Plan Lector: Al iniciar el primer periodo académico se asignarán los textos uno por cada periodo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Primero

- **`PLAN LECTOR: Danny, el campeón del mundo. Roald Dahl. Editorial Loqueleo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`PLAN LECTOR: El pan de la guerra. Editorial. Deborah Ellis. Ediciones Castillo`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`Plan Lector: Leo Leo editorial avión de papel.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Transicion

- **`PLAN LECTOR: Libro de Lectura Libre Guiada: El estudiante debe elegir un libro, teniendo en cuenta las pautas del docente (literatura y autores sugeridos)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`PLAN LECTOR: Los secretos de Hafiz Mustafá - Francisco Leal Quevedo. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Septimo

- **`Plan Lector: Meditaciones Gato Aurelio- Editorial planeta, Humanos Púrpura - Fredy Pedraza Cuevas - Novela Autopublicada, En los pliegues del aire - Daniel Hernández Chambers - Editorial Algar., Libro de Lectura Libre Guiada: El estudiante debe elegir un libro, teniendo en cuenta las pautas del docente (literatura y autores sugeridos)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Decimo

- **`PLAN LECTOR: Mi hermano el genio. Rodrigo Muñoz Avia. Editorial Edebé.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Sexto

- **`Plan Lector: Orgullo y Prejuicio. Autor: Jane Austen. Editorial: Enlace.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Once

- **`Puñales en la niebla. Autor: Danilo Ramírez. Enlace Editorial. (Segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`Puñales en la niebla. Danilo E. Ramírez G. Editorial Enlace.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`Querida Lucy. Autor: Triunfo Arciniegas. Editorial: Enlace. (Tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Quinto

- **`Química general, orgánica y biológica. Estructuras de la vida. Karen C. Timberlake. Cuarta edición. Editorial Pearson. *`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Decimo

- **`Química general, orgánica y biológica. Estructuras de la vida. Karen C. Timberlake. Cuarta edición. Editorial Pearson. * (Es el mismo de grado 8° a 11°)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`Química general, orgánica y biológica. Estructuras de la vida. Karen C. Timberlake. Cuarta edición. Editorial Pearson. * (Es el mismo de grado 8° a 11°) Física. Wilson, Buffa, Lou. Sexta edición. Editorial Pearson. * (Es el mismo de grado 8° a 11°)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Noveno

- **`Química general, orgánica y biológica. Estructuras de la vida. Karen C. Timberlake. Cuarta edición. Editorial Pearson. * (Este es el mismo texto del año anterior)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Once

- **`Química, general, orgánica y biológica. Timberlake – Ed. Pearson (7º a- 11º).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`ROBÓTICA Robotic 1 Básico EDITORIAL: Educatemas`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Segundo

- **`ROBÓTICA: Robotic 0 Intermedio EDITORIAL: Educatemas`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Primero

- **`ROBÓTICA: Robotic 1 Avanzado EDITORIAL: Educatemas`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Cuarto

- **`ROBÓTICA: Robotic 1 Intermedio EDITORIAL: Educatemas`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Tercero

- **`ROBÓTICA: Robotic 2 Básico EDITORIAL: Educatemas`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Quinto

- **`ROBÓTICA: TECPRO F + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Sexto

- **`ROBÓTICA: TECPRO G + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Septimo

- **`ROBÓTICA: TECPRO H + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Octavo

- **`ROBÓTICA: TECPRO I + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Noveno

- **`ROBÓTICA: TECPRO J + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Decimo

- **`ROBÓTICA: TECPRO K + Acceso digital EDITORIAL: Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Once

- **`SAVIA Ciencias Naturales 1. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Primero

- **`SAVIA Ciencias Naturales 2. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`SAVIA Ciencias Naturales 3 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`SAVIA Ciencias Naturales 4 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`SAVIA Ciencias Naturales 5 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`SAVIA Lenguaje 1. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Primero

- **`SAVIA Lenguaje 2. Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Segundo

- **`SAVIA Lenguaje 3 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Tercero

- **`SAVIA Lenguaje 4 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`SAVIA Lenguaje 5 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`SAVIA Matemáticas 4 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Cuarto

- **`SAVIA Matemáticas 5 Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): San José de Fontibón · grados: Quinto

- **`SCIENCE ADVENTURE 1 EDITORIAL RICHMOND`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Primero

- **`SCIENCE ADVENTURE 3 EDITORIAL RICHMOND`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Tercero

- **`SCIENCE ADVENTURE 4 EDITORIAL RICHMOND`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Cuarto

- **`SCIENCE ADVENTURE 5 EDITORIAL RICHMOND`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Quinto

- **`SCIENCE ADVENTURE 6 EDITORIAL RICHMOND`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas de útiles 2025 ACT · grados: Sexto

- **`Se continuará con el libro Literacy Readers, Scholastic Ed. Título adquirido en el 2025, como parte del proyecto de lectura. Libro Dynamic spaces Elementary 2 student book and tools box Editorial Dinámico pedagogía y diseño.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Primero

- **`Se continuará trabajando con el texto de grado segundo - Alpha Mathematics On-Level Practice Book. 3. Editorial Libros y Libros y se desarrollarán guías para fotocopiar que servirán de apoyo académico.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Tercero

- **`Segundo período: - Libro prescrito: material en el colegio. - Lectura autónoma: Novela Gráfica: Don Quijote de la Mancha parte I. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Decimo

- **`Sherlock, Lupin y yo. Último acto en el teatro de la Ópera. Irene Adler. Editorial Planeta.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Septimo

- **`Sindy sin dientes. Autor: Mauricio López Forero. Ed. Atenea (segundo periodo)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Primero

- **`Sistema Flex TAC- Sociales 5, edición exclusiva para la institución. Ed. Libros y libros`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Quinto

- **`Sistema Flex TAC-Lenguaje 1, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Primero

- **`Sistema Flex TAC-Lenguaje 10 y 11, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Decimo

- **`Sistema Flex TAC-Lenguaje 2, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Sistema Flex TAC-Lenguaje 3, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Tercero

- **`Sistema Flex TAC-Lenguaje 4, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Cuarto

- **`Sistema Flex TAC-Lenguaje 5, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Quinto

- **`Sistema Flex TAC-Lenguaje 6, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Sexto

- **`Sistema Flex TAC-Lenguaje 7, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Septimo

- **`Sistema Flex TAC-Lenguaje 8, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Octavo

- **`Sistema Flex TAC-Lenguaje 9, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Noveno

- **`Sistema Flex TAC-Sociales 1, edición exclusiva para la institución. Ed. Libros y libros`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Primero

- **`Sistema Flex TAC-Sociales 2, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Sistema Flex TAC-sociales 3, edición exclusiva para la institución. Ed. Libros y libros`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Tercero

- **`Sistema Flex TAC-Sociales 4, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Cuarto

- **`Sistema Flex TAC-Sociales 6, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Sexto

- **`Sistema Flex TAC-Sociales 7, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Septimo

- **`Sistema Flex TAC-Sociales 8, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Octavo

- **`Sistema Flex TAC-Sociales 9, edición exclusiva para la institución. Ed. Libros y libros.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Noveno

- **`SISTEMA UNO I EDITORIAL: Santillana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Segundo

- **`Solamente la vida. Autor: Fernando Soto Aparicio. Editorial: Atenea. (Tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Octavo

- **`Sueña José Autor: Silvia Camossa. Ed. Enlace (tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Sueños intactos. - Julia Mercedes Castilla. - Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Decimo

- **`TAC-Lenguaje 11°, edición exclusiva para la institución. Ed. Libros y libros (continua con el libro 2025)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Edicion cerrada por el colegio.
  - colegios (1×): Modelia · grados: Once

- **`Te amo, peladita. Albeiro Echavarría. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Octavo

- **`Teoría del conocimiento - Johannes Hessen. Editorial Panamerica.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Noveno

- **`Tercer periodo: -Lectura autónoma: Novela gráfica. El quijote de la mancha 1. Autor: Miguel de Cervantes. Editorial: Enlace - Libro prescrito: material en el colegio`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Once

- **`Texto Fundamentos de Fisica Ruelas Arturo. Velasquez Juan Carlos. Segunda edicion. Editorial Mc Graw Hill`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Texto Fundamentos de Quimica Hein Morris. Arena Susan. Willard Cary. Decimoquinta edicion. Editorial Cengage`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`TREN DEL SABER T: LENGUAJE- SOCIALES -MATEMÁTICAS -CIENCIAS EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Transicion

- **`TRENS DEL SABER J : *LENGUAJE- SOCIALES *MATEMÁTICAS -CIENCIAS EDITORIAL: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Jardín (merged) · grados: Jardin

- **`Un regalo inesperado, María García Esperón. Editorial Enlace.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

- **`Un superhéroe para Camilo. Autor: Alfredo Alonso Hincapié Editorial: Atenea. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Quinto

- **`Una Rebelión en la granja. Autor: George Orwell. Ed. Enlace. (Primer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`Valeria. En el reino de Malagana. Albeiro Echeverria. Editorial Panamericana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Septimo

- **`Valerio Valentín va a la selva. Autor: Arturo Torres Moreno Editorial: Atenea. (tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Cuarto

- **`Valerio Valentín. Autor: Lilia Gutiérrez Riveros Ed. Atenea. (segundo periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Jardin, Primero, Segundo, Tercero, Transicion

- **`Valores. ERE 1. Editorial Maletín. (Se venderá en el colegio)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Primero

- **`Valores. ERE 2. Editorial Maletín. (Se venderá en el colegio)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Segundo

- **`Valores. ERE 3. Editorial Maletín. (Se venderá en el colegio)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Tercero

- **`Valores. ERE 5. Editorial Maletín. (Se venderá en el colegio)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Quinto

- **`Valores. ERE 6. Editorial Maletín. (Se venderá en el colegio)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Matilde · grados: Sexto

- **`Veinte poemas de amor y una canción desesperada. Autor: Pablo Neruda: Editorial Norma`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Noveno

- **`Voces desde el desvelo. Autor: Pilar Tarquino. Ed. Atenea. (Tercer periodo).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Modelia · grados: Once

- **`Vuelven las leyendas. Autor: Celso Román. Editorial Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Sexto

- **`Vuelven las leyendas. Autor: Celso Román. Editorial: Enlace`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Octavo

- **`Yo soy mayor que mi padre., Pedro Solera., Ed. SM`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Lista textos y útiles 2021 · grados: Noveno

- **`¡Silencio, niños! y otros cuentos. Autora: Ema Wolf. Torre Azul. Editorial Norma.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`¿De dónde vienen los perros?, Francisco Leal Quevedo. Editorial Panamericana.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - colegios (1×): CACS · grados: Cuarto

### directamente con el colegio (1)

- **`CARPETA IDEAS CREATIVAS/SKIFER (papelería), la puede adquirir directamente en el jardín con un 10% de descuento. Se sugiere comprarla en el jardín debido a que el contenido tiene una adecuación especial material.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se compra en el jardin, no en Tukit.
  - colegios (3×): Osito de Miel · grados: Jardin, Prejardin, Transicion

### directamente con la editorial (6)

- **`EXPEDICIÓN LENGUAJE A LIBRO CURSIVA/CUADERNO DE TRABAJO SCRIP / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`EXPEDICIÓN LENGUAJE B LIBRO CURSIVA/CUADERNO DE TRABAJO SCRIP / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`EXPEDICIÓN LENGUAJE C LIBRO CURSIVA/CUADERNO DE TRABAJO SCRIP / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`EXPEDICIÓN MATEMATICA A CON CUADERNO DE TRABAJO / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`EXPEDICIÓN MATEMATICA B CON CUADERNO DE TRABAJO / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

- **`EXPEDICIÓN MATEMATICA C CON CUADERNO DE TRABAJO / EDITORIAL ENCUENTRO. Este texto se debe adquirir directamente con la editorial debido a que se realizó una adecuación especial a nuestro proyecto educativo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Lo vende la editorial, no Tukit.
  - colegios (1×): Osito de Miel · grados: Jardin, Prejardin, Transicion

### aún no proveemos (28)

- **`3. Uniforme de Gala: El mismo uniforme de diario con blazer de paño color azul oscuro con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniformes`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1. Uniforme de diario`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1. Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocés (según el modelo) sobre la rodilla, media pantalón de lana azul oscuro, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1. Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón azúl oscura, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1. Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscura, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón,`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1. Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscuro, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con el escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`1.Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azúl oscura, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo. Delantal de tela según modelo`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2. Uniforme para educación física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`2. Uniforme para Educación Física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos. *Para la clase de natación traje de baño: Femenino: Mujeres: Usar traje de baño de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el capítulo 1 artículo 14 Uniforme de Educación Física. Gorro en Lycra o Silicona y Gafas. Masculino: Pantaloneta de baño (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de natación. Nota: las gafas de natación son opcionales`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`3. Uniforme de Gala: El mismo uniforme de diario con blazer de pa%f1o color azul oscuro con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Quinto

- **`Para la clase de nataci%f3n traje de ba%f1o: Femenino: Mujeres: Usar traje de ba%f1o de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el cap%edtulo 1 art%edculo 14 Uniforme de Educaci%f3n F%edsica. Gorro en Lycra o Silicona y Gafas.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Quinto

- **`Para la clase de natación traje de baño: Femenino: Mujeres: Usar traje de baño de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el capítulo 1 artículo 14 Uniforme de Educación Física. Gorro en Lycra o Silicona y Gafas.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Sexto

- **`Para la clase de natación traje de baño: Femenino: Mujeres: Usar traje de baño de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el capítulo 1 artículo 14 Uniforme de Educación Física. Gorro en Lycra o Silicona y Gafas. Masculino: Pantaloneta de baño (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de natación.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto

- **`PARAGRAFO: Los estudiantes de Grado Once no portarán el Saco Naranja ni la chaqueta de la sudadera, su uniforme se complementará con la Chaqueta PROM respectiva, de acuerdo con el Modelo orientado por el Gimnasio Modelia Real. De presentarse inconvenientes con la chaqueta de Prom. los estudiantes de grado once deberán portar o el saco naranja institucional o la chaqueta de educación física. Está prohibido el uso de sacos con capota diferentes a los de la chaqueta del Prom.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Bachillerato, Once, Preescolar, Primaria

- **`Uniforme de diario`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocés (según el modelo) sobre la rodilla, media pantalón de lana azúl oscuro, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con el escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscura, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme de Gala`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme de Gala: El mismo uniforme de diario con blazer de paño color azul oscuro con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme de Gala: El mismo uniforme de diario con blazer de paño color azul oscuro o negro con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto

- **`Uniforme para educaci%f3n f%edsica: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas seg%fan modelo y color establecido para cada curso. Tenis de cuero totalmente blancos.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Quinto

- **`Uniforme para educación física`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme para educación física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta,`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Uniforme para educación física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto

- **`Uniforme para educación física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos. Femenino: Mujeres: Usar traje de baño de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el capítulo 1 artículo 14 Uniforme de Educación Física. Gorro en Lycra o Silicona y Gafas. Masculino: Pantaloneta de baño (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de natación. Nota: las gafas de natación son opcionales`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`UNIFORMES 1. Uniforme de diario: Femenino: blusa blanca manga larga, cuello bebé, chaleco azul bordado en el cuello con rojo y con escudo del colegio, falda escocesa (según el modelo) sobre la rodilla, media pantalón de lana azul oscuro, zapato colegial azul oscuro, blazer azul de paño con el escudo del colegio bordado en el bolsillo izquierdo. Masculino: camisa blanca manga larga con cuello clásico, corbata vinotinto, chaleco azul bordado en el cuello con rojo y con escudo del colegio, pantalón de paño gris ratón, medias clásicas grises (no tobilleras) y zapatos negros de cuero (No se permiten zapatos de charol, gamuza, ni tenis negros), blazer azul de paño con el escudo del colegio en el bolsillo izquierdo. 2. Uniforme para educación física: Sudadera completa de color azul oscuro con el escudo del colegio, debajo pantaloneta, camiseta y medias largas según modelo y color establecido para cada curso. Tenis de cuero totalmente blancos. Para la clase de natación traje de baño: Femenino: Mujeres: Usar traje de baño de una sola pieza de color oscuro o negro, sin estampados, material de licra o poliamida de acuerdo a lo establecido en el capítulo 1 artículo 14 Uniforme de Educación Física. Gorro en Lycra o Silicona y Gafas. Masculino: Pantaloneta de baño (en licra, poliamida, o endurance) cualquier color oscuro o negro, gorro de natación. Nota: las gafas de natación son opcionales. 3. Uniforme de Gala: El mismo uniforme de diario con blazer de paño color azul oscuro con el escudo del colegio en el bolsillo izquierdo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`UNIFORMES: Uniforme de diario, Uniforme para educación física, Uniforme de Gala`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Fuera de alcance de esta version.
  - colegios (1×): CACS · grados: Primero

### aún no se compra (9)

- **`bata blanca marcada. (Durante el año se solicitará para la realización de experimentos.)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (3×): Modelia · grados: Jardin, Prejardin, Transicion

- **`Cuento para el plan lector, que se solicitará para el segundo periodo académico a través de una circular.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (3×): San Pedro · grados: Jardin, Prejardin, Transicion

- **`Plan Lector: se solicitará una obra literaria cada periodo`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (3×): San Pedro · grados: Octavo, Septimo, Sexto

- **`Kit básico de componentes electrónicos que se emplea a lo largo del bachillerato. Dependiendo del tipo de proyecto o experiencia práctica, se solicitarán materiales adicionales específicos.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (2×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`-Material fotocopiable. Se solicitará según se requieran durante el curso.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (1×): Listas 2026 · grados: Once

- **`ACTIVIDADES PEDAGÓGICAS DURANTE EL AÑO ESCOLAR Se realizará una convivencia y una salida pedagógica interdisciplinaria.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`ACTIVIDADES PEDAGÓGICAS DURANTE EL AÑO ESCOLAR: Se realizará una convivencia y una salida pedagógica interdisciplinar.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (1×): CACS · grados: Cuarto, Decimo, Jardin, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Material fotocopiable. Se solicitará según se requieran durante el curso`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`Se solicitará material didáctico y para las prácticas de laboratorio a lo largo del año`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio lo pedira mas adelante.
  - colegios (1×): Listas 2026 · grados: Septimo

### no comprar (12)

- **`Diccionario Español (El que tenga en casa)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (10×): Listas de útiles 2025 ACT · grados: Cuarto, Noveno, Octavo, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero

- **`Diccionario Inglés - español (El que tenga en casa)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (9×): Listas de útiles 2025 ACT · grados: Cuarto, Noveno, Once, Primero, Quinto, Segundo, Septimo, Sexto, Tercero

- **`Diccionario: El disponible en casa`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (4×): CACS · grados: Primero, Quinto, Segundo, Tercero

- **`cuento, se sugiere (colección buenas noches), o el que tenga en casa.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Prejardin

- **`cuento. se sugiere (colección buenas noches), o el que tenga en casa`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Transicion

- **`Diccionario Español (El que tenga en casa).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`Diccionario Inglés - español (El que tenga en casa`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Octavo

- **`Diccionario inglés - español (El que tenga en casa).`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Decimo

- **`ESPAÑOL EL QUE TENGA EN CASA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`FILOSÓFICA EL QUE TENGA EN CASA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

- **`James no está en casa.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Lista textos y útiles 2021 · grados: Cuarto

- **`MATEMATICAS EL QUE TENGA EN CASA`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: El colegio indica usar el que ya tienes.
  - colegios (1×): Listas de útiles 2025 ACT · grados: Once

### licencia digital / plataforma (30)

- **`Plataforma de Inglés-Editorial Houghton Mifflin Harcourt (HMH) *En el mes de ENERO 2026 se enviará una circular con las instrucciones, fechas y medios de pago. Les agradecemos esperar la información institucional.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (8×): San Pedro · grados: Cuarto, Decimo, Noveno, Once, Primero, Segundo, Septimo, Tercero

- **`Plataforma de comunicaciones $63.000 (Ítem a cobrar en el recibo de matrícula)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (7×): Lista de útiles 2026 · grados: Cuarto, Decimo, Octavo, Primero, Segundo, Septimo, Sexto

- **`Sistema de aprendizaje Socioemocional Happy - Amco (se adquiere de manera individual por plataforma.)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (7×): Modelia · grados: Cuarto, Jardin, Prejardin, Primero, Quinto, Tercero, Transicion

- **`Link de pago: https://pagoslearning.com/`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (5×): CACS · grados: Decimo, Octavo, Once, Septimo, Transicion

- **`Sistema de aprendizaje Socioemocional Happy – Amco (se adquiere de manera individual por plataforma.)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (5×): Modelia · grados: Jardin, Noveno, Octavo, Primero, Segundo, Septimo, Sexto, Tercero, Transicion

- **`Plataforma de comunicaciones $63.000 (Ítem a cobrar incluido en el recibo de matrícula)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (3×): Lista de útiles 2026 · grados: Jardin, Prejardin, Transicion

- **`Plataforma de Inglés-Editorial Houghton Mifflin Harcourt (HMH)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (3×): San Pedro · grados: Octavo, Quinto, Sexto

- **`Plataforma de lectura Literacy Pro Next Generation Full Bundle + Placement Test. Para el proceso de compra se darán las directrices al iniciar 2026`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (3×): Listas 2026 · grados: Noveno, Octavo, Septimo

- **`Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: https://pagoslearning.com/`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (2×): CACS · grados: Noveno, Sexto

- **`Plataforma de comunicaciones $63.000`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (2×): Lista de útiles 2026 · grados: Once, Quinto

- **`Plataforma de lectura Beereaders. (todo el año)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (2×): Listas 2026 · grados: Decimo, Noveno

- **`-Plataforma de lectura Literacy Pro Next Generation Full Bundle + Placement Test:Para el proceso de compra se darán las directrices al iniciar 2026`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Decimo

- **`-Plataforma de lectura Literacy Pro Next Generation Full Bundle + Placement Test:Para el proceso de compra se darán las directrices al iniciar 2026.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Once

- **`Comprensión lectora y Plan lector virtual Lengua Castellana RAZ- PLUS. Link de pago: https://pagoslearning.com/. Libros de plan lector: La familia más rica del mundo, Editorial Enlace. El país más hermoso del mundo. Editorial Norma. Detective Equis. Antonia Sanín. Ediciones Castillo.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Tercero

- **`Comprensión lectora y Plan lector virtual Lengua Castellana RAZ- PLUS. Link de pago: https://pagoslearning.com/. Libros de plan lector: La llave de las estrellas, Malena Salazar Murcia. Editorial Enlace. La teoría de los colibríes, Michelle Kadarusman. Editorial Norma. La palabra más hermosa, Jordi Sierra i Fabra. Editorial Algar.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Quinto

- **`Comprensión lectora y Plan lector virtual Lengua Castellana RAZ- PLUS. Link de pago: https://pagoslearning.com/. LIBROS DEL PLAN LECTOR: Yo soy yo. (Incluye cuaderno de actividades).Gabriela Peyron. Editorial Norma. Bobot (incluye cartilla de actividades). Cecilia Eudave. Editorial Castillo. Antología de cuentos para leer. Jorge A. Jiménez R. Editorial Palbooks.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Segundo

- **`Cuarto periodo: -Plataforma de lectura Beereaders.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Once

- **`Diccionario Inglés- español. Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: https://pagoslearning.com/. Nota: mismo link de lengua castellana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Quinto

- **`Libro: Oxford Discover Science, # 2, Second edition. Editorial Oxford y plataforma online.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Segundo

- **`Libro: Oxford Discover Science, # 3, Second edition. Editorial Oxford y plataforma online.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Tercero

- **`Libro: Oxford Discover Science, # 4, Second edition. Editorial Oxford y plataforma online.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Cuarto

- **`Libro: Oxford Discover Science, # 5, Second edition. Editorial Oxford. y plataforma online.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Quinto

- **`Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: https://pagoslearning.com/ Nota: mismo link de lengua castellana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Tercero

- **`Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: https://pagoslearning.com/. Nota: mismo link de lengua castellana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Primero

- **`Plan lector virtual Inglés RAZ- PLUS, administrada en Colombia por QUOVIX. Link de pago: Link de pago: https://pagoslearning.com/. Nota: mismo link de lengua castellana`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Segundo

- **`Plan lector virtual Lengua Castellana RAZ PLUS. Link de pago: https://pagoslearning.com/. PLAN LECTOR: Filo. Mi amigo imaginario. Mapi y Fabio Sardo. Editorial Enlace. El mundo del señor agua. El fantástico viaje del señor agua. Agostino Traini. Editorial Planeta. Anita y el dulce de leche de la abuela. Pilar Vélez. Editorial Palbooks.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): CACS · grados: Primero

- **`Plataforma de comunicaciones`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Lista de útiles 2026 · grados: Noveno

- **`Plataforma de comunicaciones (Ítem a cobrar en el recibo de matrícula)`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Lista de útiles 2026 · grados: Tercero

- **`Plataforma de lectura Beereaders. Todo el año.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Once

- **`Plataforma de lectura Literacy Pro Next Generation Full Bundle + Placement Test.`**
  - estado: `fuera_busqueda` · concepto: — · attrs: —
  - motivo: Se paga fuera de Tukit. No entra al carrito.
  - colegios (1×): Listas 2026 · grados: Sexto
