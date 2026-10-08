# ADR 0039 — Lo que no tiene precio no gana por barato, y el coseno no resta

- **Estado:** aceptada
- **Fecha:** 2026-10-07
- **Servicios tocados:** `inteligencia` (`optimizador`), `catalogo` (`descubrir.clasificar`)
- **Origen:** la documentación formal de los algoritmos del núcleo (`docs/algoritmos/`), que al
  enunciar las propiedades de cada algoritmo encontró dos que el código no garantizaba.

## Contexto

**El frente trataba lo que no tiene precio como gratis.** El costo del frente (`_objetivos_de_asignacion`)
suma solo los candidatos con precio; la falta de precio se mide en `disponibilidad`. Cambiar un
candidato con precio por uno sin precio baja el costo y baja la disponibilidad, así que los dos puntos
quedan en el frente sin dominarse. `_proyectar` minimizaba el costo primero, y con dos líneas
(`A`: económico a $3.000 o premium sin precio; `B`: económico a $2.000 o premium a $9.000) el
Ahorrador elegía el premium sin precio y mostraba un total de $2.000 que no incluía esa línea. El
Premium y A tu Medida tenían el mismo problema: una marca sin precio sumaba fidelidad sin sumar costo.
La heurística (`elegir_por_perfil`) ya hacía lo correcto: pone lo que no tiene precio al final de su orden.

**El canal semántico podía restar.** `clasificar` suma `0.15 · coseno` en las ramas léxicas sin
recortarlo. Con un coseno negativo, el canal semántico hundía un match que el léxico acertaba, y la
propiedad «híbrido ≥ léxico», que el docstring y la tesis afirman, dependía del modelo de embeddings.

**Cuánto afectaban hoy**, medido el 2026-10-07:

| Hecho | Valor |
|---|---|
| Productos activos sin precio vigente | 0 de 666 (0 de 367 representantes) |
| Coseno mínimo producto–concepto ajeno, con los vectores reales | 0,436 (0 negativos en 79.344 pares) |

Ninguno de los dos se activaba con el catálogo actual. Eran defectos latentes: el primero aparece en
cuanto una oferta vence o se desactiva y el producto queda sin precio; el segundo, si cambia el modelo.

## Decisión

1. **El frente se proyecta sobre sus puntos de máxima disponibilidad** (`_surtibles`), tanto en
   `_proyectar` (Ahorrador, Premium, Fan) como en `_armar_a_tu_medida`. Lo que Tukit no puede surtir no
   gana una comparación de precio, igual que en la heurística. Si una línea solo tiene candidatos sin
   precio, todos los puntos los llevan y la línea sigue saliendo («no conocemos el precio» es mejor que
   una línea vacía).
2. **El coseno se recorta en 0** antes de entrar a la fusión. Un coseno negativo no significa «menos
   parecido que nada». Con eso, «híbrido ≥ léxico» vale sin suponer nada del modelo.

## Alternativas rechazadas

- **Contar lo que no tiene precio como costo infinito.** Lo volvería inelegible, y a veces es el único
  candidato que cumple lo que el colegio exige.
- **Cambiar solo la clave de desempate del Ahorrador** (disponibilidad antes que costo). Arreglaba ese
  kit y dejaba igual al Premium y a A tu Medida.
- **Filtrar del frente los puntos sin máxima disponibilidad al calcularlo.** Cambiaría el frente que se
  mide y se reporta. El frente sigue siendo de cuatro objetivos; el filtro es parte de la proyección.

## Lo que queda abierto

Un rescate semántico (`clasificar`, rama de rescate) vale entre 0,55 y 0,95. Con el umbral de
autoaceptación τ = 0,75, un rescate con coseno ≥ 0,93 se acepta sin revisión humana, contra la
intención de que el rescate siempre se revise. Medido con los vectores reales, ningún producto alcanza
0,93 contra un concepto ajeno (6 pares de 79.344 pasan de 0,86), y la lista pasa por revisión humana
antes de llegar a una familia. El arreglo correcto es que la respuesta del emparejamiento diga que
vino de un rescate y que `estado_desde_emparejamiento` lo mande a revisión; eso cambia el contrato de
`/v1/catalogo/emparejar`, así que se difiere. Bajar el techo del rescate por debajo de τ acoplaría el
catálogo a un umbral que vive en `inteligencia` y se configura por entorno.

## Consecuencias

- Pruebas nuevas: `TestUnCandidatoSinPrecioNoGanaPorBarato` (`inteligencia`) y
  `test_un_coseno_negativo_no_resta` (`catalogo`). Las suites completas pasan (341 y 713).
- Con el catálogo actual ningún kit cambia: no hay productos sin precio ni cosenos negativos.
- El documento de algoritmos (`docs/algoritmos/`) registra los dos cambios y la medición.
