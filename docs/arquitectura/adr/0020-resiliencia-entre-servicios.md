# ADR 0020. Resiliencia entre servicios: cortacircuitos y mamparos por destino, reintentos solo en lecturas idempotentes

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (comunicación entre servicios), OE4 (disponibilidad bajo fallo parcial)
- **Relacionada con:** ADR 0007 (broker), ADR 0011 (el webhook idempotente de Wompi es el patrón de
  idempotencia de escritura que aquí se generaliza)

## Contexto

La comunicación entre servicios ya trae lo caro de hacer bien: **timeouts por llamador** (cada
`remoto.py` fija su propio `ESPERA_SEGUNDOS`, no un global —60 s en inteligencia, 30 s en comercio,
300 s en el gateway porque detrás hay un pipeline de minutos) y **degradación honesta** (los
`remoto.py` devuelven `None` cuando la dependencia opcional no responde; el cliente de Comercio pasa
los rechazos de negocio como `(estado, cuerpo)` y solo levanta en 5xx/red; en el cobro, Catálogo
caído es 503, nunca un cobro a ciegas).

Lo que falta son los tres patrones que evitan que un fallo parcial se vuelva total: **no hay
reintentos**, **no hay cortacircuitos** y **no hay aislamiento de recursos** (un destino lento puede
agotar las conexiones que otro necesita). A escala de piloto esto rara vez muerde, pero un sistema
que aspira a operar como negocio no puede depender de que el fallo nunca llegue.

Hay una trampa específica que el diseño debe respetar: **un reintento ciego sobre una escritura es el
modo de falla más caro del negocio.** Reintentar un `POST /v1/ordenes` es un doble cobro; reintentar
un `POST /v1/contactos` es un efecto lateral duplicado. El `CONTRATO_API.md §9` lo marca
explícitamente.

## Decisión

**Se añaden cortacircuitos, mamparos y reintentos, envueltos en un solo ayudante compartido
`tukit_comun/resiliencia.py`, con una regla dura: la resiliencia de transporte solo aplica a las
lecturas idempotentes; las escrituras se protegen por idempotencia de aplicación.**

El ayudante expone un context manager `llamada_protegida(destino, *, reintentable=False)` que compone
tres piezas:

1. **Cortacircuitos por destino.** Uno por cada servicio-destino (`catalogo`, `identidad`,
   `comercio`, `wompi`), con un `Disyuntor` **propio** (~40 líneas puras en `tukit_comun.resiliencia`,
   se usa con `async with` como el `cliente_efimero` que ya existe, con el estado in-memory y el
   almacén intercambiable a Redis sin tocar el llamador). Se implementó propio en vez de
   `purgatory-circuitbreaker` porque esa librería arrastra `pkg_resources`/`setuptools` —ya deprecado—
   por 40 líneas de lógica trivial (contar fallos, abrir, medio-abrir tras un tiempo). Umbrales
   generosos: abre a los 5 fallos, prueba de nuevo a los 30 s.
   Un destino caído deja de recibir llamadas que de todos modos fallarían, y el llamador recibe el
   fallo de inmediato en vez de esperar el timeout completo.

2. **Mamparos por *pool*.** Un `httpx.AsyncClient` de vida larga por (servicio, destino) en
   `app.state.remotos`, con `httpx.Limits` explícito. El límite de conexiones de un destino es la
   frontera del mamparo: un Catálogo lento no puede agotar las conexiones que el llamador necesita
   para hablar con Identidad. El `cliente_efimero(cliente, espera)` que ya existe (`http.py:106`) se
   conserva —sigue siendo el path inyectado en pruebas y el que propaga el correlation-ID—; el
   `remoto.py` le pasa el cliente del *pool* en producción.

3. **Reintentos con *backoff*, solo en GET idempotentes.** Con `tenacity`, y `reintentable=True`
   **permitido únicamente en lecturas** (`ClienteCatalogo.emparejar/listas/lista/producto`). El
   ayudante **rechaza en tiempo de programación** un método no-GET marcado `reintentable=True`: es un
   error de uso, no una opción. Las escrituras nunca reintentan a nivel transporte.

**Las escrituras se protegen por idempotencia de aplicación**, generalizando el patrón que el webhook
de Wompi ya usa (`comercio.evento_pasarela_procesado`, `api.py:559-607`): una clave —`Idempotency-Key`
de cabecera o clave natural del evento— y una tabla de deduplicación, de modo que una escritura
repetida es un no-op verificable, no un doble efecto.

## Consecuencias

**A favor.** Un fallo parcial deja de propagarse: el cortacircuitos corta la cascada, el mamparo
contiene el agotamiento de recursos, y el reintento recupera las lecturas transitorias sin arriesgar
las escrituras. La degradación honesta que ya funciona no se toca —se le añade abajo la maquinaria
que la hace resistente bajo carga.

**En contra.** Una dependencia nueva (`tenacity`; el cortacircuitos es propio, sin dependencia) más
el *pool* de larga vida, y estado por destino que hay que observar (el gauge `tukit.breaker.abierto` de la ADR
0021 existe para eso). Un cortacircuitos mal calibrado puede abrir de más; por eso los umbrales
arrancan generosos y se ajustan con la métrica, no a ciegas.

**Deuda que se declara.** El backend del cortacircuitos arranca en memoria (por proceso). Cuando haya
más de una réplica por servicio, el estado del cortacircuitos debe compartirse por Redis para que
todas las réplicas vean el mismo destino como caído; el cambio es de configuración, no de código, por
eso el `Disyuntor` se escribió con el almacén de estado intercambiable.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Reintentos genéricos en todas las llamadas** | Reintentar una escritura es un doble cobro. La regla dura GET-only es el punto entero de esta decisión. |
| **Un cortacircuitos global** | Un destino caído abriría el circuito para todos los destinos. El aislamiento por destino es lo que convierte un fallo parcial en degradación parcial. |
| **Malla de servicios** (Istio/Linkerd) | Resuelve esto a nivel de infraestructura, pero es un componente pesado para seis procesos en minikube; el costo operativo no lo justifica al volumen del piloto. |
| **Escribir el cortacircuitos a mano** | Es un patrón sutil (half-open, ventana de fallos, backend compartible) que una librería madura ya resuelve. Reescribirlo es más código y más bugs. |
| **Solo timeouts** (lo de hoy) | Los timeouts evitan colgarse pero no evitan la cascada ni el agotamiento de conexiones bajo un destino lento. |
