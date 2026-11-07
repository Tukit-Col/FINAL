# Corrida del oro sobre la versión evaluada (7-nov-2026)

- Código: `validacion/oe5`, idéntico en `servicios/`, `libs/` y `apps/` a `b6b6fe7`, la versión evaluada.
- Pruebas: las de Rey en `origin/a/fases-2-6-oe5` (`datos/golden`, `test_golden_*`, `ensayos/e2e`). Se copiaron a un worktree aparte en `/tmp/tukit-oro-wt`, sin tocar la rama.
- Bases: copias aisladas `tukit_qa7_*` de las bases reales. Se comprobó por tabla que las reales quedaron idénticas a sus copias.
- Gemini: no se llamó. Las respuestas vienen grabadas en `datos/golden/fixtures-modelo/` y la guardia de red queda en 0.
- Tiempo: nivel 1, 15 s; e2e completo, 1 min 38 s, más unos 5 min de preparación del stack.

| Meta | Resultado | Evidencia |
|---|---|---|
| PRE-01 percepción | Cumple. 22/22 filas iguales al dorado y 0 inventadas. El PDF largo se lee y se rechaza por tope (la causa de H-A-36 desapareció porque el entorno tiene el extra `pdf`). | `inteligencia.xml` (TestFilaPorFila 22/22) |
| PRE-02 emparejamiento | Cumple en emparejamiento: top-1 22/22 en catálogo y parseo 111/111. Sigue H-A-38: sin columna de cantidad se guarda 1. | `catalogo.xml`, `inteligencia.xml` |
| PRE-03 anti-alucinación | Cumple: 0 productos fuera del catálogo. | `catalogo.xml`, `inteligencia.xml` |
| PRE-04 alternativa ante hueco | No cumple: 6 xfail, H-A-39 (un hueco nunca trae sustituto). | `inteligencia.xml` (TestLosHuecos) |
| PRE-05 baja confianza a revisión | No cumple: los renglones de baja confianza {2, 5, 8, 11} de G05 no quedan marcados; solo se marca {13} (H-A-40). La confianza sí se guarda (1 verde). | `e2e-acudiente.xml` |

E2E completo: 74 verdes, 14 xfail con su hallazgo y 1 omitida.

Hay 2 fallas, y ninguna es una regresión del sistema:
1. El tope del PDF largo da XPASS: la prueba esperaba H-A-36 y el defecto ya no ocurre.
2. `test_el_pago_aprobado_cobra_y_deja_pagado_el_pedido_congelado`: el pedido congelado trae una línea menos que la que la prueba calcula como comprable. Falta ver si la línea que no llega quedó con cantidad cero (corrección f1e1a26, que sí está en el código) o si es un hallazgo nuevo. Queda anotado para Rey.

En nivel 1 hay además una falla de coherencia del índice: faltan los fixtures adversariales en el worktree. Es del montaje, no del sistema.
