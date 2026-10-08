# ADR 0031 — El acudiente cancela sus solicitudes y quita o cambia de colegio a sus hijos

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `inteligencia` (estado `cancelado`, migración `9e3a5f7b2c41`, `trabajos`, `api`, `remoto`), `catalogo` (`/interno/listas-por-contacto/{id}/retirar`), `identidad` (`/v1/cuenta/matriculas/{id}`), contrato TS, `apps/web` (panel)

## Contexto

Desde su panel, el acudiente no podía deshacer nada: una solicitud quedaba ahí para siempre,
aunque se hubiera equivocado de grado, y un hijo registrado con el colegio equivocado no se
podía corregir ni quitar.

Al pedirlo, el autor del proyecto dejó dos requisitos: cancelar una solicitud y poder borrar a
un hijo o cambiarle el colegio.

## Decisión

**Cancelar una solicitud**

- El trabajo pasa a un estado nuevo, `cancelado`. Es terminal y se alcanza desde todos los
  estados salvo `procesando`, porque cancelar mientras el pipeline escribe dejaría el trabajo a
  medias. Deja de salir en "Mis solicitudes".
- No se cancela una solicitud cuyo kit ya se compró (`kit_comprado`), ni una con un pedido
  pendiente de pago (`pedido_pendiente`): primero se cancela el pedido, que es lo que consulta a
  la pasarela antes de soltarlo (§9.3). Inteligencia le pregunta a Comercio los pedidos del
  acudiente. Si Comercio no responde, no se cancela a ciegas (503).
- Solo el dueño cancela: la ruta exige sesión y compara el `usuario_id` del token.
- Una lista subida (en el Catálogo) **no se borra**. Es una lista oficial del colegio y alguien
  la puede curar igual. Solo se le quita el `contacto_referencia` del acudiente: deja de salir en
  su panel y, al aprobarse, no le arma un kit (el poller exige contacto). Si el trabajo
  cancelado salió de una lista subida, esa lista también se desvincula; si no, volvería a
  aparecer como "recibida".

**Quitar o cambiar de colegio a un hijo**

- Quitar **no borra datos**: cierra el vínculo del acudiente (`vigente_hasta`) y, si nadie más
  lo tiene, retira la matrícula (`retirada`, `cerrado_en`). Es como el esquema distingue "se
  fue" de "nunca estuvo", y es lo que consulta la política de retención de datos de menores.
- Cambiar de colegio o de grado retira la matrícula vieja y crea la nueva con el mismo apodo,
  en una sola transacción: un colegio sin sede o un grado inválido (422) no toca nada. Una
  matrícula es (estudiante, sede, grado, año), así que otro colegio es otra matrícula.
- La lista de hijos del acudiente trae el `matricula_id` (no el del estudiante), para poder
  pedir el cambio.
- Volver a agregar un hijo quitado reactiva su matrícula y su vínculo. Antes, la derivación del
  id caía en la fila retirada y el hijo no volvía a aparecer.

## Alternativas rechazadas

- **Borrar el trabajo cancelado.** Se pierde el rastro de lo que el acudiente pidió y de lo que
  se revisó; `cancelado` lo conserva y lo saca de la vista.
- **Borrar la lista subida.** Es una lista oficial del colegio, útil para el siguiente acudiente.
- **Cancelar el pedido pendiente junto con la solicitud.** Cancelar un pedido consulta la
  pasarela y puede fallar con un pago en curso; mezclarlo con cancelar la solicitud esconde ese
  fallo. Se le pide al acudiente que lo cancele primero, con el mensaje exacto.
- **Editar la matrícula en sitio al cambiar de colegio.** Rompería la derivación de ids y el
  historial de en qué colegio estuvo el hijo.

## Consecuencias

- La cola del admin puede mostrar trabajos cancelados (el resumen por estado los cuenta), pero
  no se pueden aprobar: `cancelado` es terminal.
- Las solicitudes y los pedidos de un hijo quitado siguen ahí.
- Cambiar de colegio no mueve las solicitudes viejas: quedan con el colegio de entonces.
