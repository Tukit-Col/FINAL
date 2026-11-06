# ADR 0025. Tiempo real: SSE para el progreso del acudiente, WebSocket para la colaboración del admin

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Objetivos afectados:** OE2 (comunicación en tiempo real), OE3 (experiencia del acudiente y del
  curador), OE4 (que el gateway no bufferice streams)
- **Relacionada con:** ADR 0022/0024 (el progreso del trabajo nace de las transiciones de estado que
  ya viajan por el outbox), ADR 0001 (el gateway como pieza aparte de los seis servicios de dominio; el
  manifiesto lo declara "sin dominio y sin base" — invariante que esta decisión respeta)

## Contexto

Hoy el frontend descubre los cambios por *polling*: `sondear()` (`apps/web/api-navegador.ts:180-211`)
re-consulta el estado del trabajo en intervalo fijo. Funciona, pero tiene el costo del polling —
latencia hasta el siguiente tick, y peticiones que casi siempre devuelven "sin cambios". Hay dos
necesidades de tiempo real, y **son distintas en forma, no solo en grado**:

1. **Progreso del trabajo hacia el acudiente.** Un flujo **unidireccional** servidor→cliente: el
   pipeline avanza (`encolado`→`procesando`→…→`publicado`) y el acudiente quiere verlo sin recargar.
   El cliente no envía nada; solo escucha.

2. **Colaboración en la consola de revisión del admin.** Es **bidireccional**: varios curadores sobre
   la misma cola necesitan presencia (quién está viendo qué), bloqueo advisory de la línea que alguien
   edita, y refresco en vivo de la cola. El cliente emite tanto como recibe.

Meter ambas por el mismo transporte fuerza el patrón más pesado sobre el caso más simple, o el más
simple sobre el caso que no le alcanza.

## Decisión

**Dos transportes, uno por forma de comunicación: SSE para el progreso unidireccional, WebSocket
(socket.io) para la colaboración bidireccional.**

### SSE para el progreso del acudiente

- **Inteligencia** expone `GET /v1/trabajos/{id}/eventos` (`text/event-stream`), alimentado por las
  transiciones de estado del trabajo que ya viajan por el outbox (ADR 0022/0024). `id:` monotónico para
  que el navegador reanude con `Last-Event-ID` tras una desconexión. Cierra en `publicado`/`fallido`.
  Emite el **mismo shape `Trabajo`** que el poll — no un contrato nuevo.
- **El gateway hace passthrough en streaming.** Hoy `reenviar` (`gateway/api.py:221-229`) lee
  `respuesta.content` — bufferiza el cuerpo entero, con lo que un stream nunca haría flush y el SSE
  llegaría de golpe al cerrarse, no en vivo. Se cambia a `StreamingResponse` cuando el upstream es
  `text/event-stream`. Esto **respeta el invariante del gateway** (ADR 0001, manifiesto): sigue sin
  dominio y sin base, solo deja de bufferizar un tipo de cuerpo que no debe bufferizar.
- **El polling se conserva como degradación honesta.** `sondear()` no se borra: el hook
  `usarEventosTrabajo` cae a `sondear()` cuando `EventSource` está en `CLOSED`. SSE es el camino
  rápido; el poll, la red de seguridad. Coherente con la degradación honesta que ya practica el sistema
  (ADR 0020).

### WebSocket (socket.io) para la colaboración del admin

- Namespace `/revision`, sala por `trabajo:{id}` y sala `cola`. Auth con **JWT en el handshake**,
  validado contra `/v1/sesiones/actual`. Mensajes tipados (al paquete de contrato compartido):
  `presencia:entra/sale`, `bloqueo:pedir/soltar/negado`, `invalidar:{queryKey}`.
- **El WebSocket no pasa por el gateway HTTP.** El endpoint socket.io vive **al lado** del gateway, en
  su propio origen; el admin conecta directo con su JWT. El gateway se mantiene fiel a su invariante
  (sin estado, sin conexiones de larga vida); el WS, que es intrínsecamente con estado y de larga vida,
  no lo contamina.
- **El bloqueo de edición es advisory + respaldo de concurrencia optimista.** El lock por WS (con TTL,
  liberado en `disconnect`) evita que dos curadores editen la misma línea a la vez en el caso normal;
  pero como es un camino de **posible pérdida de datos**, la mutación lleva además un *version token*
  que rechaza el guardado si otro lo cambió primero. El WS da la buena UX; el version token da la
  garantía. No se confía la integridad a un lock advisory.

## Consecuencias

**A favor.** Cada caso usa el transporte de su forma: el acudiente recibe progreso push sin el peso de
un socket bidireccional; el admin obtiene presencia y bloqueo reales. El gateway se mantiene puro (ADR
0013) porque el WS lo evita y el SSE solo deja de bufferizarse. El progreso reusa el shape `Trabajo` y
el outbox existentes; no hay contrato nuevo para el caso simple. El polling sobrevive como red de
seguridad.

**En contra.** Dos tecnologías de tiempo real en vez de una, y una dependencia nueva (socket.io). Se
acepta porque unificar forzaría WebSocket sobre el caso unidireccional (más complejo de lo necesario en
cliente y servidor) o SSE sobre el bidireccional (que no puede recibir del cliente). La forma manda.

**Deuda que se declara.** El estado de presencia/bloqueo del WS arranca **en memoria de un proceso**
(un solo proceso admin). El adaptador Redis (`@socket.io/redis-adapter`) queda *stubbeado* detrás del
in-memory con un `ponytail:` que nombra el techo: cuando el backend admin escale a más de un proceso,
se conecta el adaptador Redis sin tocar los handlers.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Solo polling** (lo de hoy) | Funciona pero paga latencia y peticiones vacías; no da presencia ni bloqueo colaborativo, que el caso del admin sí necesita. |
| **WebSocket para todo** | Impone un socket bidireccional con estado sobre el progreso del acudiente, que es puro servidor→cliente. Más complejo en ambos extremos sin beneficio; y SSE reanuda con `Last-Event-ID` gratis. |
| **SSE para todo** | SSE no puede recibir del cliente; la colaboración del admin (presencia, pedir bloqueo) es intrínsecamente bidireccional. No alcanza. |
| **WebSocket a través del gateway** | Contamina el gateway con conexiones de larga vida y estado, rompiendo su invariante "sin dominio y sin base" (ADR 0001). El WS al lado, en su propio origen, mantiene el gateway puro. |
| **Bloqueo solo advisory** (sin version token) | Un lock advisory que se pierde en un `disconnect` mal manejado permite doble edición y pérdida de datos. El version token es el respaldo que hace la integridad no-negociable. |
