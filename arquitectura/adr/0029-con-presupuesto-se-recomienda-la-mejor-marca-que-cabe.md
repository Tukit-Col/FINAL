# ADR 0029 — Con presupuesto se recomienda la mejor marca que cabe, tomada del frente

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `inteligencia` (`optimizador`), contrato (§6, versión 1.3), `apps/web` (`/empezar`, paso 3)

## Contexto

El benchmark Laya contra NSGA-II (`ensayos/reporte-benchmark-laya-nsga.md`, rama
`bench/laya-vs-nsga`) mostró que, con presupuesto, el kit recomendado lograba el **40 %** de la
calidad posible, mientras el frente que el NSGA-II acababa de calcular traía un kit que cabía y
lograba el **94 %**. `recomendar` solo miraba los tres kits fijos y, si el recomendado no cabía,
caía al más barato. El contrato (§6) prometía "caer al siguiente punto del frente", y el código no
lo hacía.

El benchmark dejó otros dos hallazgos: la regla simple (`elegir_por_perfil`) ordenaba por precio
unitario y no por costo de la línea, y una regla de "subir de marca donde cuesta menos" dominaba
algún punto del frente en el 68 % de las listas.

## Decisión

- Con `presupuesto_por_hijo`, se recomienda la **mejor marca que cabe**. Si el Premium de siempre
  no cabe, ese kit se reemplaza por el punto del frente de mayor fidelidad dentro del tope. Sigue
  llamándose Premium, porque es su mismo arquetipo con la cota del acudiente, y la razón dice que
  se ajustó. No se ajusta si no mejora la marca del Ahorrador.
- El tope es el presupuesto **tal cual**. `disposicion_sobreprecio` no lo estira: dice cuánto más
  pagaría por marca sin tope, no cuánto se puede pasar del tope que él mismo puso.
- Si el recomendado no cabe, se cae al kit de mejor marca que sí cabe, no al más barato.
- `elegir_por_perfil` ordena por **costo de la línea** (precio × unidades a comprar).
- El NSGA-II se siembra con la **escalera de costo marginal**, que también entra al filtro final:
  ningún kit sembrado puede dominar un punto del frente.
- En `/empezar` hay un campo opcional "Tope de gasto". Con tope, la prioridad del paso 3 se apaga
  (ya no decide el kit marcado) y el hogar no toma la ruta rápida, porque la caché solo aplica uno
  de los tres kits fijos.

Esta decisión la tomó el autor del proyecto al revisar el benchmark: entre "recomendar la mejor
marca que cabe" y "respetar la regla de la encuesta y solo caer cuando no cabe", eligió la
primera, y entre "reemplazar el Premium" y "agregar un cuarto kit", eligió reemplazar el Premium
para no cambiar el contrato, la base ni las pantallas.

## Alternativas rechazadas

- **Solo caer al frente cuando el recomendado no cabe.** Es lo literal del contrato, pero con la
  regla de la encuesta (Ahorrador por defecto) no mueve el 40 % del benchmark.
- **Un cuarto kit "Presupuesto".** Más claro para el papá, pero cambia el enum de perfiles, la
  base, el contrato y las pantallas.
- **Meter el presupuesto como restricción del NSGA-II.** Recortaría el frente; la cota se aplica
  después del frente, al elegir el punto.

## Consecuencias

- En las 174 listas del benchmark (semilla 0), el kit recomendado con presupuesto cabe siempre e
  iguala el óptimo exacto (antes: 40 % de la calidad posible). La regla simple acierta el 100 % de
  los Ahorrador (antes 80 %) y la escalera ya no domina ningún punto del frente (antes 68 %).
- Un acudiente con tope pierde la ruta rápida: su solicitud pasa por el optimizador y por la
  revisión humana. Queda abierto recomendar al instante el mejor kit canónico que quepa.
- Cuando el Premium se ajusta, la tarjeta sigue diciendo "Premium": solo la razón del recomendado
  explica el ajuste. Queda abierto marcarlo en la tarjeta.
