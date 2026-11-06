# ADR registrados desde el submódulo

> **Actualización 5-nov-2026:** los ADR 0001-0026 ya están copiados en esta misma carpeta
> (índice en [`INDICE_0001-0026.md`](INDICE_0001-0026.md)), así que los 49 registros viven
> aquí. La carpeta `Arquitectura/` del repositorio de documentos quedó archivada en
> `_archivo/2026-11-05/borradores_arquitectura/`. Lo que sigue es la historia de por qué la
> serie estuvo partida en dos.

Los registros de decisión de arquitectura viven en `Arquitectura/adr/`, fuera de este
repositorio, y su índice es la tabla del §4 de `Arquitectura/ARQUITECTURA.md`. El código los
cita por número (`ADR 0012`, `ADR 0017`…) y los planes de `docs/diseno/planes/` los crean allá.

Esta carpeta existe porque esa otra mitad no siempre está a la mano: la rama
`feature/pagos-wompi-sandbox` se trabajó en una máquina sin `Arquitectura/`, y una decisión
que solo vive en un mensaje de commit no es una decisión registrada. Se escriben aquí, en el
mismo formato (Nygard: contexto, decisión, alternativas rechazadas, consecuencias), y se
mueven cuando alguien con el repositorio de la tesis los incorpore.

La numeración **continúa la serie externa**. Los primeros de esta carpeta nacieron como
0021-0026, pero el backbone (resiliencia, eventos, observabilidad) registró allá sus propios
0019 a 0026 y el código cita los dos. Por eso los de pagos y curaduría se renumeraron a
0033-0038 al unir las ramas: en el código, `ADR 0021` a `ADR 0026` son siempre los del
backbone. Lo mismo pasó al unir `feature/afinar-kits-agustiniano` y `feature/maps-and-feats`
después de `arreglos/h-b-01-03`: el de atributos nació como 0040 y es 0043, y los de Google
Places y del alta de colegios nacieron como 0039 y 0040 y son 0044 y 0045. El número es una
etiqueta; el título es la decisión.

