# Asistente NL2C: nota de diseño

Esta nota dice qué mecanismo del código responde a cada patrón de seguridad de la literatura y a cada riesgo de la lista OWASP. Va primero el problema, después los patrones, después la tabla de mecanismos y al final lo que el diseño no cubre. Las cifras de evaluación están en `docs/informes/nl2c/README.md`; el desarrollo completo, en `docs/informes/nl2c/nl2c.tex`.

## 1. Qué hace y qué no

NL2C convierte el texto de un acudiente en la restricción `R = ⟨filtros_duros, pesos_NSGA, preferencias_PRM⟩` que ya consume el recomendador. La propuesta aprobada (VFP) prometió llamado a funciones. El modelo (Gemini, `GEMINI_MODELO`) solo elige una función de una lista y rellena sus argumentos; no escribe en el kit, no toca preferencias y no habla con el padre. Aplicar un cambio es una acción del padre por los endpoints de siempre.

Tres rutas, cada una con un plan fijo (`nl2c_flujo.py`):

| Ruta | Funciones permitidas | Resultado |
|---|---|---|
| `POST /v1/nl2c/interpretar` | `fijar_restricciones`, `sin_accion` | R validada y spec de UI |
| `POST /v1/kits/{id}/asistente/proponer` | `proponer_cambio`, `proponer_descarte`, `explicar_kit`, `sin_accion` | propuestas atadas al kit |
| `POST /v1/nl2c/decision` | ninguna (no llama al modelo) | registro de aceptar o rechazar |

## 2. Patrones de la literatura y cómo se usan

- **Plan-then-execute y action-selector** (Beurer-Kellner et al., 2025). El plan de cada ruta se fija en código antes de ver el texto del padre; el modelo solo selecciona una acción de la lista de esa ruta. Un texto inyectado no puede agregar pasos al plan porque el plan no sale del modelo. Implementación: `HERRAMIENTAS_INTERPRETAR`, `HERRAMIENTAS_KIT`, `toolConfig.allowedFunctionNames`, y un segundo filtro por lista blanca en `consultar_modelo`.
- **Un solo turno, sin retorno de resultados** (action-selector). Ningún resultado de herramienta vuelve al modelo, de modo que un dato envenenado del kit no puede influir en una segunda decisión. `MAX_TURNOS = 1`.
- **Separación de datos y control, versión CaMeL** (Debenedetti et al., 2025). El modelo no maneja valores del kit: emite referencias cortas (`L3`, `A1`) que el servidor resuelve contra sus propios datos (`contexto_del_kit`). Los precios, SKU y textos que ve el padre salen de datos del servidor y de plantillas, no del modelo. No se implementa el intérprete con capacidades de CaMeL; se toma solo la idea de que el modelo planifica y el código ejecuta.
- **Inyección indirecta** (Greshake et al., 2023). Las descripciones de renglón vienen de listas escolares y son datos no confiables. Se sanean, se acotan a 80 caracteres y se envuelven en `<renglones_del_kit>`; el prompt de sistema declara que todo lo que está entre marcas es dato.
- **Evaluación estilo AgentDojo** (Debenedetti et al., 2024). Casos con una tarea legítima del usuario y una instrucción del atacante, con una condición de éxito escrita antes de correr el modelo. Se reporta la tasa de éxito del ataque (ASR) y la utilidad bajo ataque.

## 3. Mapa con OWASP Top 10 para aplicaciones LLM 2025

| Riesgo | Cómo aparece aquí | Mecanismo | Dónde |
|---|---|---|---|
| LLM01 Inyección de prompt | Texto del padre y descripciones del kit con órdenes | Texto como dato entre marcas; saneado de delimitadores y caracteres de ancho cero; lista blanca de funciones; plan fijo; proyección de R | `nl2c.sanitizar`, `armar_usuario`, `consultar_modelo`, `proyectar_R` |
| LLM02 Divulgación de información sensible | PII del padre al proveedor; fuga hacia otro padre | Redacción de correo, teléfono, enlace, dirección y nombres antes de la llamada; el prompt de la ruta de interpretar no lleva datos del hogar; la bitácora guarda huellas, no texto; mismo 404 para kit ajeno e inexistente | `sanitizar`, `auditar`, `routers/nl2c.py` |
| LLM05 Manejo inadecuado de la salida | Salida del modelo hacia la pantalla | Validación con Pydantic `extra="forbid"`; recorte a dominios; todo texto visible sale de plantillas del servidor; la web vuelve a validar la spec contra la lista blanca y no pinta HTML | `proyectar_R`, `construir_ui_empezar`, `espec.ts: validarEspec` |
| LLM06 Agencia excesiva | El modelo con permiso de actuar | Solo propone. Aceptar un cambio o un descarte llama al endpoint existente de S3 (`PUT .../producto` o `PUT .../descarte`) con la sesión del padre, que exige que el kit sea suyo; el modelo no tiene ninguna vía para aplicarlo. Máximo 5 propuestas por respuesta | `nl2c_kit.validar_llamadas_kit`, `PanelKit.tsx` |
| LLM10 Consumo ilimitado | Texto largo, ráfagas, costo | 1000 caracteres de texto, 400 tokens de salida, 12 s de plazo sin reintento, un turno, límite estricto en el gateway (30 por token y 60 por IP cada 600 s) | `nl2c.py` constantes, `limite.py` |

