# ADR 0030 — Solo se arman los kits que el acudiente pide

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `inteligencia` (`optimizador`, `trabajos`, `api`, migración `7d4b2c9e1f36`), contrato TS (`PerfilKit`, `Preferencias`), `apps/web` (`/empezar` paso 3, `/kits`), `apps/admin` (matriz de kits)
- **Reemplaza en parte:** ADR 0029 (el kit con tope ya no ocupa el lugar del Premium)

## Contexto

Todo trabajo armaba tres kits: Ahorrador, Fan y Premium. El Fan salía aunque nadie hubiera
pedido un personaje, y los canónicos de cada lista aprobada también traían su Fan. El papá veía
un kit que no pidió y el revisor revisaba un kit que nadie iba a comprar.

Con el ADR 0029, un acudiente con presupuesto recibía un Premium "ajustado": la mejor marca que
cabía en su tope, con el nombre Premium. La tarjeta no lo distinguía del Premium de verdad, y el
punto medio del formulario no armaba nada propio: marcaba el Ahorrador.

Al probarlo, el autor del proyecto definió el flujo que quería:

- El kit del punto medio tiene nombre propio, **A tu Medida**, y ocupa el espacio entre el
  Ahorrador y el Premium.
- El tope de gasto solo tiene sentido para ese kit: con "Lo más económico" o "Puedo estirarme"
  no se pide. Con el punto medio es opcional y, sin tope, se le explica al papá en qué se basa.
- El Fan solo se arma si el papá elige un personaje.
- Los canónicos de una lista son solo el Ahorrador y el Premium. El kit con personaje se arma
  para el acudiente que lo pide.

## Decisión

- **Kits que se arman** (`optimizador.armar_los_tres`): siempre `Ahorrador` y `Premium`; `Fan`
  solo con `personaje_por_hijo`; `A tu Medida` solo con `prioridad: "equilibrio"` o un tope.
- **`A tu Medida`** es el punto del frente con mayor fidelidad cuyo costo cabe en el tope. Sin
  tope declarado, el tope es la mitad de camino entre el total del Ahorrador y el del Premium (el
  mismo criterio del escenario intermedio del benchmark). Si no hay un kit distinto que armar
  (el tope alcanza para el Premium, o no alcanza para subir ninguna marca), no se arma, y la
  razón del kit marcado lo explica. El Premium vuelve a ser siempre la mejor marca.
- **Recomendación:** Fan si pidió personaje; A tu Medida si eligió el punto medio; Premium con
  calidad primero y ≥10 % de sobreprecio; si no, Ahorrador. Con tope, si el marcado no cabe se
  cae a la mejor marca que cabe; si ninguno cabe, la razón dice cuánto cuesta el más barato.
  Los montos se escriben en pesos colombianos (`$443.255`).
- **Canónicos:** se arman sin preferencias, así que son Ahorrador y Premium. Los que ya existían
  se regeneran.
- **Ruta rápida:** el Fan se arma para el acudiente que pide un personaje: es el Ahorrador
  canónico con el personaje en las anclas. Ahorrador y Premium se muestran tal cual los revisó
  una persona. `A tu Medida` no sale de la caché, porque depende de cada acudiente: quien elige el
  punto medio pasa por el optimizador y por la revisión humana.
- **Formulario:** el campo de tope solo aparece con el punto medio, y su ayuda explica la mitad
  de camino cuando se deja vacío. Se envía `prioridad`.
- Contrato 1.5. Migración `7d4b2c9e1f36`, que admite el perfil `A tu Medida` en `kit.perfil`.

## Alternativas rechazadas

- **Seguir ajustando el Premium** (ADR 0029). La tarjeta decía "Premium" sin serlo.
- **Un cuarto kit siempre visible.** Mostraría un kit que el papá no pidió.
- **Armar `A tu Medida` en la ruta rápida mezclando el Ahorrador y el Premium canónicos.** Sale
  al instante, pero el autor prefirió que se arme para cada acudiente con el optimizador.

## Consecuencias

- Los trabajos sin personaje ni punto medio tienen dos kits, y el revisor revisa dos.
- Quien elige el punto medio no recibe el kit al instante: espera la revisión humana.
- Un canónico viejo con Fan sigue funcionando: la ruta rápida ignora su Fan y arma el del
  acudiente si lo pidió.
- La interfaz no puede asumir tres kits: la matriz del admin y el selector de la web toman los
  que llegan, en el orden Ahorrador, Fan, A tu Medida, Premium.
