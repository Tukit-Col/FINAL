# ADR 0006 — Eliminar Neo4j y resolver la expansión de grafo en proceso

- **Estado:** aceptada
- **Objetivos afectados:** OE2, OE3

## Contexto

La documentación presenta la normalización como GraphRAG e implica una base de datos de
grafos. En el código hay soporte para Neo4j, pero está **apagado**: la bandera de
expansión por grafo viene en falso y la dirección de conexión viene vacía por defecto.

Lo que sí funciona y está encendido es un grafo de concepto a variantes construido en
memoria con NetworkX sobre el catálogo, sin servicios externos.

Los números del dominio explican por qué eso alcanza. El consolidado de diecisiete
colegios tiene 3.608 ítems, 48 categorías y 1.451 formas distintas de nombrar. Ese grafo
cabe holgadamente en memoria. Neo4j resuelve recorridos profundos sobre grafos que no
caben en memoria, y este no es ese problema.

Mantener Neo4j en el despliegue significa un motor más que instalar, respaldar, asegurar
y explicar, para un camino de código que nadie ejecuta.

## Decisión

**Se elimina Neo4j del alcance.** La expansión por grafo se resuelve en proceso con
NetworkX sobre el catálogo canónico, y la documentación se corrige para describir eso.

La terminología también se corrige. Lo que el sistema hace es **expansión de consulta
aumentada por grafo** sobre candidatos recuperados: el grafo relaciona el concepto
genérico con sus variantes observadas y enriquece la consulta. Llamarlo GraphRAG, en el
sentido de Edge y colegas, sugiere resumen jerárquico global sobre comunidades del grafo,
que no es lo que ocurre. Sostener el nombre es una imprecisión que un jurado puede
señalar con razón.

## Consecuencias

### Positivas

- Un motor de datos menos en el despliegue, lo que baja el costo de operar y la
  superficie por asegurar.
- La descripción del sistema pasa a ser cierta, que en un documento académico vale más que
  sonar sofisticado.
- El grafo en memoria se reconstruye por categoría con caché, así que la latencia es
  despreciable frente a la búsqueda vectorial.

### Negativas, y las asumimos

- **Se renuncia a consultas de grafo expresivas.** Si en el futuro la sustituibilidad
  entre productos necesitara recorridos de varios saltos, habría que reconsiderarlo. La
  investigación del MVP ya exploró un grafo de sustituibilidad entre productos y **lo
  rechazó**, así que la necesidad no está demostrada.
- **El grafo vive en memoria del proceso.** Con varias réplicas, cada una construye el
  suyo. Mitigación: la construcción es por categoría y con caché; el costo es memoria, no
  correctitud.
- **Hay requisitos del SRS que nombran GraphRAG.** Hay que reformularlos, no borrarlos, y
  dejar la trazabilidad del cambio.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Neo4j en producción | Un motor más para un camino apagado, sobre un grafo que cabe en memoria |
| Extensión de grafos de Postgres | Añade dependencia y complejidad de consulta sin resolver un problema que hoy no existe |
| Quitar del todo la expansión por grafo | Sí aporta: conecta la forma escrita en la lista con el concepto canónico, que es el corazón de la normalización con 1.451 formas de nombrar 48 categorías |

## Evidencia

- Bandera de expansión por grafo en falso y dirección de Neo4j vacía en la configuración
  de MS-Busqueda.
- Grafo de concepto a variantes activo con NetworkX, con caché por categoría.
- Grafo de sustituibilidad entre productos evaluado y rechazado en la investigación del MVP.
- Dimensiones del dominio: 3.608 ítems, 48 categorías, 1.451 formas de nombrar.
