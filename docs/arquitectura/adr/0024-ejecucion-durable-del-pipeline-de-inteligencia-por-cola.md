# ADR 0024. La ejecución del pipeline de Inteligencia es durable: cola con SKIP LOCKED, no `asyncio.Task` en proceso

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Objetivos afectados:** OE2 (orquestación del pipeline), OE3 (que ningún trabajo se pierda), OE4
  (recuperación ante caída de proceso)
- **Concreta:** ADR 0018 (orquestación durable del pipeline con máquina de estados; LangGraph diferido)
  — aquella decidió *que* la ejecución debe ser durable y con estado persistido; ésta decide *cómo* con
  lo que ya existe, retirando el `asyncio.Task` que hoy la hace efímera.
- **Relacionada con:** ADR 0022 (reusa el mismo drenador `SKIP LOCKED`), ADR 0019 (el pipeline puro se
  separa de la ejecución)

## Contexto

La ADR 0018 ratificó que el pipeline de Inteligencia (emparejamiento → optimización → curación →
publicación) debe orquestarse de forma **durable**, con el estado persistido en una máquina de estados,
para poder retomar y auditar. El código todavía no cumple esa decisión en su parte más crítica: el
lanzamiento del trabajo.

`inteligencia.lanzar` (`trabajos.py:993-1002`) arranca el pipeline con
`asyncio.create_task(procesar(...))` — una corrutina en el mismo proceso. **Su propio docstring lo
admite**: si el servicio se cae mientras un trabajo corre, ese trabajo queda en estado `procesando`
para siempre, sin nadie que lo retome. No hay reintento, no hay otro worker que lo recoja, no hay
rastro de que se interrumpió. El estado se persiste (bien, como pide 0018), pero la *ejecución* que lo
mueve es efímera, así que el estado persistido se queda congelado en el punto del crash.

Esto contradice directamente la ADR 0018 y es el único punto del sistema donde una caída de proceso
causa pérdida silenciosa de trabajo del usuario.

## Decisión

**El lanzamiento deja de ser `asyncio.create_task` y pasa a ser una fila durable, drenada con el mismo
mecanismo `SELECT … FOR UPDATE SKIP LOCKED` que ya usa el outbox (ADR 0022).**

1. **`lanzar` solo encola.** Escribe el trabajo en estado `encolado` (persistido, transaccional) y
   retorna. No arranca ninguna corrutina de proceso. La respuesta HTTP al acudiente es inmediata,
   igual que hoy.

2. **Un worker drena la cola.** Un drenador —el mismo `bandeja.drenar` de la ADR 0022, o su gemelo
   para la tabla de trabajos— toma trabajos `encolados` con `SKIP LOCKED`, los marca `procesando` y
   ejecuta `procesar`. Si el proceso muere a mitad, la fila sigue ahí: al reiniciar (o desde otra
   réplica), otro worker la retoma. El `SKIP LOCKED` garantiza que dos workers nunca tomen el mismo
   trabajo.

3. **Idempotencia por paso, apoyada en la máquina de estados de 0018.** Retomar un trabajo a medias
   exige que cada paso del pipeline sea idempotente o sepa reanudar desde el último estado persistido.
   Aquí se cobra el trabajo de la ADR 0019: la máquina de estados extraída a `dominio/maquina.py` (pura,
   `puede_pasar(estado, evento)`) dice desde dónde reanudar, y los pasos ya-puros
   (`estado_desde_emparejamiento`, el optimizador) se re-ejecutan sin efecto lateral duplicado.

4. **LangGraph sigue diferido**, como decidió la ADR 0018. Esta ADR **no** introduce un motor de
   orquestación: reusa el drenador que ya existe. Si el grafo del pipeline se vuelve suficientemente
   ramificado como para justificar LangGraph, esa es una decisión futura sobre esta base durable, no un
   requisito de ahora. La cola durable es el piso mínimo que 0018 exige; LangGraph sería el piso
   siguiente.

## Consecuencias

**A favor.** Se cierra el único punto de pérdida silenciosa de trabajo: una caída de proceso deja el
trabajo retomable, no congelado. Cumple la ADR 0018 con infraestructura que ya existe (el drenador
`SKIP LOCKED`), sin dependencia nueva. Habilita escalar horizontalmente el procesamiento: varias
réplicas drenan la misma cola sin coordinación extra. La respuesta al usuario sigue siendo inmediata.

**En contra.** La reanudación exige que cada paso del pipeline sea idempotente/reanudable, lo que es
trabajo real de diseño por paso (no todos los pasos lo son hoy). Se acepta porque es la única forma
honesta de "durable": un pipeline que no puede reanudar no es durable aunque persista su estado.

**Deuda que se declara.** La migración es la más riesgosa del rediseño (ADR 0019 la marca): se hace por
etapas —cosechar lo puro, extraer la máquina de estados, y solo entonces cambiar `lanzar`/`procesar`—
con tests de caracterización golden-path del fast-path y del slow-path *antes* de tocar `procesar`, para
que la red de regresión detecte cualquier cambio de comportamiento.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **Dejar `asyncio.create_task`** (lo de hoy) | Contradice la ADR 0018 y pierde trabajo del usuario en cada caída de proceso. Es el gap que esta ADR existe para cerrar. |
| **Una cola de tareas dedicada** (Celery, RQ, Arq) | Otro componente y otro broker que operar cuando el mecanismo `SKIP LOCKED` sobre Postgres ya está probado en el outbox y da exactamente la durabilidad que se pide. Reusar > añadir. |
| **LangGraph ahora** | La ADR 0018 lo difirió a propósito; el pipeline actual no es tan ramificado como para justificar un motor de orquestación. La cola durable es el piso mínimo; LangGraph, una decisión posterior sobre esta base. |
| **Un solo worker dedicado** (sin `SKIP LOCKED`) | Funciona con una réplica pero no escala y reintroduce un punto único de fallo. `SKIP LOCKED` permite N workers sin coordinación. |
