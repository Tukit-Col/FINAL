# Mis pedidos con fases (dashboard del padre)

## Verificacion: lo que el operador cambia en admin, ¿lo ve el padre?
SI se refleja (misma fuente, sin cache que lo retrase).
- Admin avanza la fase por `POST /v1/ordenes/{id}/avanzar` de Comercio; el estado vive en la tabla de pedidos + historial.
- El dashboard lee `GET /v1/comercio/mis-pedidos` (`servicios/comercio/tukit_comercio/routers/comercio.py:145`), mismo repositorio. Filtra por el `usuario_id` de la SESION validada contra Identidad (`:156`), no por parametro.
- Sin cache: `cache: "no-store"` en `libs/ts/tukit-contrato/src/cliente-http.ts:182` y `export const dynamic = "force-dynamic"` en `apps/web/src/app/dashboard/page.tsx:54`.
- Lo unico que retrasaba el cambio: la pagina solo se leia al cargar. Ahora hay polling (abajo).
- Etiquetas: `ETIQUETA_PASO_ACUDIENTE` (admin, `logistica.ts:288`) es copia de `ETIQUETA_PASO_PEDIDO` del contrato; admin no puede importar valores del contrato (node test), asi que queda duplicada.

## Construido
- Backend (lectura): `mis_pedidos` ahora trae `linea_de_tiempo` por pedido (la misma de `/mis-pedidos/{id}`, sin actor, nota ni celular). Test en `test_checkout.py`.
- Contrato: `PASOS_PEDIDO`, `FASES_SEGUIMIENTO`, `ETIQUETA_FASE_SEGUIMIENTO` ("Preparando tu kit"), `Pedido.linea_de_tiempo?`, subruta `@tukit/contrato/comercio`.
- Web: `lib/fases-pedido.ts` (logica pura), `dashboard/SeguimientoPedido.tsx` + `Seguimiento.module.css` (iconos lucide distintos, check en hechas, pulso en la actual, gris futuras, incidencia en ambar, cancelado atenuado, fecha por fase, repartidor, entrega estimada; horizontal en escritorio, vertical en movil; reduced-motion), `ActualizarSolo.tsx` (router.refresh cada 30 s con pestana visible y al volver a enfocar, minimo 10 s entre lecturas, solo si hay pedidos sin cerrar). Mis pedidos pasa de tabla a tarjetas, con enlaces a "Ver el pedido completo" y "Abre un caso" (`#casos`).
- Test: `apps/web/test/fases-pedido.test.ts` (8, pasan).

## Verificado
tsc web y contrato, eslint, node --test (web fases 8, contrato), pytest comercio 298. Capturas escritorio y movil con pagina temporal (borrada) y datos ficticios, leidas.

## NO verificado
- El dashboard real con sesion (tarjeta completa con badge/acciones/DetallePedido) y el polling en navegador.
- El pulso animado (captura estatica); la captura movil en Chrome headless se corta a ~500 px de layout, no se vio el ancho 390 exacto.
- El dev server en :3000 sirve una copia vieja del contrato (los exports nuevos salen undefined): hay que reiniciarlo.

## Reiniciar
SI: `make reanudar` (backend comercio, para `linea_de_tiempo` en mis-pedidos) y reiniciar los dev servers web/admin (contrato nuevo). Sin reinicio de comercio las tarjetas salen sin fases (campo opcional), no se rompe.

## Pendiente menor
CSS viejo de la tabla (`.table`, `.filaPedido`, etc.) en Dashboard.module.css quedo sin uso.
