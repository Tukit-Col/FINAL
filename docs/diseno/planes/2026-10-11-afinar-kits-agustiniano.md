# Afinar los kits del Agustiniano sin poblar el catálogo

- **Fecha:** 2026-10-11.
- **Estado:** ejecutado el 2026-10-11, salvo poblar el catálogo (fuera de alcance; ver [pendientes](../../PENDIENTES.md), §3). Resultado medido con `ensayos/kits_offline.py`, confirmado de punta a punta en bases aisladas y aplicado después a la base de desarrollo (importar y regenerar los canónicos), con los mismos totales: los huecos que ve el acudiente pasan de 385 a 220; los kits, de $9.857.452 a $8.959.420 (Ahorrador) y de $17.602.526 a $14.159.658 (Premium).
- **Origen:** la [auditoría de huecos del Agustiniano](../../informes/nuevo-reporte-huecos-agustiniano.md) (commit `d4ea7cb`).
- **Alcance:** todo lo que se arregla con código, con la curaduría de las listas y con la curaduría de lo que ya está en el catálogo. Poblar el catálogo con el scraper queda fuera, a pedido del usuario, hasta terminar este afinamiento. La lista de lo que falta surtir está en [surtido-huecos-agustiniano.md](../../informes/surtido-huecos-agustiniano.md).

## Decisiones del usuario (2026-10-11)

- Tarro y frasco son lo mismo.
- C142 (componentes electrónicos especializados) no se vende. C071 Kit de tecnología se desactiva, y sus productos van a C142 o a su concepto propio (protoboards a C102, jumpers a C121).
- Los audífonos (C110) y los textos con título (C134) tampoco se venden. Llegan como "Lo consigues por tu cuenta".
- Nada de scraper por ahora.

## Fases

### 0. Medir

- `ensayos/kits_offline.py` arma, a partir de `datos/` y sin base de datos, lo que la ruta rápida y el optimizador le darían a cada renglón del colegio: el tipo con que llega, lo que se exige, los candidatos y el producto de cada perfil, con sus unidades y su subtotal.
- `ensayos/test_kits_offline.py` fija el resultado esperado de los renglones de la auditoría que este plan corrige. Corre con el resto de las pruebas.
- El empaque (`unidad_base`, `unidades_por_empaque`) pasa a ser columna de `productos_canonicos.csv`. Hoy solo lo escribe `enriquecer` en la base, así que cada recarga lo deja en 1.

### 1. Código

- La ruta rápida toma el tipo del concepto cuando el renglón no trae uno (sección 3.1 de la auditoría).
- `juntar_herramientas` junta por concepto, no por SKU: elige un solo producto que sirva para todos los renglones del mismo hijo (3.5).

### 2. Cómo se comparan los atributos

- Cada atributo se compara de una forma: exacta, "al menos", con tolerancia o con equivalencias (respuesta a 5.1).
- Correcciones del extractor: números escritos en letras, plurales de tamaño, `#10`, `cms`, pulgadas, vocabulario nuevo.
- Discriminantes nuevos en los conceptos que no tienen.
- Los libros cargan los atributos que se leen de su título. Los diccionarios se unifican en C034, con el idioma como discriminante.
- Un valor curado `*` en el renglón quita un atributo leído del texto.

### 3. Curaduría de las listas

- Tipo `no_comprar`, `otro` o `uniforme` donde el colegio no pide comprar.
- Conceptos equivocados, renglones compuestos partidos en dos y cantidades.
- Atributos curados donde el vocabulario no alcanza.

### 4. Curaduría del catálogo

- Atributos que faltan, el campo `personaje`, los títulos de los libros y la reclasificación de C071.

### 5. Regenerar y volver a medir

- Recrear las bases aisladas de la auditoría, cargar, correr el poller y comparar con la auditoría de `d4ea7cb`.