## 4. Decisiones que conviene recordar

1. **Texto del modelo anclado al texto del padre.** Una marca a excluir solo pasa si aparece en lo que el padre escribió (`texto_base` en `proyectar_R`). Sin eso, un modelo manipulado podía hacer que la pantalla mostrara una cadena del atacante dentro del resumen.
2. **Pesos con piso y tope.** Cada peso queda entre 0.05 y 0.60 y suman 1.00. Una versión anterior dejaba la suma fuera de 1 cuando el modelo pedía ceros; la pegó un caso adversarial con un modelo obediente.
3. **Bandera doble.** `TUKIT_ASISTENTE=1` en el backend y `NEXT_PUBLIC_TUKIT_ASISTENTE=1` en la web. Apagadas, las rutas devuelven 404 y los paneles no se montan. El panel de `/empezar` tiene además su propia bandera, `NEXT_PUBLIC_TUKIT_ASISTENTE_EMPEZAR=1`, apagada por omisión: desde el 2 de noviembre de 2026 el inicio usa el formulario guiado y el asistente solo aparece en la página del kit. Si el modelo falla, la web vuelve al formulario clásico.
4. **Sin escritura propia.** Ni el backend ni el panel guardan preferencias; el formulario recibe los valores por un evento del navegador y el padre confirma.

## 5. Lo que el diseño no cubre

- **Propuesta válida que el padre no pidió.** Un renglón con una orden inyectada puede lograr que el modelo proponga un cambio real (dentro del kit, con precios del servidor). El servidor no puede conocer la intención del padre; lo frena la confirmación explícita.
- **Descartar un renglón** solo se propone; no existe un endpoint de descarte.
- **Un solo proveedor.** El texto saneado sale hacia Gemini; no hay modelo local.
- **Bitácora en memoria.** `BITACORA` y la tabla de propuestas emitidas viven en el proceso; no se persisten.

## 5b. Los filtros duros llegan al optimizador

`marcas_excluidas` y `solo_disponibles` ya no son decorativos. El recorrido es: `a_preferencias(R)` los incluye (solo si el padre los pidió) → el asistente los muestra en el resumen y los guarda con las demás restricciones → el formulario de `/empezar` los manda dentro de `preferencias` (se ven y se pueden quitar antes de enviar) → `Preferencias` del trabajo (cifradas en `preferencias_cifradas`) → `armar_los_tres` → `aplicar_filtros_duros`.

- **Por construcción, antes del frente.** Se quitan candidatos de cada renglón antes de calcular el frente de Pareto. No son un peso: un peso podría dejar pasar la marca que el padre pidió no ver. (El presupuesto sí se aplica después del frente; ver el docstring de `optimizador.py`.)
- **Comparación de marcas.** Sin mayúsculas, tildes ni signos (`Faber-Castell` = `FABER CASTELL`), por palabras completas (`Norma` no excluye `Normalizado`). Si el catálogo no trae marca, se mira el nombre del producto.
- **Marca exigida por el colegio.** Catálogo no guarda la marca exigida como dato aparte; la señal es que el texto del renglón nombre la marca. En ese renglón no se quita y la línea lo explica ("El colegio pide X en esta línea y no la quitamos"). `solo_disponibles` sí aplica también ahí.
- **`solo_disponibles`.** Disponible = candidato con precio vigente en una oferta activa, que es lo único que llega a Inteligencia y lo que ya mide el objetivo `disponibilidad`.
- **Línea sin candidatos.** No se rellena con lo prohibido: queda como `HUECO_CATALOGO`, sin precio y fuera del total, con un `mensaje` que dice qué se quitó y por qué.
- **Kit Fan.** El producto de personaje entra por una vía aparte (`inyectar_personaje_fan`); allí se aplica el mismo filtro.
- **Ruta rápida (`aplicar-canonico`): se rechaza, no se filtra.** Esa ruta reutiliza el kit canónico sin re-optimizar y sin las alternativas por marca, así que no puede honrar los filtros. Si llegan, responde 422 `filtros_requieren_recalculo`, y el formulario no toma esa ruta cuando hay filtros: crea un trabajo normal, que sí re-optimiza.
- **Límites en el borde.** Hasta 10 marcas de 1 a 40 caracteres, igual que `FiltrosDuros`; las preferencias de una subida de PDF viajan como JSON sin esquema, así que el optimizador también las lee con tipos y topes defensivos.

Pruebas: `servicios/inteligencia/tests/test_filtros_duros.py` (exclusión, excepción de marca exigida, línea sin candidatos, `solo_disponibles`, Fan, guardado y pipeline completo, 422 de la ruta rápida), `test_nl2c.py::test_a_preferencias_pasa_marcas_excluidas_y_solo_disponibles_al_optimizador` y `apps/web/test/restricciones-asistente.test.ts`.

## 6. Referencias

Beurer-Kellner et al. (2025), Debenedetti et al. (2025), Debenedetti et al. (2024), Greshake et al. (2023) y OWASP (2025), con sus datos completos en `docs/informes/nl2c/nl2c.bib`.
