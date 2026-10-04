# ADR 0028 — Los cambios del acudiente viven en su trabajo, no en las líneas del kit

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `inteligencia` (`trabajos`, `api`, modelo `trabajo_pipeline`, migración `5c1e8a3f9b20`), contrato TS (`contrato.ts`, `origen.ts`, `cliente-http.ts`), `apps/web` (`/kits/[trabajo_id]`), `apps/admin` (editor de línea)

## Contexto

El acudiente veía su kit pero no podía tocarlo. Cada renglón traía alternativas (otro nivel,
otra marca), pero solo como una lista para mirar. En la ruta rápida (`parent_apply`) ni siquiera
veía los otros dos kits: el backend le devolvía únicamente el que eligió al empezar.

Para que pudiera cambiar un producto había que decidir **dónde se escribe el cambio**. La opción
obvia era reutilizar la ruta del admin (`fijar_producto_en_linea`), que reescribe `linea_kit` y
recalcula `kit.total_cop`. Pero esas líneas no son siempre del acudiente:

- En la ruta rápida, su trabajo es un **puntero** al kit canónico del grado (ADR 0017 y siguientes):
  las líneas son las del canónico, compartidas por todos los acudientes de ese grado.
- Un trabajo de acudiente ya publicado puede quedar fijado como **canónico** del grado
  (`kit_canonico`), y entonces sus líneas también las reciben otros por la ruta rápida.

Escribir en `linea_kit` habría hecho que el cambio de un papá alterara el kit de otro.

## Decisión

- El cambio del acudiente se guarda en **su trabajo**, en la columna nueva
  `trabajo_pipeline.cambios` (`{perfil: {item_id: producto}}`). El producto se congela al
  elegirlo: sku, nombre, marca, nivel, imagen, empaque y precio.
- `trabajos.ver` aplica esos cambios **al leer**, en los dos caminos (kits propios y puntero al
  canónico), con la misma aritmética del armado (`techo(pedida / empaque)`), y vuelve a sumar el
  total. El pago (`trabajos.ordenar`) lee `ver`, así que cobra lo que el acudiente eligió.
- Solo se acepta un producto que **ya estaba en la línea**: el sugerido o una de sus
  alternativas. El acudiente elige entre lo que una persona revisó, no cualquier sku.
- La línea cambiada trae `cambiado_por_acudiente` y `sku_sugerido`; el sugerido pasa a ser una
  alternativa más, para que siempre se pueda volver a él. Volver al sugerido **borra** el cambio.
- Si el trabajo tiene dueño (`usuario_id`), solo su sesión lo puede cambiar. La ruta rápida
  admite trabajos sin cuenta, y esos los cambia quien tenga el id.
- Solo se cambian kits publicados. Una línea consolidada entre hermanos no se cambia por
  separado.
- La ruta rápida devuelve los **tres** kits del canónico, con el elegido como `recomendado`.
  El acudiente los compara desde un selector discreto y puede pagar otro.
- Endpoint: `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` (contrato 1.4).

## Alternativas rechazadas

- **Escribir en `linea_kit`** (reusar la ruta del admin). Alteraría el kit canónico que reciben
  otros acudientes.
- **Copiar los kits del canónico al trabajo del acudiente** al primer cambio. Rompe el modelo
  por referencia de la ruta rápida: duplica filas y deja copias que no se enteran de lo que la
  curaduría corrija después en el canónico.
- **Dejar que el acudiente elija cualquier producto del concepto.** Saltaría la revisión humana,
  que es la promesa del producto ("nunca te mandamos un kit sin revisar").

## Consecuencias

- El kit canónico queda intacto sin importar cuántos acudientes cambien productos.
- El precio del producto cambiado queda congelado al elegirlo, igual que el de las líneas del
  kit. Si cambia en el catálogo, el acudiente lo ve al volver a elegir.
- Si el acudiente ya tenía un pedido pendiente de pago y cambia algo, el siguiente pago crea un
  pedido nuevo con los cambios (ADR 0024: un pedido pendiente por kit, con firma de la orden).
- Un cambio sobre un renglón que la curaduría quite después del canónico deja de aplicarse en
  silencio: `ver` solo aplica cambios a líneas que existen.
