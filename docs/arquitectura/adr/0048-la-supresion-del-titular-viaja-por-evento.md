# ADR 0048: el inventario del titular se lee por HTTP y la supresión viaja por evento

- **Estado:** aceptada
- **Servicios tocados:** `libs/py/tukit_comun` (`supresion`, `topologia`), `identidad`
  (`remoto`, `publicador`, `supresion`, la bandeja y su migración `b7d4e1f20a93`), `comercio`,
  `operacion` e `inteligencia` (`supresion`), `gateway` (`limite`)
- **Origen:** el panel de privacidad del acudiente (`/privacidad`), en la rama `oe5-privacidad`.
  Aplica la Ley 1581 de 2012 (arts. 8 y 15) y se monta sobre el ADR 0046 (RabbitMQ).

## Contexto

Los datos del titular no viven solo en Identidad. Comercio guarda una copia congelada del envío
(destinatario, dirección, teléfono, documento). Operación guarda el texto libre de sus PQRS.
Inteligencia guarda las preferencias derivadas de su encuesta y el archivo de la lista que subió.
Un panel que muestra y borra solo lo de Identidad le dice al titular algo falso, y si la supresión
no llega a las otras tres bases, el borrado que exige la ley queda incompleto.

Hay dos operaciones con necesidades distintas:

- **Ver y exportar** ("¿qué tienen de mí?") es una lectura síncrona: el titular espera la respuesta.
- **Suprimir** es una escritura en cuatro bases que no comparten transacción, y no puede quedar
  marcada como hecha si una de ellas no la hizo. El servicio anterior cometía justo ese error.

Además, el grafo de dependencias apunta hacia Identidad, nunca al revés (`test_fronteras`): Comercio,
Operación e Inteligencia llaman a Identidad; Identidad no llama a nadie.

## Decisión

1. **El inventario se lee por HTTP, con el token del propio titular.** `tukit_identidad.remoto`
   llama a `mis-pedidos` (Comercio), `mis-casos` (Operación) y `/v1/trabajos` (Inteligencia) con el
   Bearer del titular, y cada sección baja a `{"disponible": false}` si su servicio no responde. Es
   la única arista Identidad → otro servicio, es de solo lectura y usa endpoints que el titular ya
   puede llamar por la puerta: no abre ningún permiso nuevo ni lee otra base.
2. **La supresión viaja por evento, con confirmación de vuelta.**
   - `suprimir_titular` anonimiza lo de Identidad, crea la `solicitud_supresion` en `propagando` y
     escribe `titular_suprimido` en su bandeja, todo en una transacción.
   - La bandeja de Identidad pasa a la forma común (`tipo`, `agregado_tipo`, `agregado_id`) y gana
     su publicador (`tukit_identidad.publicador`), como los demás.
   - Hay tres colas nuevas atadas a `titular_suprimido`: `comercio.supresion`,
     `operacion.supresion` e `inteligencia.supresion`. Cada servicio borra o enmascara lo suyo y,
     en la misma transacción, escribe `supresion_confirmada` en su propia bandeja.
   - Identidad consume las confirmaciones de `identidad.supresion` y aplica
     `SolicitudSupresion.confirmar`. La solicitud pasa a `completada` (con `resuelto_en`) solo
     cuando confirmaron los tres.
3. **Lo que la ley obliga a conservar se conserva.** Se quedan los pedidos, las líneas, los pagos,
   el historial (ET art. 632, C.Co. art. 60, Ley 1480 arts. 7 y 47), y el estado y las fechas de
   los casos (Ley 1581 art. 17). Los `usuario_id` se quedan como referencia seudónima: en Identidad
   ya no resuelven a nadie.
4. **Todo es idempotente.** Enmascarar lo enmascarado deja la base igual, la confirmación no se
   escribe dos veces y `confirmar` no repite un servicio. Una confirmación tardía no reabre ni
   cambia la fecha de una solicitud cerrada.

## Alternativas descartadas

- **Endpoint de confirmación en Identidad.** Invierte el grafo, porque Comercio tendría que llamar
  a Identidad por una ruta interna que hoy no tiene autenticación de servicio. Y pierde la garantía
  del outbox: el borrado y la confirmación ya no irían juntos.
- **Identidad llama por HTTP a un `DELETE` en cada servicio.** Es síncrono contra tres servicios.
  Si uno está caído, la solicitud falla o hay que construir reintentos que la bandeja ya da.
- **Respaldo sin broker (sondear la bandeja de Identidad).** Agregaría tres lecturas cruzadas
  nuevas al manifiesto. Con este ADR la supresión solo viaja con RabbitMQ: sin broker, la
  solicitud se queda en `propagando`, lo cual es cierto y visible, en vez de marcarse completada.

## Consecuencias

- Hay cinco procesos más con broker: `publicador-identidad` y `supresion-{comercio, operacion,
  inteligencia, identidad}`. `make arriba` los lanza y `make abajo` los detiene.
- **La migración `b7d4e1f20a93` renombra columnas de `identidad.bandeja_salida`.** Una fila con un
  `clave_agregado` que no sea un uuid la hace fallar a propósito.
- **Sin broker, la supresión local se hace y la propagación espera.** El panel lo muestra en
  `propagando`.
- **Pendiente:** un barrido que pase a `fallida` la solicitud que lleve demasiado tiempo en
  `propagando`, y que lo avise al equipo.
