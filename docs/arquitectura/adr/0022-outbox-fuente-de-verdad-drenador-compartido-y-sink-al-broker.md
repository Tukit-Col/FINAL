# ADR 0022. El outbox es la fuente de verdad; un drenador compartido lo entrega a un sink intercambiable (notificador hoy, broker mañana)

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (backbone de eventos entre servicios), OE4 (entrega confiable)
- **Extiende:** ADR 0007 (un solo broker de mensajería, RabbitMQ) — esta decisión define *cómo* los
  servicios alimentan ese broker sin reintroducir el doble-escritura, y hace que el broker sea un
  destino intercambiable en vez del punto de acoplamiento.
- **Relacionada con:** ADR 0021 (el drenador es el punto único donde se re-bindea el correlation-ID)

## Contexto

El patrón outbox transaccional ya está bien implementado y es el corazón sano del sistema: el evento
se escribe **en la misma transacción** que el cambio de estado que lo origina (`_publicar_evento` en
`inteligencia/trabajos.py:1005`, el insert del webhook en `comercio/api.py`), de modo que no existe la
ventana de doble-escritura donde el estado se guarda pero el evento se pierde (o al revés). Un poller
por servicio drena la tabla y entrega. **Esto no se cambia: es exactamente el bug que el outbox
arregla, y arreglarlo de otro modo sería un retroceso.**

Hay dos problemas, y ninguno es el outbox en sí:

1. **La lógica de drenaje está triplicada**, con divergencias sutiles: `operacion/repartidor.py:125`,
   `identidad/poller.py:112`, `inteligencia/poller.py:96`. Cada una re-implementa la reflexión de la
   tabla replicada, el `SELECT … FOR UPDATE SKIP LOCKED`, y el marcar-publicado/incrementar-intentos.
   Tres copias es tres lugares donde arreglar un bug y tres lugares donde el span de traza y el re-bind
   del correlation-ID (ADR 0021) tendrían que repetirse.

2. **La entrega es solo por *polling* a un único consumidor (el notificador).** No hay push
   sub-segundo, ni fan-out a varios consumidores, ni *replay*. La ADR 0007 ya decidió que el broker
   sería RabbitMQ; lo que falta es el camino que lleva del outbox al broker sin acoplar el productor al
   transporte.

## Decisión

**Se extrae un drenador compartido y se le pone detrás un `Sink(Protocol)` intercambiable. El outbox
sigue siendo la fuente de verdad; el broker de la ADR 0007 se convierte en un sink más, no en el
centro.**

1. **Drenador compartido `tukit_comun/bandeja.py`.** Una función
   `drenar(motor, manejar, *, limite)` que consolida las tres copias: refleja la tabla replicada (como
   `repartidor.py:59-81`), hace `SELECT … FOR UPDATE SKIP LOCKED` (dos drenadores nunca toman la misma
   fila), invoca `manejar(evento)`, y marca publicado o incrementa intentos. Extracción segura entre
   fronteras: la tabla reflejada es la *replicada*, idéntica por diseño en los tres servicios. Es el
   único lugar donde vive el span OTel del drenaje y el re-bind del correlation-ID (ADR 0021).

2. **`Sink(Protocol)` como costura de entrega.** El drenador entrega a un sink, no a un transporte
   concreto (la costura ya existe en `repartidor._entregar`, `:134-159`):
   - **`NotifierSink`** — el consumidor de hoy, se conserva.
   - **`BrokerSink` (RabbitMQ, `aio-pika`)** — publica el evento al broker de la ADR 0007; los
     consumidores (notificador, y los futuros de la saga) consumen de sus colas/exchanges. El *routing
     key* es el tipo de evento; RabbitMQ hace el fan-out y las DLQ.

3. **El outbox nunca desaparece.** El broker es un *upgrade de entrega* (push, fan-out, replay),
   **no** un cambio de arquitectura. Incluso con el broker en línea, el evento se escribe primero al
   outbox en la transacción de negocio y el drenador lo publica después: si el broker está caído, el
   evento espera en el outbox y se entrega cuando vuelva. Esto es lo que hace que "exactamente una vez
   desde el punto de vista del negocio" sea cierto sin coordinación distribuida.

## Consecuencias

**A favor.** Una sola implementación de drenaje —un lugar para el bug, el span y el correlation-ID—.
El productor no sabe si detrás hay un notificador o un broker: cambiar de uno a otro es cambiar el
sink inyectado, no tocar la lógica de negocio. Se habilita el push sub-segundo y el fan-out de la ADR
0007 sin sacrificar la garantía del outbox. La saga (ADR 0023) y el pipeline durable (ADR 0024) se
montan sobre esta misma tubería.

**En contra.** Una dependencia nueva (`aio-pika`) y una pieza de infraestructura que operar
(RabbitMQ, ya asumida por la ADR 0007). El `BrokerSink` añade un salto de red entre el drenador y el
consumidor; se acepta porque el outbox absorbe la caída del broker sin perder eventos.

**Deuda que se declara.** El drenador sigue siendo *at-least-once*: un evento puede entregarse dos
veces si el proceso muere entre publicar y marcar-publicado. Por eso los consumidores deben ser
idempotentes (ADR 0020, idempotencia de aplicación) — no se busca *exactly-once* de transporte, que es
un problema imposible; se busca *effectively-once* por idempotencia del consumidor.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Publicar al broker directamente desde el handler** (sin outbox) | Reintroduce el doble-escritura: el cambio de estado y el publish al broker no comparten transacción, así que un crash entre ambos pierde o duplica. El outbox existe precisamente para cerrar esa ventana. |
| **Dejar las tres copias del poller** | Tres lugares donde arreglar cada bug y repetir el span + correlation-ID. La tabla replicada es idéntica por diseño; no hay razón para tres implementaciones. |
| **Broker como fuente de verdad** (event sourcing puro) | Convierte al broker en dependencia dura de la corrección, no solo de la latencia. Con el outbox como verdad, el broker puede caerse sin perder un evento. |
| **Kafka en vez de RabbitMQ** | Ya resuelto en la ADR 0007: el routing por topic/DLQ de RabbitMQ encaja con la mezcla comando/evento de la saga a escala de seis servicios; Kafka es log-replay para millones/s que aquí no aplican. |
| **Sink acoplado** (el drenador conoce RabbitMQ) | Ata la lógica de drenaje al transporte; el `Protocol` la mantiene testeable con un sink en memoria y permite volver al notificador puro si hiciera falta. |
