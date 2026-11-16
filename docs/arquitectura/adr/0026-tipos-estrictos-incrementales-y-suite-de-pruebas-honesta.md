# ADR 0026. Tipos estrictos incrementales por paquete y una suite de pruebas honesta (podar el ruido, fortalecer las invariantes)

- **Estado:** propuesta
- **Fecha:** 2026-09-25
- **Objetivos afectados:** OE4 (calidad y mantenibilidad verificables), OE2 (la costura de tipos como
  contrato interno)
- **Relacionada con:** ADR 0019 (el `dominio/` puro es lo que tipa limpio y se prueba con `assert`),
  ADR 0014 (las funciones de aptitud sobre fronteras son el modelo de "prueba que gana su sitio")

## Contexto

La suite tiene **50 archivos `test_*.py` y ~1.007 pruebas recolectadas**, y esa es su fortaleza: es la
red de regresión que permite el rediseño de las ADRs 0019–0025 sin perder funcionalidad. Pero no todas
las pruebas ganan su sitio, y la tipificación es desigual:

1. **Hay pruebas de bajo valor** que dan falsa sensación de cobertura: tautologías de esquema
   (`test_notificacion_sin_contacto`), pruebas que verifican el *doble* en vez del sistema
   (`test_embeddings::test_es_determinista`, `test_da_un_vector…`), chequeos frágiles sobre el código
   fuente (`test_embeddings::test_no_sale_a_la_red`, que hoy vive como test cuando es un *lint*),
   chequeos de una migración de una-sola-vez (`test_atributos_contrato::test_no_queda_rastro…`), y
   *smoke tests* que afirman `status == 201` sin comprobar ninguna invariante.

2. **Dos pruebas TypeScript nunca corren en CI**: existen pero no hay script que las invoque, así que
   su cobertura es ficticia.

3. **Los tipos no son estrictos.** Sin `mypy --strict`, la costura entre capas (ADR 0019) no está
   verificada por el compilador; un `dominio/` puro que dice recibir `list[LineaPedido]` puede recibir
   cualquier cosa sin que nadie avise.

El riesgo de "arreglar tipos" y "limpiar tests" es el clásico: un muro rojo de miles de errores de
mypy que nadie paga, o una poda que borra justo la prueba que sí atrapaba un bug.

## Decisión

**Tipos estrictos incrementales por paquete, y una poda de pruebas justificada una por una, conservando
y fortaleciendo las que verifican invariantes reales.**

### Tipos — `mypy --strict` incremental, sin muro rojo

`[tool.mypy]` con `strict = false` global y `[[tool.mypy.overrides]]` `strict = true` activado
**paquete por paquete**, en el orden en que se refactoriza (ADR 0019): primero `tukit_comun.*` (la base
que todos importan), luego cada servicio a medida que su `dominio/` puro se extrae —porque el dominio
puro, sin FastAPI ni SQLAlchemy, tipa limpio casi gratis—. `make tipos` queda **verde desde el día 1**
porque el estricto solo cubre lo ya migrado; nunca hay un estado rojo que nadie pueda pagar.

**Docstrings Google** (`Args`/`Returns`/`Raises`) para la API pública nueva de `dominio/` y
`repositorios/`; se conservan los docstrings narrativos ricos que ya existen en los adaptadores. `ruff`
gana las reglas `D` (convención google) **por paquete**, con el mismo avance incremental que mypy.

### Pruebas — podar el ruido, fortalecer las invariantes

- **Podar, con justificación en el commit de cada una:** las tautologías, las que prueban el doble, los
  chequeos de código fuente (que pasan a *lint*), los de migración de una-sola-vez, y los *smoke tests*
  sin invariante. Una prueba que no puede fallar cuando el sistema se rompe no protege nada; mantenerla
  es costo sin cobertura.
- **Conservar y fortalecer las de alto valor**, que son la red del rediseño: `test_precio_congelado`,
  `test_checkout` (422 `precio_cambiado`, idempotencia del webhook), `test_privacidad` (derecho al
  olvido), `test_autorizacion` (multi-tenencia), `test_descubrir` (abstención/plural), `test_pasarela`
  (firma Wompi), y `test_fronteras`/`test_fronteras_se_activan` (las funciones de aptitud de la ADR
  0014).
