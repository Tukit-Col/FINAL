# ADR 0040 — Cómo se compara cada atributo, y la cantidad en unidad base

- **Estado:** aceptada
- **Fecha:** 2026-10-11
- **Servicios tocados:** `catalogo` (`consulta._cumple`, `routers/admin` ruta rápida, `enriquecer`,
  `cargador`, `volcar`)
- **Origen:** la [auditoría de huecos del Agustiniano](../../informes/auditoria-huecos-agustiniano/v2-d4ea7cb.md),
  sobre `d4ea7cb`: de 888 renglones comprables, 465 salían bien; 57 eran falsos huecos y 151 se
  resolvían con un producto que no cumplía.

## Contexto

El filtro por renglón (`_renglon_resuelto`) exigía cada atributo **igual** al del producto. Eso
dejaba fuera lo que sirve: una escuadra de 26 cm donde piden 20, un ferrocarril de 100 hojas donde
piden 80, un sketchbook A4 donde piden carta. Y dejaba pasar lo que no sirve cuando el atributo
que hacía la diferencia no se leía o el concepto no lo filtraba: un marcador suelto por una caja, un
óleo por una pintura escolar.

Además, la cantidad del renglón y el empaque del producto no hablaban el mismo idioma. El empaque
solo existía en la base (lo escribía `enriquecer`), así que cada recarga desde `datos/` lo dejaba en
1 y el kit compraba diez paquetes de veinte hojas para diez hojas. Y donde la lista contaba paquetes
(«3 paquetes de octavos»), la cantidad estaba en paquetes, no en unidades.

## Decisión

1. **Cada atributo se compara a su manera.** Lo que cambia qué cosa es se compara exacto. Lo que se
   mide admite lo cercano. Las tablas están en `consulta.py` (`_AL_MENOS`, `_TOLERANCIA`,
   `_EQUIVALENTES`) y en la guía de curaduría (§5.5):
   - `hojas`: al menos lo pedido, a lo sumo el doble.
   - `unidades`, `colores`, `piezas`, `notas`, `gramaje`, `capacidad`: al menos lo pedido.
   - `puntos`: entre lo pedido y 2,2 veces lo pedido.
   - `longitud`: entre 0,85 y 1,35 veces lo pedido.
   - Medidas `a x b cm`: menos de un 25 % por lado (estricto desde el 2026-10-12: en el borde, un lienzo de 30 × 25 pasaba por uno de 30 × 40).
   - Equivalencias: `carta` ≈ `a4`, `frasco` = `tarro`, `plastico` ≈ `antifluido`.
   - `idioma`: «de inglés» acepta el bilingüe con español; «inglés – inglés», solo el monolingüe.
2. **Lo que el producto no declara no cumple.** Se descartó tratarlo como «por confirmar»: la
   decisión de 2026-10-07 es que, si nada cumple, hay hueco y no un sustituto. Lo que falta se
   corrige en los datos (el producto declara el atributo), no aflojando el filtro.
3. **Un renglón que pide un juego exige más de uno.** En los conceptos que filtran por `unidades`, la
   caja, el estuche, el kit o un plural con cantidad 1 piden más de una unidad. Si ningún juego
   cumple, vale la pieza suelta, porque eso se dedujo y el renglón no lo dijo.
4. **El revisor puede quitar un atributo leído** con el valor `*` en los atributos del renglón.
5. **La herramienta pedida en varias materias sale de un solo producto.** Antes de elegir, los
   renglones de un concepto `uno_por_estudiante` se quedan con los candidatos que sirven para todos.
   `juntar_herramientas` sigue juntando por SKU, y ahora el SKU coincide.
6. **La ruta rápida toma el tipo del concepto** cuando el renglón no trae uno (ADR 0038 ya lo decía
   para la ruta lenta).
7. **El empaque es curaduría:** `unidad_base` y `unidades_por_empaque` son columnas de
   `productos_canonicos.csv`, y `enriquecer` no pisa un valor mayor que 1. **La cantidad del renglón
   va en unidad base**: «2 cajas de colores x 12» son 24 colores.

## Consecuencias

- En la medición sin base de datos (`ensayos/kits_offline.py`), los 13 kits del Agustiniano pasan de
  $9.857.452 a $8.959.420 (Ahorrador) y de $17.602.526 a $14.159.658 (Premium). Los huecos que ve el
  acudiente pasan de 385 a 220; los otros 212 renglones llegan como líneas informativas (uniforme,
  licencia, «por su cuenta», «no hay que comprarlo»).
- Algunos renglones que antes se cobraban con un sustituto ahora son huecos honestos: pegante de
  125 g, bata antifluido, lienzo de 30 x 40, block rayado, cartulina fluorescente. Son la lista de
  surtido (`docs/informes/surtido-huecos-agustiniano.md`).
- Un concepto que agrega un discriminante necesita que sus productos lo declaren. Si no, deja huecos
  falsos. La guía lo pide en su lista de verificación.
- Las tolerancias son una decisión de producto, no una constante física. Se cambian en
  `consulta.py` y se mide el efecto con `kits_offline.py` antes de aceptar el cambio.
