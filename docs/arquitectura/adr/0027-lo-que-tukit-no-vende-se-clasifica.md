# ADR 0027 — Lo que Tukit decide no vender se clasifica como `otro`, no queda como hueco

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `catalogo` (conceptos), `inteligencia` (`optimizador`, `parseo`), contrato TS (`linea.ts`), `apps/web`

## Contexto

Las listas piden cosas que Tukit no va a surtir: audífonos, un títere, vestuario para una
presentación, un computador o una tablet, componentes de robótica poco comunes (relay, puente H,
joystick). Había dos maneras de tratarlas, y ninguna era correcta:

- **Sin concepto:** el renglón iba a revisión en cada lista y en el kit se leía "No entendimos qué
  pide", que es falso: se entiende perfectamente.
- **Como `util` sin productos:** el kit decía "No lo tenemos", y el reporte de huecos lo contaba
  como algo por surtir. Mezclaba lo que falta con lo que se decidió no tener.

Cuando por fin tenían tipo `otro`, la interfaz los pintaba como "Lo gestiona el colegio", que
explica que el colegio o la editorial lo venden. También era falso.

## Decisión

- Lo que Tukit decide no vender lleva un concepto de tipo **`otro`**, con sus sinónimos, para que
  la próxima lista lo reconozca sin revisión.
- `otro` no se busca en el catálogo, no entra al total y tiene su propia clase de línea,
  **`por_su_cuenta`**: "Lo consigues por tu cuenta". La comparten `web` y `admin` desde
  `libs/ts/tukit-contrato/src/linea.ts`.
- Un texto escolar sin producto resuelto, cuya edición exacta vende una librería, va al mismo
  grupo: se entendió qué pide y el acudiente lo compra afuera.
- Un `util` sin productos sigue siendo "No lo tenemos". Esa es la señal de un hueco real.

## Alternativas rechazadas

- **Reutilizar `no_comprar`.** Significa que no hay que comprarlo (lo entrega el colegio, sirve
  el de casa). Aquí sí hay que comprarlo, solo que no en Tukit.
- **Ocultar esas líneas del kit.** El acudiente perdería de vista algo que la lista exige y
  llegaría al colegio sin ello.

## Consecuencias

- El reporte de huecos queda limpio: lo que dice "No lo tenemos" es lo que falta surtir.
- Decidir vender algo más adelante es cambiar el tipo del concepto a `util` y agregarle productos;
  los renglones ya asignados lo siguen sin reasignarse.
- Los conceptos `otro` actuales son C110 Audífonos de diadema, C132 Títere, C139 Vestuario para
  presentaciones, C142 Componente electrónico especializado y C147 Dispositivo electrónico.
