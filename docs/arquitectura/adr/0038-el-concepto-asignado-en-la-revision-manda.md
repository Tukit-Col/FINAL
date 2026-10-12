# ADR 0038 — El concepto asignado en la revisión manda sobre el texto, y su tipo decide si se busca

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `catalogo` (`consulta.emparejar`, `/v1/catalogo/emparejar`), `inteligencia` (ruta rápida, previsualización)

## Contexto

En la revisión de una lista, una persona asigna el concepto de cada renglón. Pero la
previsualización de los kits y la ruta rápida volvían a emparejar **por el texto**, como si nadie
lo hubiera revisado. Un `Juego didáctico … Opciones: rompecabezas, lotería` asignado a mano a su
concepto salía en la previsualización como "No entendimos qué pide", y lo curado no se
aprovechaba.

Además, la ruta rápida intentaba ponerle producto a cualquier renglón con concepto, incluidos
uniformes, licencias o una muda de ropa. Cuando el concepto era un `util` todavía sin productos,
el trabajo terminaba en un 500 en vez de reportar el hueco.

## Decisión

1. **El concepto asignado se respeta.** `/v1/catalogo/emparejar` acepta `conceptos`, una lista
   paralela a los renglones con el código ya asignado. Si el código existe, no se clasifica por el
   texto: solo se buscan los productos de ese concepto (`concepto_forzado`, parecido 1.0).
2. **El tipo decide si se busca en el catálogo.** Solo `util` y `libro_libre` se surten. Si el
   renglón trae tipo propio, ese manda; si no, manda el del concepto. Lo demás es una línea
   informativa con el mensaje de su tipo.
3. **Sin productos no es un error.** Un `util` cuyo concepto no tiene productos queda
   `HUECO_CATALOGO` ("No lo tenemos"), no tumba el trabajo.

## Alternativas rechazadas

- **Agregar el texto del renglón como sinónimo en cada revisión, para que el texto acierte
  solo.** Llena los conceptos de frases de una sola lista que después atraen renglones ajenos. El
  sinónimo se agrega cuando sirve para listas futuras, no para forzar esta.
- **Confiar solo en el tipo del renglón.** Muchos renglones llegan sin tipo de la percepción; el
  del concepto es el único dato curado disponible.

## Consecuencias

- La previsualización muestra lo que el revisor decidió, que es lo que luego se publica.
- Asignar mal un concepto en la revisión ya no se corrige solo: el error del revisor se respeta.
  Es el precio de que el acierto también se respete.
- Una versión que ya está en la cola no cambia al crear un concepto o mover un sinónimo: hay que
  reasignarla a mano.