| ADR | Decisión | Estado | Origen |
|---|---|---|---|
| [0027](0027-lo-que-tukit-no-vende-se-clasifica.md) | Lo que Tukit decide no vender se clasifica como `otro`, no queda como hueco | aceptada | `feature/curaduria-de-listas` |
| [0028](0028-los-cambios-del-acudiente-viven-en-su-trabajo.md) | Los cambios del acudiente viven en su trabajo, no en las líneas del kit | aceptada | `feature/integracion` |
| [0029](0029-con-presupuesto-se-recomienda-la-mejor-marca-que-cabe.md) | Con presupuesto se recomienda la mejor marca que cabe, tomada del frente | aceptada, reemplazada en parte por 0030 | `feature/mejoras-benchmark-nsga` |
| [0030](0030-solo-se-arman-los-kits-que-se-piden.md) | Solo se arman los kits que el acudiente pide: Ahorrador y Premium siempre, Fan y A tu Medida a pedido | aceptada | `feature/integracion` |
| [0031](0031-el-acudiente-cancela-solicitudes-y-edita-a-sus-hijos.md) | El acudiente cancela sus solicitudes y quita o cambia de colegio a sus hijos | aceptada | `feature/integracion` |
| [0032](0032-la-logistica-de-preview-kits-se-une-sin-su-cola.md) | La logística de `preview-kits` se une a los pagos; su cola y su vista previa no | aceptada | `feature/integracion-total` |
| [0033](0033-pago-con-widget-de-wompi.md) | El pago se abre con el widget de Wompi, con la configuración por `postMessage` | aceptada | `feature/pagos-wompi-sandbox` |
| [0034](0034-confirmacion-del-pago-por-sincronizacion-y-webhook.md) | El pago se confirma preguntándole a Wompi, y webhook y sincronización comparten un aplicador idempotente | aceptada | `feature/pagos-wompi-sandbox` |
| [0035](0035-cancelar-solo-con-wompi-consultado.md) | Un pedido pendiente se cancela solo después de consultar a Wompi; vence a las 24 horas y hay uno por kit | aceptada | `feature/pagos-wompi-sandbox` |
| [0036](0036-estado-de-compra-calculado.md) | El estado de compra de una solicitud se calcula cruzando pedidos, no se guarda | aceptada | `feature/pagos-wompi-sandbox` |
| [0037](0037-la-curaduria-viaja-por-git.md) | La curaduría de listas y del catálogo viaja por git como CSV | aceptada | `feature/curaduria-de-listas` |
| [0038](0038-el-concepto-asignado-en-la-revision-manda.md) | El concepto asignado en la revisión manda sobre el texto, y su tipo decide si se busca | aceptada | `feature/curaduria-de-listas` |
| [0039](0039-lo-que-no-tiene-precio-no-gana-por-barato.md) | Lo que no tiene precio no gana por barato en el frente, y el coseno no resta en la fusión | aceptada | `feature/atributos-catalogo` |
| [0040](0040-la-lista-que-el-catalogo-no-recibe-se-importa-despues.md) | La lista que el catálogo no recibe se guarda y se importa después, con una clave de idempotencia; el onboarding responde `503` | aceptada | `arreglos/h-b-01-03` |
| [0041](0041-los-procesos-de-fondo-se-recuperan-solos.md) | Los procesos de fondo se recuperan solos de una caída de Postgres o de RabbitMQ; un error de programación los sigue terminando | aceptada | `arreglos/h-b-01-03` |
| [0042](0042-un-evento-da-un-solo-aviso.md) | Un evento da un solo aviso, aunque la bandeja lo entregue otra vez | aceptada | `arreglos/h-b-01-03` |
| [0043](0043-como-se-compara-cada-atributo.md) | Cada atributo se compara a su manera (exacto lo que cambia qué cosa es, con tolerancia lo que se mide), y la cantidad del renglón va en unidad base | aceptada | `feature/integracion-total` |
| [0044](0044-direcciones-con-google-places.md) | La dirección del checkout se autocompleta con Google Places (New), y sin Google sigue siendo un campo libre | aceptada | `feature/maps-and-feats` |
| [0045](0045-alta-de-colegios-no-aliados-desde-la-cola.md) | El staff sube desde la cola la lista de cualquier colegio de Bogotá, con un solo directorio y una regla de logo | aceptada | `feature/maps-and-feats` |
| [0046](0046-las-colas-viajan-por-rabbitmq.md) | Los eventos y los trabajos viajan por RabbitMQ, y la base queda como respaldo: cada productor publica su bandeja y ningún consumidor lee la base de otro | aceptada | `feature/colas-rabbitmq` |
| [0047](0047-redis-guarda-lo-que-se-recalcula-y-cuenta-el-limite.md) | Redis guarda lo que se puede recalcular (la lectura aceptada de una lista y el vector de cada renglón) y cuenta el límite de tasa del gateway, y sin él todo sigue como antes salvo el límite, que cuenta en memoria | aceptada | `feature/cache-redis` |
| [0048](0048-la-supresion-del-titular-viaja-por-evento.md) | El inventario del titular se lee por HTTP con su propio token y la supresión viaja por `titular_suprimido`; cada servicio confirma y la solicitud solo se cierra cuando confirman los tres | aceptada | `oe5-privacidad` |
| [0049](0049-direccion-con-openstreetmap-sin-llave-de-google.md) | Sin llave de Google, la dirección se busca en OpenStreetMap (Nominatim detrás de un proxy, sin autocompletar por tecla) y se confirma en un mapa; las coordenadas sí se guardan | aceptada | `fix/direccion-osm` |

## Para incorporarlos

1. Copiar cada archivo a `Arquitectura/adr/` con el mismo nombre.
2. Agregar su fila a la tabla del §4 de `Arquitectura/ARQUITECTURA.md` con estado `aceptada`.
3. Borrar esta carpeta en una rama que solo haga eso, para que la historia diga cuándo pasó.
