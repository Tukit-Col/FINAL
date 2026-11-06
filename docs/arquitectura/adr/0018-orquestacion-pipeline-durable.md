# ADR 0018. Orquestación del pipeline como trabajos durables, y por qué LangGraph se difiere

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Fecha:** 2026-09-21
- **Decide:** equipo ISIS2610-G19
- **Objetivos afectados:** OE2 (diseño del proceso), OE3 y OE4 (ejecución del pipeline)
- **Relacionada con:** ADR 0010 (la resolución decide sobre el score del reranker),
  ADR 0007 (RabbitMQ como broker único), ADR 0006 (expansión de grafo en proceso)

## Contexto

El corazón de Tukit es un pipeline de cuatro etapas sobre cada ítem de una lista escolar:
**percepción** (interpretar la lista subida), **normalización** (mapear cada renglón contra el
catálogo canónico), **resolución** (decidir si un candidato es la respuesta, dudarlo, o pasarlo
a revisión humana) y **optimización** (armar los kits que balancean precio, calidad y
preferencias). Una lista tiene decenas de ítems y el proceso completo, aun después de cachear
el grafo de sustituibilidad, toma segundos por lista y depende de servicios externos: el
reranker sobre GPU serverless (ADR 0005) y la pasarela para nada aquí, pero sí modelos que
pueden fallar o tardar.

Dos hechos obligan a decidir cómo se orquesta y no dejarlo implícito:

**El proceso se interrumpe a propósito.** La resolución no siempre concluye sola: cuando el
puntaje del reranker cae en la banda de duda (umbrales τ/δ, ADR 0010), el ítem **espera una
decisión humana**. Un pipeline que se interrumpe para esperar a una persona no es una función
que se llama y retorna; es un proceso de larga duración con estado que hay que persistir,
porque entre el momento en que se pide la revisión y el momento en que llega puede pasar un
tiempo arbitrario y el sistema puede reiniciarse en el medio.

**El proceso se cae y hay que reanudarlo sin repetir lo caro.** Si la optimización falla en el
ítem 18 de 20, no tiene sentido volver a correr la percepción y la normalización de los 17
anteriores, que ya estaban resueltos. Repetir es caro (es CPU de modelos) y, peor, no es
idempotente si por el camino se emitieron eventos.

El MVP actual ejecuta el pipeline como `async` secuencial en memoria, sin orquestador. Funciona
para una demostración pero no sobrevive ni a un reinicio ni a una espera humana: el estado vive
en la pila de una corrutina y se pierde con el proceso.

## Decisión

**El pipeline se modela como trabajos durables con estado persistido, reanudables por etapa, y
la transición entre estados —incluida la espera humana— se gobierna con una máquina de estados
auditada por transición.**

Dos tablas en la base de `inteligencia`, ya declaradas en el manifiesto:

```
trabajo_pipeline    el trabajo sobre una lista: a qué matrícula pertenece, estado global
etapa_trabajo       una fila por (trabajo, etapa, intento): estado, entrada, salida, error
```

La unidad de reanudación es la clave **`(trabajo_id, etapa, intento)`**. Al arrancar o
reanudar, el ejecutor busca la última etapa completada de cada ítem y continúa desde la
siguiente; una etapa que falló se reintenta incrementando `intento`, sin borrar el registro del
intento anterior, que queda como evidencia de qué pasó. Una etapa ya completada **no se vuelve a
ejecutar**: su salida persistida es la entrada de la siguiente.

La transición entre estados se modela con una **máquina de estados explícita**
(`python-statemachine`), no con banderas booleanas dispersas. Los estados incluyen la espera
humana como un estado de primera clase (`en_revision`), del que solo se sale por una decisión
registrada. Cada transición se audita —queda quién o qué la disparó y cuándo—, lo que convierte
el HITL en un rastro consultable en vez de un efecto de borde.

La comunicación entre etapas y con el resto del sistema usa el broker único (ADR 0007) y el
patrón de bandeja de salida: el evento que anuncia "ítem resuelto" se escribe en la misma
transacción que el cambio de estado, de modo que no hay forma de que el estado avance sin que el
evento salga, ni al revés.

### LangGraph: evaluado y diferido

LangGraph fue la alternativa de orquestación que más de cerca se consideró, porque su modelo
—un grafo de nodos con un *checkpointer* que persiste el estado entre pasos y permite reanudar—
describe casi exactamente lo que este pipeline necesita, incluida la interrupción para
intervención humana, que la librería soporta como primitiva.

**Se difiere, no se rechaza.** Las razones:

1. **El MVP no lo requiere.** El modelo de trabajos durables con dos tablas y una máquina de
   estados ya da reanudabilidad, reintentos idempotentes y auditoría de transiciones con
   dependencias que el equipo controla por completo. Agregar LangGraph resolvería un problema
   que estas dos tablas ya resuelven, a cambio de una dependencia más en el camino caliente.
2. **La tesis no depende de la librería.** La contribución de OE2/OE4 es el **diseño del proceso
   durable**, no la herramienta que lo ejecuta. Documentar el diseño en términos de estados,
   etapas y reanudación —y no en términos de nodos de LangGraph— hace que la documentación
   sobreviva a que la librería cambie de API o se reemplace.
3. **Adoptarla después no cambia nada aguas arriba.** El *checkpointer* de LangGraph puede
   apoyarse sobre Postgres, que es donde ya viven `trabajo_pipeline` y `etapa_trabajo`. La
   migración sería sustituir el ejecutor manteniendo el mismo modelo de datos y los mismos
   estados. Es exactamente la clase de decisión que conviene diferir: reversible y sin costo de
   arrastre.

Queda anotada como el camino de crecimiento natural si el pipeline se vuelve un grafo con
ramas y confluencias que la máquina de estados lineal empiece a expresar con dificultad.

## Consecuencias

**A favor.** El pipeline sobrevive a reinicios y a esperas humanas arbitrariamente largas. Un
fallo en un ítem no obliga a repetir el trabajo caro de los demás. El HITL deja de ser un efecto
de borde y pasa a ser un estado auditado. La orquestación no introduce ninguna dependencia
externa nueva en el MVP.

**En contra.** Persistir estado por etapa es más código y más escrituras que un `async` en
memoria, y obliga a pensar la idempotencia de cada etapa (qué pasa si se reintenta una que ya
emitió su evento). Ese costo es el precio de la durabilidad y se paga una vez.

**Deuda que se declara.** La calibración de los umbrales τ/δ que disparan la espera humana se
hizo con pocos ejemplos frente a los que hay anotados; ese flanco se cuenta honestamente en la
Memoria y su mejora es trabajo de OE3, no de esta decisión de orquestación.

## Alternativas consideradas

| Alternativa | Por qué no (por ahora) |
| --- | --- |
| **`async` secuencial en memoria** (lo del MVP) | No sobrevive a un reinicio ni a una espera humana; el estado vive en la pila de una corrutina. Sirve para demostrar, no para operar. |
| **LangGraph con checkpointer sobre Postgres** | Encaja casi exactamente, pero el MVP no lo necesita y ata la documentación a una librería. **Diferida**, no rechazada: es el camino de crecimiento. |
| **Un motor de flujos de trabajo externo** (Temporal, Airflow) | Resuelve durabilidad y reintentos, pero mete un componente de infraestructura pesado para tres personas y un pipeline que cabe en dos tablas. Desproporcionado al volumen. |
| **Cola de tareas cruda** (Celery/RQ) sobre el broker | Da reintentos pero no modela la espera humana como estado ni deja auditoría de transiciones; habría que reconstruir a mano justo lo que la máquina de estados da. |
