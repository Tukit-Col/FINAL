# Presupuesto de paginas, ronda 2 (Introduccion a Conclusiones, tope 50 antes de los cuatro \input)

Medido con `bash compilar.sh` el 1-nov (paginas del PDF; la Introduccion empieza en la 1). Los \input de optimizacion, nl2c, oe5 y calidad son hoy stubs de una frase; agregan unas 8 a 10 paginas.

| Capitulo | Inicio | Paginas |
|---|---|---|
| I Introduccion | 1 | 2 |
| II Descripcion general | 3 | 8 |
| III Contexto | 11 | 6 |
| IV Analisis del problema | 17 | 7 |
| V Diseno de la solucion | 24 | 8 |
| VI Desarrollo | 32 | 9 |
| VII Resultados | 41 | 7 |
| VIII Conclusiones | 48 | 3 |
| Total I a VIII | | 50 |

Referencias desde la 51 y anexos desde la 57 (fuera del tope).

## Movido a anexos (solo tablas, figuras y detalle; la prosa de I a IV no se recorto)

- Anexo `anx:tablas`: III comparacion-soluciones; IV moscow; II entregables; V reparto, politicas, latencia, adr, impulsores, alternativas; VII kits.
- Anexo `anx:figuras`: fig. c4-contexto (V) y graficas F3-2 y F5-2 (VII).
- Anexo `anx:ampliaciones`: detalle de lenguajes y Amdahl, doce pruebas de frontera, defectos de seguridad, carga y degradacion (V y VII), tabla RAG por fase (VI).
