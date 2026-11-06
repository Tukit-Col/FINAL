# ADR 0021. Observabilidad: trazas OpenTelemetry, logs atados al correlation-ID y readiness distinta de liveness

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (operabilidad), OE4 (diagnóstico en producción)
- **Relacionada con:** ADR 0007 (los eventos que cruzan el broker deben arrastrar el hilo de la
  petición), ADR 0020 (las métricas del cortacircuitos)

## Contexto

El **correlation-ID ya está implementado y en producción** —no es trabajo pendiente—: un contextvar
de módulo (`tukit_comun/http.py:57-60`), un middleware por petición que lo lee de `x-correlation-id`
o acuña un `uuid4` y lo eco de vuelta (`:185-198`), y propagación saliente aditiva en
`cliente_efimero` (`:127-128`). Una petición que atraviesa gateway → inteligencia →
catálogo/identidad/comercio arrastra el mismo id por toda la cadena, y el gateway es el punto de
acuñado de entrada.

Sobre esa base sólida quedan tres huecos:

1. **El correlation-ID no está atado a las líneas de log.** Existe en el contextvar, pero un log
   estructurado no lo incluye salvo que cada `logger.info` lo pase a mano. El id sirve para amarrar la
   cadena solo si aparece en cada línea sin esfuerzo.
2. **No hay trazas ni métricas.** No se puede ver una petición como un árbol de spans a través de los
   servicios, ni medir tasas y latencias por endpoint. El log y `/v1/servicios` cubren lo básico,
   pero no una topología.
3. **La sonda de salud no distingue "vivo" de "listo".** `GET /salud` responde `ok` mientras el
   proceso corra, aunque la base esté caída o las migraciones sin aplicar. Un orquestador que use eso
   para decidir enrutar tráfico mandará peticiones a un servicio que no puede servirlas.

## Decisión

**Se completa la historia de observabilidad sobre el correlation-ID existente, instrumentando en el
factory compartido `crear_app` para que los seis servicios lo hereden de golpe.**

1. **Logs estructurados atados al correlation-ID.** Un `logging.Filter` nuevo en
   `tukit_comun/registro.py` (stdlib, ~15 líneas, sin dependencia nueva) que lee
   `id_de_correlacion()` (`http.py:63`) e inyecta el campo `correlacion` en cada línea JSON.
   `crear_app` llama `configurar_registro(titulo)`. A partir de ahí, todo log de toda petición trae
   su hilo sin que nadie lo pase a mano.

2. **OpenTelemetry para trazas y métricas.** Instrumentación automática en `crear_app`
   (`FastAPIInstrumentor` y `HTTPXClientInstrumentor`, que propaga `traceparent` W3C **junto** al
   correlation-ID) y `SQLAlchemyInstrumentor` en cada `_arrancar` tras `crear_motor`. El exportador
   OTLP se lee del entorno (`OTEL_EXPORTER_OTLP_ENDPOINT`) y es **no-op si no está configurado**,
   igual que `WOMPI_MODO=falso` deja la pasarela en simulación: la instrumentación no impone un
   colector en desarrollo ni en la demostración académica. Métricas de dominio:
   `tukit.ordenes.creadas`, `tukit.pagos.aprobados`, `tukit.trabajos.publicados`, y el gauge
   `tukit.breaker.abierto` de la ADR 0020.

3. **Correlation-ID a través del outbox.** Se persiste `correlacion_id` dentro de la `carga` del
   evento (en `_publicar_evento` y en el insert del webhook) y se **re-bindea** en el drenador
   compartido (`tukit_comun/bandeja.py`, ADR 0022) antes de manejar cada evento. Así el trabajo
   asíncrono que dispara un evento conserva el hilo de la petición que lo originó, que hoy se pierde
   en la frontera síncrono→asíncrono. El span de la traza lleva el atributo `tukit.correlacion_id`,
   que enlaza log y traza.

4. **Liveness distinta de readiness.** Se conserva `GET /salud` como alias de liveness y se añaden en
   `crear_app` dos sondas: `GET /health/live` (el proceso corre) y `GET /health/ready` (la base
   responde a `SELECT 1` —con el `pool_pre_ping` que ya está activo, `bd.py:126`— y el head de Alembic
   coincide; 503 con el detalle de qué falló si no). **El gateway pasa a consultar `/health/ready`**
   en `/v1/servicios`: "todos arriba" deja de significar "el proceso vive" y pasa a significar
   "pueden servir".

## Consecuencias

**A favor.** Un fallo se sigue de punta a punta: la traza da el árbol de spans, el log filtra por
`correlacion`, y ambos comparten el mismo id incluso a través del outbox. El readiness permite a un
orquestador no enrutar tráfico a un servicio que arrancó pero no puede servir. Todo se hereda del
factory compartido, sin tocar cada servicio.

**En contra.** OpenTelemetry añade dependencias (`opentelemetry-*`) y un pequeño costo por span. Se
acota con el exportador no-op: en desarrollo y en la demo no hay colector ni overhead de red, solo la
creación local de spans, que es barata.

**Deuda que se declara.** El colector OTLP (Tempo/Jaeger + Prometheus, o un backend equivalente) es
infraestructura de despliegue que esta decisión habilita pero no monta; queda como trabajo de la
puesta en producción, no del diseño.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Solo el correlation-ID en logs** (sin OTel) | Da trazabilidad textual pero no el árbol de spans ni métricas de latencia por endpoint. El id ya existe; OTel es el complemento que faltaba. |
| **Instrumentar servicio por servicio a mano** | Repite en seis lugares lo que el factory compartido hace una vez, y se desincroniza. |
| **Una sola sonda `/salud`** (lo de hoy) | No distingue vivo de listo; un orquestador enruta tráfico a un servicio que no puede servirlo. |
| **APM propietario** (Datadog, New Relic) | OpenTelemetry es el estándar abierto y no ata la tesis a un proveedor; el exportador OTLP habla con cualquier backend. |
| **Pasar el correlation-ID a mano en cada log** | Ruido en cada llamada y se olvida justo donde importa. El `logging.Filter` lo hace invisible y total. |