- **Convertir integración→unidad** al extraer el dominio (ADR 0019): las reglas que hoy exigen
  FastAPI+Postgres para probarse (reverificación de precio FU-08, la máquina del pipeline, las
  transiciones de la saga) pasan a `assert` puros sobre `dominio/`. Es el payoff directo del layering:
  las pruebas más caras del sistema se vuelven las más rápidas.
- **Tests nuevos guiados por TDD** para toda lógica nueva de las ADRs 0020–0025: el helper de
  resiliencia (que **debe** rechazar `reintentable=True` en un no-GET), `bandeja.drenar` (dos
  drenadores no toman la misma fila; se re-bindea el correlation-ID), las transiciones de saga, y en el
  frontend la máquina del asistente, `enviar-solicitud`, la caída del hook SSE a `sondear()`, y la
  invalidación de mutaciones.
- **Cablear los tests TS en CI:** el `package.json` raíz gana `"test": "npm run test --workspaces
  --if-present"` y `"test:ci": "npm run typecheck && npm run lint && npm run test"`; cada app gana su
  script `test`. `node --test` para lógica pura; **Vitest + React Testing Library** solo para
  componentes/hooks con DOM. Las dos pruebas que hoy no corren dejan de ser cobertura ficticia.

## Consecuencias

**A favor.** La costura entre capas queda verificada por el compilador donde ya se migró, sin un muro
rojo impagable. La suite deja de tener pruebas que dan cobertura ficticia y gana pruebas de dominio que
corren en milisegundos. La red de regresión de alto valor no solo se conserva: se fortalece y se
extiende a lo nuevo. Los tests TS pasan a existir de verdad en CI.

**En contra.** La poda es trabajo de juicio prueba-por-prueba (no un `rm` masivo) y el avance
incremental de mypy significa que durante un tiempo conviven paquetes estrictos y laxos. Se acepta
porque la alternativa —muro rojo global o poda a ciegas— es peor: o nadie la paga, o borra la prueba
que importaba.

**Deuda que se declara.** Hasta que el último servicio se migre (ADR 0019), habrá paquetes en
`strict = false`; el objetivo es que el estricto avance al mismo ritmo que el layering y no se quede
atrás. Un paquete refactorizado que no active `strict = true` es deuda visible en la config.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| **`mypy --strict` global de golpe** | Un muro de miles de errores que nadie paga y que bloquea todo lo demás. El incremental por paquete da el mismo destino sin el estado rojo intermedio. |
| **No podar** (conservar las ~1.007 tal cual) | Las pruebas de bajo valor dan cobertura ficticia y ruido en cada corrida; una prueba que no puede fallar cuando el sistema se rompe es costo sin protección. |
| **Poda masiva por patrón** (borrar todo lo que huela a smoke) | Borraría pruebas que sí atrapan invariantes. La poda justificada una-por-una es más lenta pero no tira la red buena. |
| **Dejar los tests TS sin cablear** | Cobertura ficticia: pruebas que existen pero nunca corren mienten sobre el estado del frontend. |
| **Borrar los chequeos de código fuente en vez de moverlos a lint** | El chequeo "no sale a la red" es útil como *lint* (barato, en cada commit); es solo su forma de *test* la que es frágil. Se mueve, no se pierde. |

## Estado de la poda (noviembre de 2026)

La suite creció a 183 archivos de prueba y 2.994 pruebas Python (más 345 de TypeScript, que ahora
corren en CI con el job `web`). La limpieza de noviembre fue estructural, no una poda: no se
borró ninguna prueba por valor, solo se fusionaron duplicados exactos (por ejemplo, nueve
pruebas de "sin token es 401" quedaron como una parametrizada de 19 rutas × 3 credenciales). Las pruebas
se ordenaron por módulo y comportamiento, las ayudas compartidas viven en `_ayudas_*.py` o en el
`conftest.py` y ninguna prueba importa de otra. Los parches a internos privados se reemplazaron por costuras
públicas (`nl2c.usar_llamador`, `app.state.reloj`, `correr_una_vez` con dependencias).
Ver `ESTRATEGIA_DE_PRUEBAS.md`.
