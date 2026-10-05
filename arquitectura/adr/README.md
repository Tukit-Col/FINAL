# ADR registrados desde el submódulo

Los registros de decisión de arquitectura viven en `Arquitectura/adr/`, fuera de este
repositorio, y su índice es la tabla del §4 de `Arquitectura/ARQUITECTURA.md`. El código los
cita por número (`ADR 0012`, `ADR 0017`…) y los planes de `docs/planes/` los crean allá.

Esta carpeta existe porque esa otra mitad no siempre está a la mano: la rama
`feature/pagos-wompi-sandbox` se trabajó en una máquina sin `Arquitectura/`, y una decisión
que solo vive en un mensaje de commit no es una decisión registrada. Se escriben aquí, en el
mismo formato (Nygard: contexto, decisión, alternativas rechazadas, consecuencias), y se
mueven cuando alguien con el repositorio de la tesis los incorpore.

La numeración **continúa la serie externa**. El número más alto citado en el código al abrir
la rama era el 0020 (formulación del optimizador multiobjetivo), así que estos empiezan en el
0021. Si al incorporarlos el 0021 ya está tomado allá, se renumeran allá y se corrigen las
citas aquí: el número es una etiqueta, el título es la decisión.

| ADR | Decisión | Estado | Origen |
|---|---|---|---|
| [0021](0021-pago-con-widget-de-wompi.md) | El pago se abre con el widget de Wompi, con la configuración por `postMessage` | aceptada | `feature/pagos-wompi-sandbox` |
| [0022](0022-confirmacion-del-pago-por-sincronizacion-y-webhook.md) | El pago se confirma preguntándole a Wompi, y webhook y sincronización comparten un aplicador idempotente | aceptada | `feature/pagos-wompi-sandbox` |
| [0023](0023-cancelar-solo-con-wompi-consultado.md) | Un pedido pendiente se cancela solo después de consultar a Wompi; vence a las 24 horas y hay uno por kit | aceptada | `feature/pagos-wompi-sandbox` |
| [0024](0024-estado-de-compra-calculado.md) | El estado de compra de una solicitud se calcula cruzando pedidos, no se guarda | aceptada | `feature/pagos-wompi-sandbox` |
| [0025](0025-la-curaduria-viaja-por-git.md) | La curaduría de listas y del catálogo viaja por git como CSV | aceptada | `feature/curaduria-de-listas` |
| [0026](0026-el-concepto-asignado-en-la-revision-manda.md) | El concepto asignado en la revisión manda sobre el texto, y su tipo decide si se busca | aceptada | `feature/curaduria-de-listas` |
| [0027](0027-lo-que-tukit-no-vende-se-clasifica.md) | Lo que Tukit decide no vender se clasifica como `otro`, no queda como hueco | aceptada | `feature/curaduria-de-listas` |
| [0028](0028-los-cambios-del-acudiente-viven-en-su-trabajo.md) | Los cambios del acudiente viven en su trabajo, no en las líneas del kit | aceptada | `feature/integracion` |
| [0029](0029-con-presupuesto-se-recomienda-la-mejor-marca-que-cabe.md) | Con presupuesto se recomienda la mejor marca que cabe, tomada del frente | aceptada, reemplazada en parte por 0030 | `feature/mejoras-benchmark-nsga` |
| [0030](0030-solo-se-arman-los-kits-que-se-piden.md) | Solo se arman los kits que el acudiente pide: Ahorrador y Premium siempre, Fan y A tu Medida a pedido | aceptada | `feature/integracion` |
| [0031](0031-el-acudiente-cancela-solicitudes-y-edita-a-sus-hijos.md) | El acudiente cancela sus solicitudes y quita o cambia de colegio a sus hijos | aceptada | `feature/integracion` |
| [0032](0032-la-logistica-de-preview-kits-se-une-sin-su-cola.md) | La logística de `preview-kits` se une a los pagos; su cola y su vista previa no | aceptada | `feature/integracion-total` |

## Para incorporarlos

1. Copiar cada archivo a `Arquitectura/adr/` con el mismo nombre.
2. Agregar su fila a la tabla del §4 de `Arquitectura/ARQUITECTURA.md` con estado `aceptada`.
3. Borrar esta carpeta en una rama que solo haga eso, para que la historia diga cuándo pasó.
