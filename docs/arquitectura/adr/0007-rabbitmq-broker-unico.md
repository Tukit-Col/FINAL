# ADR 0007 — RabbitMQ como broker único; Redis solo caché y límite de tasa

- **Estado:** aceptada
- **Objetivo afectado:** OE2

## Contexto

Los documentos de arquitectura mencionan Celery, y Celery aparece **únicamente en los
documentos**: no hay una sola línea de Celery en el código. Es una decisión que quedó
escrita y nunca se implementó.

Lo que el código hace es RabbitMQ, consumido a través de la librería compartida
`Tukit-Auditoria`, con bandeja de salida local por servicio y consumidores idempotentes.

Redis también está presente, pero para dos cosas distintas de mensajería: caché y límite
de tasa en el gateway.

El riesgo aquí es de claridad, no técnico: tres tecnologías nombradas para el mismo
propósito aparente, y un jurado que pregunte "¿cuál es el bus de eventos?" recibe tres
respuestas distintas según el documento que abra.

## Decisión

**RabbitMQ es el único mecanismo de mensajería entre servicios.** Se elimina toda mención
a Celery de los documentos. **Redis queda restringido a caché y límite de tasa**, y se
documenta así de forma explícita para que nadie lo confunda con una cola.

El patrón de integración queda fijado en uno solo: quien produce escribe en su bandeja de
salida local dentro de la transacción del negocio, un trabajador publica a RabbitMQ, y
quien consume es idempotente por clave del evento.

## Consecuencias

### Positivas

- Una sola manera de comunicar servicios, que un equipo de cuatro puede razonar completa.
- La documentación deja de contradecir al código.
- La bandeja de salida ya está implementada, así que esta decisión ratifica lo que existe
  en lugar de ordenar trabajo nuevo.

### Negativas, y las asumimos

- **RabbitMQ no es un registro persistente de eventos.** No se puede reproducir la historia
  como con un registro de tipo Kafka. Mitigación: la bandeja de salida es la fuente de
  verdad y sí es persistente; RabbitMQ solo transporta.
- **Redis es otra pieza de infraestructura.** Pero es la misma que ya sostiene el límite de
  tasa del gateway, así que no añade nada nuevo al despliegue.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Celery con Redis, como decían los documentos | Nunca se implementó, y Celery aporta un modelo de tareas que la librería compartida ya cubre con menos piezas |
| Kafka | Reproducción de eventos y retención son atributos valiosos, pero el costo de operar Kafka en minikube con cuatro personas es desproporcionado para el volumen de un piloto |
| Solo llamadas sincrónicas entre servicios, sin broker | Acopla la disponibilidad de todos a todos y elimina la degradación elegante que hoy funciona |

## Evidencia

- Celery presente solo en `ATAM_Tukit.tex`, `SAD_Tukit.tex` y el documento maestro; cero
  apariciones en código.
- RabbitMQ consumido vía `tukit_auditoria` en los trabajadores de MS-Busqueda y
  MS-Plataforma.
- Redis declarado como dependencia para caché en MS-Busqueda y límite de tasa en el gateway.
