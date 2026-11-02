# Handoff: personalización final (decidido el 17-oct-2026)

**Decisión de María Paula (opción A):** el carrusel queda fuera del demo y del pitch por ahora.
Se retoma antes de las sesiones de validación con padres (OE5).

## Cómo debe ser cuando se retome
- **Productos reales, no portadas inventadas.** El carrusel muestra los cuadernos del catálogo
  (foto, marca y precio reales) que cumplen el renglón de la lista. Se descartan las 8 portadas
  de la rama `mejoras/seguridad-ortografia-carrusel`: esos SVG pesan 0 bytes y no son productos
  que vendamos.
- **Sin nombre del niño.** No se pide ningún texto libre: nos ahorra el riesgo de datos de
  menores y la promesa de imprimir algo que no podemos imprimir.
- **Sin stickers en la interfaz.** Los stickers son un regalo de TUKIT dentro del kit, no una
  opción que el padre configure.
- **Sí a las preferencias de rayado.** El padre puede filtrar cuando la lista no lo exige:
  cuadriculado, ferrocarril, una línea o doble línea, y si se puede, tamaño y hojas. Cuando la
  lista sí lo exige, la preferencia queda bloqueada y se explica por qué.
- **Se apoya en lo que ya existe en `origin/main`:** el botón "Cambiar por otra opción" de
  `LineaDeKit` y la ruta `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item}/producto`. El
  carrusel pasa a ser la forma de presentar esas opciones, no un flujo nuevo.

## Requisito previo: los atributos del catálogo
Para filtrar por rayado, tamaño y hojas, cada producto necesita esos atributos llenos y con el
mismo vocabulario. Hoy no es así. Por ejemplo, en la lista revisada de Tercero del Agustiniano,
los renglones de cuaderno (9, 33, 40 y 42) tienen `atributos` vacío. Además, el renglón 70
("…del año anterior") está marcado para comprar, y seguramente no debería.

La auditoría y el plan de llenado van en `05_atributos_catalogo.md`.

## Pendiente de la rama `mejoras/seguridad-ortografia-carrusel`
No se fusiona entera: tiene 15 archivos en conflicto y está 154 commits detrás. Si sirve
rescatar algo, sería el CSS del carrusel (scroll-snap y controles) y las páginas de cookies,
privacidad y términos, revisadas aparte.
