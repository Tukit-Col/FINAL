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

## Ronda 3 (2-nov): integracion S2 (calibracion) y S4 (NL2C)

Cuerpo I a VIII: paginas 1 a 56 (tope 60). Referencias desde la 57, anexos desde la 64.
VI pasa de 9 a 15 paginas con VI.8 Optimizacion y calibracion y VI.9 NL2C; VII empieza en la 47 y VIII en la 54.
Movido a anexos: `anx:calibracion` (umbral por nivel, rejilla, tau, sensibilidad, hipervolumen por perfil, con sus figuras)
y `anx:nl2c` (rondas 2 y 3, campos, ASR, condiciones, costo, utilidad bajo ataque).

## Ronda 4 (4-nov): cierre de OE5, hilo, rigor formal, datos y producto

Cuerpo I a VIII: paginas 1 a 69 (conclusiones desde la 66). Pasa el tope de 60 en 9 paginas.
Lo que crecio: OE5 con resultados (tabla de tareas, hallazgos, cambios), "Datos del sistema" (tab:datos-sistema),
modelo formal del optimizador (variables, R1-R3, f1-f4), tab:metricas, figura del recorrido con 6 capturas y
tab:requisito-pantalla, tabla ISO 25010 en calidad, parrafos puente por capitulo. Al anexo: vista de despliegue
(fig:despliegue) y cuenta + revision del equipo (fig:producto-equipo).
Si hay que volver a 60: mover tab:metricas, tab:datos-sistema y tab:iso25010 a anx:tablas (unas 3 paginas) y la
figura del recorrido a anx:figuras dejando una frase en VI.
