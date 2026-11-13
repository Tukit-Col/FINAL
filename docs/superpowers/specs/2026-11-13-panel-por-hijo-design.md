# Diseño: panel por hijo en la vista del kit (hogar con 2+ hijos)

**Fecha:** 2026-11-13 · **Tamaño:** cambio acotado (solo web + un helper de contrato).

## Intención y porqué
Un acudiente con dos o más hijos no logra, de un vistazo, separar el kit de
cada hijo, ver qué comparten y qué le falta a cada uno: hoy todo vive en una
sola lista agrupada por categoría con los hijos mezclados. Quiere identificar
"facilito" cada kit, lo compartido y lo que falta.

## Objetivos
- Con 2+ hijos, un **resumen por hijo** arriba del kit: una tarjeta plegable
  por hijo con su nombre, grado, personaje (si lo pidió), total, sus productos,
  y su "falta".
- Una **banda de compartido** arriba de las tarjetas (lo que hoy es "Lo que
  juntamos entre tus hijos").
- La **lista por categoría de hoy queda intacta** debajo, sin cambios.

## No-objetivos / anti-objetivos
- No reemplazar ni reordenar la lista actual (el acudiente sigue comprando
  desde ella).
- No recalcular aritmética de kit ni tocar el backend de Inteligencia salvo lo
  ya expuesto (`personajes_por_hijo`, `personaje_sin_encaje`, `consolidaciones`).
- No mostrar nunca el apodo donde no corresponde ni la referencia interna
  (Ley 1581): el panel usa `nombresHijos` (apodo/"Hijo N"), nunca `hijo`.
- No aparece con un solo hijo (la vista de hoy ya basta).

## Enfoque elegido
**Resumen por hijo arriba + lista actual debajo.** Se descartaron:
- *Reemplazar la vista por hijo:* reescribe `SeccionesDeLineas` y los bloques
  "fuera del carrito"; riesgo alto sobre código que acaba de cambiar.
- *Conmutador por-hijo ↔ por-categoría:* más trabajo y estado nuevo, sin que el
  acudiente lo haya pedido.
- *Tabla comparativa:* densa en celular (la web del padre es sobre todo móvil).

## Decisiones (mis llamadas sobre lo que quedó abierto)
- **Cuándo:** solo si el kit activo tiene 2+ hijos distintos en sus líneas.
  Un hijo → no se pinta nada nuevo.
- **Qué perfiles:** cualquier perfil activo (Ahorrador/Fan/Premium/A tu Medida).
  La línea de personaje de una tarjeta solo aparece si ese hijo pidió uno; la
  nota de "falta de personaje" solo aplica en Fan (viene de `personaje_sin_encaje`).
- **Plegado:** cada tarjeta plegable; **por omisión expandida**. El encabezado
  (nombre · grado · personaje · total · "N comparten · M faltan") siempre visible.
- **Total por hijo:** suma de los subtotales de las líneas comprables de ese
  hijo. Como un empaque compartido ya deja la línea del hermano en 0 unidades
  (`consolidar`), los totales por hijo suman exactamente el total del kit; no se
  reparte el costo de lo compartido.
- **"Falta" por hijo:** sus líneas en estado hueco / sin_match / pendiente de
  revisión (la clasificación `ABSTENCIONES` que ya existe) más las notas de
  `personaje_sin_encaje` de ese hijo. Texto corto, con el icono de aviso de hoy.
- **Compartido:** se reutiliza la sección de consolidaciones existente; en la
  vista por hijo se muestra como banda arriba de las tarjetas. La sección
  original de "Lo que juntamos" se mantiene (no se duplica el cálculo; es el
  mismo `kit.consolidaciones`).
- **Producto por tarjeta:** nombre + categoría + foto o icono de categoría
  (mismo patrón que la franja Fan). No repite el carrusel ni los controles de
  cambio: para eso está la lista de abajo; la tarjeta es de lectura.

## Qué toca
- `apps/web/src/app/kits/[trabajo_id]/VistaKits.tsx`: nuevo componente
  `ResumenPorHijo` (tarjetas plegables + banda compartido), montado antes de
  `SeccionesDeLineas` cuando hay 2+ hijos.
- `apps/web/src/lib/kit-vista.ts`: helper puro que arma, por hijo, `{nombre,
  grado, personaje, total, productos, falta, comparten}` desde `kit.lineas`,
  `consolidaciones`, `personajes_por_hijo`, `personaje_sin_encaje`,
  `nombresHijos`, `gradosHijos`. Probado con `node --test`.
- `apps/web/src/app/kits/[trabajo_id]/Kits.module.css`: estilos de las tarjetas.
- Sin cambios de contrato nuevos (los campos ya existen tras la rama hermanos).

## Qué queda al constructor
- Microcopy exacto de los encabezados y de la fila "falta".
- Si el plegado recuerda estado entre perfiles (propongo que no: estado local
  simple, expandido al entrar).
