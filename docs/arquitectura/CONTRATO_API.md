# Contrato de la API de Tukit

> **Superficie compartida.** Este documento y `manifiesto.toml` son lo único que varios
> equipos tocan a la vez. El manifiesto fija las fronteras de *datos*; este fija las
> fronteras de *conversación*. Cambiar cualquiera de los dos sin avisar rompe a alguien
> más, así que se cierran antes de repartir el trabajo y se versionan.

- **Versión:** 1.12
- **Prefijo:** `/v1`
- **URL base:** `http://127.0.0.1:8010` en desarrollo. Ver §12.1.
- **Formato:** JSON UTF-8. Dinero en **pesos enteros** (nunca decimales flotantes).
- **Idioma de los identificadores:** español sin tildes, como el resto del código.

### Qué cambió en 1.12

La consola interna exige sesión del equipo en el gateway. Un cliente de 1.11 que ya mandaba el
Bearer del operador o del admin no cambia nada. Uno que llamaba a `/v1/admin/*` sin token, sí:
ahora recibe `401`.

| Cambio | Dónde | Por qué |
|---|---|---|
| Toda ruta `/v1/admin/*` exige un Bearer válido con rol `admin` u `operador`: sin token o con uno que Identidad no reconoce, `401 sesion_invalida`; con uno sin rol del equipo, `403 acceso_denegado`; si Identidad no responde, `503 identidad_no_disponible` | §7, §12.1 | Por el gateway, sin token, se podían leer la cola y las listas y aprobar y publicar un kit |
| La excepción es `POST /v1/admin/sugerencias`, que manda la web pública por un acudiente que puede no tener cuenta. `GET /v1/admin/sugerencias` es del equipo | §7 | Es la única ruta bajo `/v1/admin` que no es de la consola |
| Las escrituras de consola fuera de `/v1/admin` exigen la misma sesión: `PATCH` y `DELETE /v1/catalogo/productos/{sku}`, `POST /v1/catalogo/productos/{sku}/reclasificar` y `PATCH /v1/colegios/{colegio_id}`. Leerlos (`GET`) sigue siendo público | §7 | Sin token se podía editar, retirar o reclasificar un producto y editar el perfil de un colegio |
| Aprobar el trabajo de un acudiente (`POST /v1/admin/trabajos/{id}/revision` con `aprobar`) lo publica para él y ya no lo vuelve el kit canónico de su grado. El canónico sale de la lista aprobada (`canonico_lista`) o de un preview fijado | §7 | El kit de un papá lleva sus preferencias; los papás siguientes recibían un kit armado con las de otro |
| `POST /v1/sesiones/cierre` revoca el token: sube la `version_permisos` del portador, así que cierra la sesión en todos sus dispositivos. Sin token o con uno que ya no vale sigue respondiendo `204` | Identidad | Antes solo se borraba la cookie y el token seguía valiendo hasta expirar |
| `GET /v1/contactos/{usuario_id}` deja de estar expuesto en el gateway (404 como cualquier ruta interna). `POST /v1/contactos` sigue igual | §7 | Devolvía correo y celular de cualquier usuario sin token; solo lo usan los servicios entre ellos |
| `apps/admin` reenvía como Bearer el token de la cookie `tukit_sesion` en todas sus llamadas | §12.8 | Antes solo lo hacía en el onboarding y en la logística |

### Qué cambió en 1.11

El gateway limita la tasa, y Redis guarda la lectura de una lista y el vector de cada renglón
(ADR 0047). Lo único nuevo para un cliente es el `429`. Un cliente de 1.10 sigue funcionando, y si
no trata el `429` lo ve como cualquier error con `error` y `mensaje`.

| Cambio | Dónde | Por qué |
|---|---|---|
| El gateway responde `429 demasiadas_peticiones`, con `Retry-After` y `reintentar_en_segundos`, cuando una petición pasa un tope de su nivel | §11.1 | Nada limitaba cuántas subidas o intentos de entrar hacía una persona (ESC-09) |
| Quedan fuera del límite `/v1/servicios`, `/v1/webhooks/*`, las preflight `OPTIONS` y lo que no es `/v1/*` | §11.1 | La pasarela reintenta y no es un cliente, y una sonda no debe gastar cupo |
| El gateway toma la IP de `X-Forwarded-For` solo si la conexión viene de un proxy de confianza (`TUKIT_PROXIES_CONFIANZA`), y el servidor de Next.js la reenvía | §11.1 | Sin eso, todas las familias contarían como la IP del servidor de la web |
| Con `REDIS_URL`, la lectura aceptada de un archivo y el vector de cada renglón se guardan. Sin Redis, o si no responde, se calcula como en 1.10 | §8 | Las familias de un colegio suben el mismo PDF. El cruce con el catálogo y los precios se recalcula siempre |
| `@tukit/contrato` exporta `ErrorDemasiadasPeticiones` y `conEspera`, y un `ErrorTukit` con estado `429` trae `reintentar_en_segundos` en su `detalle` | §11.1 | Para que la web y la consola digan la espera igual, aunque el `429` llegue sin cuerpo |

### Qué cambió en 1.10

Cómo viajan los eventos entre servicios (ADR 0046). La API HTTP no cambia: un cliente de 1.9
sigue funcionando igual. Cambia el contrato entre servicios, que se describe en el §10.1.

| Cambio | Dónde | Por qué |
|---|---|---|
| Con `RABBITMQ_URL`, cada productor publica su bandeja en el exchange `tukit.eventos` y cada consumidor escucha su cola. Sin ella, los consumidores siguen leyendo las bandejas, como en 1.9 | §10.1 | Ningún consumidor lee la base de otro servicio, y un evento llega en cuanto se publica |
| El mensaje es un sobre con `evento_id`, `origen`, `tipo`, `agregado_tipo`, `agregado_id`, `carga` y `correlacion_id` | §10.1 | Para deduplicar por origen e id y seguir el hilo de la petición |
| La carga de `kits_publicados` agrega `usuario_id`, el acudiente al que va el aviso. Es aditivo | §10.1 | Con broker, el repartidor no lee `trabajo_pipeline` |
| Evento nuevo, `trabajo_encolado`, en la bandeja de inteligencia y solo con broker | §10.1 | El aviso que lleva un trabajo al trabajador |
| Un mensaje que falla se reintenta cada 10 s, y al quinto intento queda en `<cola>.descartados` | §8, §10.1 | Queda visible, en vez de reintentarse sin fin |

### Qué cambió en 1.9

La dirección del checkout se autocompleta con Google Places (ADR 0044), el acudiente sigue su
pedido en una línea de tiempo y el staff sube desde la cola la lista de cualquier colegio de
Bogotá (ADR 0045). Todo es aditivo, salvo una cosa: `POST /v1/admin/onboarding` ahora exige
sesión de staff. Un cliente de 1.8 que ya mandaba el Bearer sigue funcionando sin cambios.

| Cambio | Dónde | Por qué |
|---|---|---|
| `entrega` del checkout (`POST /v1/trabajos/{id}/ordenar`) y de `POST /v1/ordenes` acepta los opcionales `localidad` (≤ 64), `indicaciones` (≤ 512), `departamento` (≤ 128) y `google_place_id` (≤ 512). Nunca coordenadas | §9.6 | Dirección con Google Places, localidad de Bogotá y "apartamento, torre, interior" |
| `envio` gana `localidad` y `google_place_id` (columnas nulables, migración `b619c58fc0c3`) en `GET /v1/ordenes/{id}`, `GET /v1/comercio/mis-pedidos/{id}` y el detalle de logística | §9.6 | Logística ve la localidad y abre la dirección en Google Maps |
| La firma que decide si un pendiente se reutiliza compara todos los campos congelados de la entrega, salvo `google_place_id` | §9.4 | Otro apartamento u otra localidad no pueden despacharse con el dato viejo |
| `GET /v1/comercio/mis-pedidos/{id}` agrega `linea_de_tiempo`; no quita nada | §9.7 | La página `/pedidos/{id}` del acudiente |
| `POST /v1/admin/onboarding` designa el colegio con `colegio_id`, con `colegio_dane` + `colegio_nombre` o solo con `colegio_nombre`; sin ninguno, `422 colegio_requerido` | §12.8 | Subir desde la cola la lista de un colegio que Tukit aún no tiene |
| `POST /v1/admin/onboarding` exige `Authorization: Bearer` de operador o admin: `401 sesion_invalida` sin sesión, `403 acceso_denegado` sin rol de staff, `503 identidad_no_disponible` si Identidad no responde. Se valida antes de leer el archivo. `OrigenDatos.onboarding` recibe el `token` primero | §12.8 | Antes cualquiera podía subir una lista a la cola y gastar una lectura de Gemini |
| El directorio de colegios de Bogotá vive en `@tukit/contrato` (`directorio-colegios.json`), cada entrada con `imageURL`, y las dos apps lo sirven en `/directorio-colegios.json` | §12.4 | Una sola copia, y logo por DANE para los colegios sin `logo_url` |

### Qué cambió en 1.8

Lo que hace la API cuando una dependencia propia se cae, según la verificación de caos de QA
(fases 7 a 9). Detalle en los ADR 0040, 0041 y 0042.

| Cambio | Dónde | Por qué |
|---|---|---|
| `POST /v1/listas/subir` con el catálogo caído responde `202` (antes `500`). El hijo cuya lista no se importó trae `version_id: null` y `estado: "pendiente"`; los demás, su `version_id`. La lista se importa sola cuando el catálogo vuelve, sin volver a subirla. Con el catálogo arriba, la respuesta es la de antes y no trae `estado` | §8, §12.9 | La lista se perdía y el acudiente no sabía si había entrado |
| "Mis solicitudes" muestra esa lista como `recibida`, con `tarea_id: null` mientras espera al catálogo | §4 | Todavía no hay tarea que cancelar |
| `POST /v1/admin/onboarding` con el catálogo caído responde `503 servicio_no_disponible` (antes `500`), con un mensaje que dice que la lista no se guardó | §8 | El admin necesita la versión en el acto y puede reintentar |
| `POST /v1/admin/listas/importar` (catálogo, entre servicios) acepta `clave_idempotencia`, un UUID. Con una clave que ya entró responde la misma tarea y la misma versión, sin crear otra; una clave que no es UUID es `422 clave_invalida` | §8 | Para que el reintento no duplique la versión |
| Los procesos de fondo (barredor, pollers, trabajador y repartidor) esperan a que vuelvan Postgres o RabbitMQ y siguen | §8 | Morían y no volvían: nadie avisaba ni importaba |
| Un evento da un solo aviso, aunque la bandeja lo entregue otra vez | §10 | Un pago avisaba dos veces si RabbitMQ se caía a mitad |

### Qué cambió en 1.7

Se une la logística de pedidos de la rama `preview-kits` con los pagos de Wompi, y se rescatan
de esa rama los arreglos de validar (no su cola ni su vista previa). Detalle en el ADR 0032.

| Cambio | Dónde | Por qué |
|---|---|---|
| El tablero (`GET /v1/comercio/pedidos`), el detalle (`GET /v1/comercio/pedidos/{id}`) y `POST /v1/ordenes/{id}/avanzar` exigen sesión de operador o admin: `401` sin sesión, `403` con otro rol, `503` si identidad no responde | §9 | Exponían direcciones y datos del reparto sin sesión |
| `GET /v1/comercio/mis-pedidos` saca al acudiente del Bearer; `?usuario_id=` se ignora | §9 | Cualquiera podía leer los pedidos de otro |
| `GET /v1/comercio/mis-pedidos/{id}`, `POST .../pago` y `POST .../cancelar` con el Bearer del dueño; un pedido ajeno es `404` | §9.5 | La puerta ya no expone `/v1/ordenes/*` salvo `avanzar` |
| `avanzar` lleva repartidor (nombre y celular), tipo de incidencia y nota; cada avance queda en el historial con el correo de quien lo hizo y avisa al acudiente | §9 | Reparto propio y trazabilidad del back-office |
| La referencia de un intento de pago es `tukit-<pedido_id>-<n>` | §9.1 | Un reintento no choca con la anterior |
| `validar` sin producto responde `422 sin_producto_que_validar` con `campo: "sku"` (antes `409`); un `sku` que no era candidato se registra y se valida, en vez de validar otro; acepta `nota` | §7 | Validar una línea ambigua daba `500` o confirmaba un producto distinto |
| `sin-coincidencia` deja la línea sin producto ni precio en todos los kits y baja su total | §7 | El acudiente la veía como hueco y `ordenar` la cobraba |
| Una reserva sin pagar vence a las 24 horas, igual que el pedido | §9.4 | El barredor la cancelaba a los 30 minutos, con un PSE quizá en curso |

### Qué cambió en 1.6

El acudiente puede deshacer desde su panel: cancelar una solicitud y quitar o cambiar de colegio
a un hijo (ADR 0031).

| Cambio | Dónde | Por qué |
|---|---|---|
| `POST /v1/trabajos/{id}/cancelar` (con sesión): el trabajo pasa a `cancelado`, terminal. No se cancela un kit comprado (`409 kit_comprado`), uno con pago pendiente (`409 pedido_pendiente`) ni uno en `procesando` (`409 en_proceso`), ni el que hoy es el kit canónico de su grado (`409 kit_canonico`); otra cuenta, `403 solicitud_ajena` | §4 | Antes una solicitud no se podía deshacer |
| `POST /v1/mis-solicitudes/listas/{tarea_id}/cancelar` (con sesión): la lista subida deja de ser del acudiente, sin borrarse | §4 | La lista es del colegio y sirve a otros |
| `EstadoTrabajo` suma `cancelado`; "Mis solicitudes" no lo devuelve y la lista `recibida` trae `tarea_id` | §4 | Para poder cancelarla |
| `DELETE /v1/cuenta/matriculas/{matricula_id}` (204) y `PUT` con `{colegio_id, grado, apodo?}`: quitar cierra el vínculo sin borrar; cambiar retira la matrícula y crea la nueva con el mismo apodo | §12.4 | Corregir el colegio o quitar a un hijo desde el panel |
| `GET /v1/cuenta/matriculas` trae `matricula_id` | §12.4 | Para pedir el cambio |

### Qué cambió en 1.5

Ya no se arman siempre tres kits: se arman los que el acudiente pidió (ADR 0030).

| Cambio | Dónde | Por qué |
|---|---|---|
| Siempre `Ahorrador` y `Premium`; `Fan` solo con `personaje_por_hijo`; `A tu Medida` solo con `prioridad: "equilibrio"` o un tope | §5 | Un kit que nadie pidió es ruido para el papá y trabajo para el revisor |
| `PerfilKit` suma `"A tu Medida"`: la mejor marca que cabe en el tope o, sin tope, en la mitad de camino entre Ahorrador y Premium | §1.3, §6 | El punto medio tenía que ser un kit propio, no un Premium ajustado |
| El Premium ya no se ajusta al presupuesto: siempre es la mejor marca | §6 | Ese lugar lo ocupa ahora `A tu Medida` |
| Preferencias suma `prioridad` (`precio`, `equilibrio`, `calidad`) | §3 | Es lo que decide si se arma `A tu Medida` |
| Los canónicos de una lista son Ahorrador y Premium; en la ruta rápida el Fan se arma para quien pide un personaje (el Ahorrador canónico con el personaje en las anclas) y `A tu Medida` no sale de la caché | §5 | Ambos dependen de cada acudiente |

### Qué cambió en 1.4

El acudiente puede cambiar productos de su kit y, en la ruta rápida, ver y pagar cualquiera de
los tres kits. Las decisiones están en el ADR 0028 (`docs/arquitectura/adr/`).

| Cambio | Dónde | Por qué |
|---|---|---|
| `PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` | §5.3 | El acudiente cambia un producto por el sugerido o una de sus alternativas |
| `GET /v1/trabajos/{id}` aplica los cambios del acudiente y trae `cambios` | §4, §5.3 | El kit que ve y el que paga son el que él armó |
| La línea cambiada trae `cambiado_por_acudiente` y `sku_sugerido` | §5.3 | Para decirle qué cambió y ofrecerle volver al sugerido |
| La ruta rápida (`parent_apply`) devuelve los tres kits, con el elegido como `recomendado` | §4, §6 | Antes solo veía el que eligió al empezar y no podía comparar ni cambiarse |

### Qué cambió en 1.3

Ningún campo cambia de forma; cambia qué kit se marca y qué lleva el Premium cuando hay
presupuesto. Sale del benchmark Laya vs NSGA-II.

| Cambio | Dónde | Por qué |
|---|---|---|
| Con `presupuesto_por_hijo` se recomienda la mejor marca que cabe, y el Premium que no cabe se ajusta al mejor punto del frente dentro del tope | §6 | El kit recomendado con presupuesto lograba el 40 % de la calidad posible y el frente ya traía uno del 94 % |
| Si el recomendado no cabe, se cae a la mejor marca que cabe, no al más barato | §6 | Es lo que §6 prometía ("el siguiente punto del frente") y el código no hacía |
| `disposicion_sobreprecio` ya no estira el tope | §6 | Quien escribía "máximo $350.000" podía recibir un kit de $385.000 |

### Qué cambió en 1.2

El §9 pasa de declarado a implementado. Lo que estaba escrito era el diseño al que había que
llegar; al llegar con Wompi de verdad (sandbox, llaves reales) aparecieron tres cosas que el
diseño no podía saber, y se documentan donde muerden.

| Cambio | Dónde | Por qué |
|---|---|---|
| §9 implementado: orden, pago, sincronización, webhook, cancelación y "mis pedidos" | §9 | `comercio` existe y la puerta lo rutea; las rutas ya no responden `501` |
| El pago se abre con el **widget** de Wompi y `POST /pago` devuelve sus datos firmados | §9.1 | El checkout alojado por URL responde 403 si el retorno es `localhost`. ADR 0033 |
| `POST /v1/pagos/{transaccion_id}/sincronizar` | §9.2 | Sin URL pública el webhook no llega, y el pedido se quedaba sin confirmar. ADR 0034 |
| La clave de idempotencia es `<transacción>:<ESTADO>`, no el id del evento | §9.2 | Wompi no manda id de evento, y `PENDING` → `APPROVED` chocaba en el candado |
| `POST /v1/ordenes/{id}/cancelar`, que consulta a Wompi antes | §9.3 | Cancelar con un PSE en curso cobraría sin entregar. ADR 0035 |
| Un pedido se paga durante 24 horas; uno pendiente por kit | §9.4 | Cada clic en Pagar creaba un pedido, y uno viejo se cobraría a un precio viejo |
| `comercio` en la tabla de puertos | §12.1 | Faltaba |

### Qué cambió en 1.1

La 1.0 especificaba el pipeline y no el catálogo, y eso dejaba al frontend sin
poder pintar una sola pantalla antes de que existiera un trabajo. La 1.1 agrega
la **superficie de lectura** (§12) y corrige tres cosas que al implementar
resultaron incompletas o incoherentes con los modelos.

| Cambio | Dónde | Por qué |
|---|---|---|
| Nueva sección 12: catálogo, listas, colegios, emparejamiento | §12 | No existía superficie de navegación. El catálogo estaba en la base y no lo exponía nadie |
| `501 no_implementado` como código de error | §11, §12.1 | `/v1/ordenes` está especificado y no tiene servicio detrás. Un `404` haría buscar un error en el cliente que no está ahí |
| `GET /v1/trabajos/{id}` devuelve también `origen`, `hijos`, `error`, `mensaje`, `creado_en`, `nota_revision`; cada etapa lleva `detalle` | §4 | El frontend no podía distinguir "sin lista publicada" de "el catálogo se cayó" sin ellos |
| `POST /v1/trabajos/{id}/reintentar` | §4.1 | §8 promete que un trabajo fallido es reintentable y no había endpoint que lo hiciera |
| Las líneas del kit traen `hijo`, `orden` y `alternativas` siempre (lista vacía si no hay) | §5 | Agrupar por hijo era imposible sin `hijo`, y un campo que a veces no viene obliga a defenderse en cada punto de uso |
| El total de un trabajo es por **hogar**, no por hijo, y `presupuesto_por_hijo` se compara contra el total del kit | §6 | Se declara porque con un solo hijo son lo mismo y la diferencia solo aparece con dos. Se revisa cuando el optimizador reparta por hijo |
| La entrada (b) por archivo (`multipart/form-data`) queda **declarada y no implementada** | §2 | Requiere `GEMINI_API_KEY` y render de PDF. Hoy solo funciona la entrada (a), por colegio y grado |
| §9 (pago) queda **declarada y no implementada** | §9 | El servicio `comercio` todavía no existe |

---

## 0. Por qué la API es asíncrona

El pipeline tarda minutos, no segundos. `OP-03` del SRS lo acota en cinco minutos de
extremo a extremo en el peor caso, y exige **progreso visible por etapa** mientras dura el
procesamiento. Una API síncrona no puede ofrecer ese progreso, y por eso el recurso central
no es el kit sino el trabajo. El tiempo de cada etapa lo acotan `DP-04` (percepción),
`DP-03` (optimización) y `DP-06` (camino corto sobre lista validada), y el
`estimado_segundos` que se le anuncia al acudiente debe ser el del camino que su trabajo va
a tomar, no uno único para los dos.

Encima, el flujo de negocio **exige** una pausa humana: los kits pasan por revisión de
Admin Tukit (`AD-01`, `AD-02`, `AD-03`) antes de llegar al acudiente (`AD-06`). Una API
síncrona no puede modelar una espera que incluye a una persona.

Por eso el recurso central no es "el kit" sino **el trabajo**: se crea, se consulta, y
cuando termina se avisa por los canales que el acudiente dejó.

```mermaid
sequenceDiagram
    participant W as apps/web
    participant I as inteligencia
    participant A as apps/admin
    participant O as operacion
    W->>I: POST /v1/trabajos
    I-->>W: 202 {trabajo_id, estado: encolado}
    I->>I: parseo, resolucion, optimizacion
    I-->>A: estado = espera_revision
    A->>I: POST /v1/trabajos/{id}/revision
    I->>O: publica kits_publicados
    O-->>W: correo + wa-link
    W->>I: GET /v1/trabajos/{id}
    I-->>W: 200 {estado: publicado, kits}
```

---

## 1. Tipos compartidos

### 1.1 `TipoItem`

Extiende el `TipoItem` que el frontend ya tiene (`util | texto | uniforme | otro`). Los
tres valores nuevos existen porque hay ítems de la lista que **no son productos
comprables**, y forzarles un emparejamiento sería un defecto, no cobertura.

| Valor | Qué es | Qué hace el pipeline |
|---|---|---|
| `util` | Papelería comprable | Busca producto, ofrece 3 niveles |
| `texto` | Texto escolar con edición obligatoria | **No busca**: resuelve por `version_vigente` a un ISBN |
| `libro_libre` | Libro sin editorial exigida | **Sí busca**, y optimiza por precio |
| `licencia_digital` | Licencia con pago externo | No entra al carrito; expone `url_externa` |
| `no_comprar` | "El disponible en casa" | Cantidad cero, con la instrucción visible |
| `diferido` | "Se solicitará más adelante" | Queda pendiente; reabre el trabajo al publicarse |
| `uniforme` | Uniforme | Fuera de alcance de v1, declarado |
| `otro` | No clasificable | Va a revisión humana |

Todo lo que no sea `util`, `texto` o `libro_libre` **no cuenta** para la métrica de
"catálogo sin huecos": esa se mide solo sobre lo comprable.

### 1.1.1 `ModoAdquisicion`: quién puede vender el ítem

Ortogonal a `TipoItem`, y es la diferencia entre un catálogo que promete y uno que cumple.
Salió de leer los 14 PDF originales: **hay textos que Tukit no puede surtir, y no por falta
de proveedor sino porque el colegio los cerró**.

| Valor | Señal en la lista | ¿Tukit lo surte? |
|---|---|---|
| `mercado_abierto` | Sin restricción declarada | Sí |
| `libro_libre` | "Cualquier editorial" | Sí, y es donde más aporta |
| `venta_directa_editorial` | "Venta directa a las familias", "tienda virtual de la editorial" | No |
| `edicion_exclusiva` | "Edición exclusiva para la institución" | No |
| `plataforma` | "Link de pago", "código de acceso" | No |
| `diferido` | "Se solicitarán acordes a las necesidades de la clase" | Todavía no |

Dos casos reales que fijan los extremos. Osito de Miel: *"el jardín ofrece las instalaciones
a las diferentes editoriales para que les hagan la venta directa a las familias sábado 24
enero... las editoriales reciben dinero en efectivo"*. Y en la otra punta, *"La casa de los
espíritus. Autor: Isabella Allende. Cualquier editorial"*, donde la restricción se **invierte**:
no hay una sola edición válida sino muchas, y el sistema puede escoger la más barata.

Que el caso `libro_libre` no estuviera modelado era un hueco caro: es el segmento de libros
donde Tukit agrega más valor, porque es el único donde tiene margen para optimizar.

### 1.2 `EstadoResolucion`

Conserva los tres que el frontend ya conoce y agrega el que faltaba:

| Valor | Significado |
|---|---|
| `RESUELTO_AUTO` | Confianza sobre el umbral; hay producto elegido |
| `AMBIGUO` | Zona gris; hay candidatos pero ninguno domina. Va a revisión |
| `SIN_MATCH` | No hay candidato admisible |
| `HUECO_CATALOGO` | **Nuevo.** Se entendió qué pide y el catálogo no lo tiene |

La diferencia entre `SIN_MATCH` y `HUECO_CATALOGO` es la que hoy no existe y es la que
permite decir *"no tengo block carta"* en vez de ofrecer origami con confianza. `SIN_MATCH`
es "no te entendí"; `HUECO_CATALOGO` es "te entendí y no lo tengo", y solo el segundo se
puede responder con una alternativa o una disculpa útil.

### 1.3 `PerfilKit`

`Ahorrador | Fan | A tu Medida | Premium`. Los tres primeros los nombran `OP-01` y `UI-02` del
SRS; `A tu Medida` llega en 1.5. Ahorrador y Premium salen siempre; Fan y A tu Medida solo si el
acudiente los pide (§5, ADR 0030).

**No confundir con el `nivel` de un producto** (`economico | confiable | premium`). Son
ejes distintos que comparten la palabra "premium": el nivel describe un producto, el perfil
describe una ponderación de objetivos sobre el kit completo. Un kit `Ahorrador` puede
contener un producto `premium` si resultó más barato por empaque.

### 1.4 `Dinero`

Entero en pesos colombianos. Nunca flotante, nunca string. `null` significa "no se conoce
el precio", que es distinto de `0`.

---

## 2. Crear un trabajo

`POST /v1/trabajos` → `202 Accepted`

La petición es **por hogar, no por hijo**. Es la decisión de diseño que hace posible la
consolidación entre hermanos y el reparto de empaques: si cada hijo se pidiera aparte, el
optimizador no podría ver que dos niños necesitan un borrador cada uno y que una caja de
diez sale mejor.

Dos formas de entrar, las dos del SRS:

```jsonc
// (a) El colegio ya publicó la lista: CO-01, o reconstruida por NR-07 y distinguida por NR-08
{
  "contacto":  { "correo": "papa@ejemplo.com", "celular": "+573001234567" },
  "hijos": [
    { "referencia": "hijo-1", "colegio_id": "2.4", "grado": "Cuarto" },
    { "referencia": "hijo-2", "colegio_id": "2.4", "grado": "Septimo" }
  ],
  "preferencias": { /* ver §3 */ }
}
```

```jsonc
// (b) El acudiente sube la lista: multipart/form-data
//     campo `hijos` con el JSON de arriba y un `archivo` por hijo
//     Formatos y límites: los que ya valida el frontend
//     (.pdf .jpg .jpeg .png .webp, 10 MB)
```

> **Estado en 1.1: (a) funciona, (b) todavía no.** El endpoint solo acepta JSON; mandarle
> `multipart` devuelve `400 entrada_invalida`. La etapa de percepción existe y está probada
> (`tukit_inteligencia.percepcion`, con las reglas de §2.1 ya impuestas), pero conectarla
> pide `GEMINI_API_KEY` y el render de PDF, y ninguna de las dos es una decisión de
> contrato. La ruta (a) cubre los 17 colegios del corpus con sus 175 listas cargadas, así
> que el frontend puede construirse entero contra ella.

Si **ningún** hijo tiene lista en el catálogo para su (colegio, grado, año), la petición se
rechaza en el acto con `422 sin_lista_oficial` y no se encola nada: el grado sin lista va por
`POST /v1/listas/subir`. Un hogar donde solo algunos hijos tienen lista sigue con `202` y
el kit anota al que faltó. Con el catálogo caído no se puede saber y se encola como siempre.

### 2.1 Un archivo es la lista de UN grado, y eso se verifica

**Regla de negocio, no límite técnico.** El archivo tiene que ser la lista del grado de ese
hijo. Si el acudiente sube el PDF completo del colegio —que trae los trece grados— el
sistema **no lo procesa**: se lo dice y le pide las páginas de su grado.

No se procesa "lo que se pueda" porque un kit armado con los útiles de otro grado es peor
que no tener kit: el acudiente no tiene cómo notar el error hasta que llega el pedido. Esto
no es hipotético, los archivos del corpus son así: el de CACS tiene **39 páginas** y el de
San Pedro **22**; los catorce suman 199.

El aviso es explícito antes de subir, porque una restricción que solo aparece como error
después de esperar es una restricción mal puesta.

```jsonc
// 422
{ "error": "lista_de_varios_grados",
  "mensaje": "Este archivo tiene la lista de 13 grados. Sube solo las páginas del grado de tu hijo.",
  "grados_detectados": ["Jardin", "Transicion", "Primero", "..."],
  "paginas": 39 }
```

**Cómo se detecta.** La señal buena es **cuántos grados distintos aparece**, que es lo que
de verdad importa, y la reporta el mismo modelo de la etapa de percepción que ya se llama.
El número de páginas es solo una guarda barata previa, porque como criterio falla en los dos
sentidos: hay listas de un grado que ocupan seis páginas y listas de tres grados que caben
en dos.

Esto además cierra un defecto de producción real: la etapa de percepción tenía un tope de
cinco páginas que **truncaba en silencio**, sin avisar ni marcar el kit como parcial. Leer
cinco páginas de un PDF de 39 y devolver un kit con toda confianza es el peor
comportamiento posible de los tres (procesar todo, rechazar, o truncar callado).

### 2.2 La otra entrada depende de que el mapeo colegio–lista sea correcto

Cuando el acudiente elige colegio y grado en vez de subir archivo, el sistema le muestra la
`version_lista_oficial` vigente de ese `(sede, grado, anio_lectivo)`. Ahí el acudiente **no
puede detectar el error**: confía en que la lista que le mostramos es la de su colegio.

Por eso la ambigüedad que quedó abierta en la extracción del corpus —dos PDF que comparten
plantilla y no se pudieron separar con confianza, con 115 renglones en juego— deja de ser
una imprecisión de datos y pasa a ser **un bloqueante de corrección de esta ruta**. Una
lista atribuida al colegio equivocado es exactamente el fallo que esta entrada no puede
tener.

Respuesta:

```json
{
  "trabajo_id": "3f9a...",
  "estado": "encolado",
  "estimado_segundos": 180,
  "consultar_en": "/v1/trabajos/3f9a..."
}
```

`contacto` es obligatorio: es lo que permite avisar cuando el trabajo termine, y sin él la
asincronía no tiene salida. Se guarda en `identidad` y la notificación lo referencia **por
identificador, nunca copiando el correo**, según la nota del manifiesto sobre la deuda
heredada en `operacion.notificacion`.

---

## 3. Preferencias: lo que el acudiente declara, no lo que inferimos

```jsonc
{
  "pesos": {                      // suma 1.0; de la P21 de la encuesta
    "precio":         0.35,
    "marca_exigida":  0.30,
    "calidad":        0.25,
    "personaje":      0.10
  },
  "presupuesto_por_hijo": 700000, // restricción DURA, no una pista
  "disposicion_sobreprecio": 0.05,
  "personaje_por_hijo": { "hijo-1": ["spiderman"] },
  "dolor_declarado": "libros"     // solo decide el titular de la UI
}
```

Tres reglas que este bloque impone y conviene no relajar:

1. **No se pide el estrato y no se persiste.** En las 60 respuestas de la encuesta, 41 son
   estrato 4: no tiene varianza suficiente para segmentar, y sí es dato sensible del hogar
   de un menor. Como además la correlación intuitiva no existe —el segmento que más gasta
   es el *menos* dispuesto a pagar sobreprecio— quitarlo no cuesta precisión.
2. **`presupuesto_por_hijo` es una cota, no un gusto.** Es el uso más valioso de la
   encuesta: convierte una opinión en una restricción que el optimizador puede imponer.
3. **Los pesos son datos personales derivados.** Se persisten cifrados en `kit.perfil` y
   `kit.pesos_usados`, y entran al derecho al olvido. El manifiesto ya documenta que el
   servicio anterior los dejaba en claro y los excluía del borrado.

Si el bloque viene vacío se usan los valores por defecto medidos: precio 0.35, marca
exigida 0.30, calidad 0.25, personaje 0.10, que es el orden que dio la P21 normalizado.

---

## 4. Consultar un trabajo

`GET /v1/trabajos/{id}` → `200 OK`

```jsonc
{
  "trabajo_id": "3f9a...",
  "estado": "publicado",
  // encolado | procesando | espera_revision | publicado | fallido
  "etapas": [
    { "nombre": "percepcion",   "estado": "ok", "ms": 4210 },
    { "nombre": "normalizacion","estado": "ok", "ms": 890  },
    { "nombre": "resolucion",   "estado": "ok", "ms": 12400 },
    { "nombre": "optimizacion", "estado": "ok", "ms": 6100 }
  ],
  "kits": [ /* §5 */ ],
  "recomendado": { /* §6 */ },
  "degradaciones": [ /* §8 */ ]
}
```

Mientras `estado` no sea `publicado`, `kits` va vacío. El acudiente **nunca ve un kit sin
revisar**: esa es la razón de ser de `espera_revision` y de `AD-06`.

La respuesta real trae además `origen`, `hijos`, `error`, `mensaje`, `creado_en`,
`terminado_en`, `nota_revision` y un `detalle` por etapa. Ver §12.6, con un cuerpo
completo tal como responde hoy.

### 4.1 Reintentar

`POST /v1/trabajos/{id}/reintentar` → `200 OK`

Existe porque §8 promete que un trabajo `fallido` es reintentable, y una promesa sin
endpoint no se puede cumplir. Vuelve a encolar sin que el acudiente tenga que rehacer nada:
el trabajo guardó su entrada y sus etapas.

Solo desde `fallido` o `encolado`. Desde cualquier otro estado es `409 estado_incompatible`,
porque reprocesar un trabajo que ya está publicado reescribiría kits que el acudiente ya
vio.

---

## 5. Los kits

Son puntos del frente de Pareto que produce el optimizador, no consultas distintas. `OP-04`
pide poder parametrizar los pesos, y eso es exactamente lo que los separa. Desde 1.5 no son
siempre tres (ADR 0030): `Ahorrador` y `Premium` salen siempre, `Fan` solo si el acudiente
pidió un personaje y `A tu Medida` solo si eligió el punto medio o declaró un tope. Los
canónicos de una lista (sin preferencias) son dos.

```jsonc
{
  "perfil": "Ahorrador",
  "total": 412000,
  "objetivos": { "costo": 412000, "fidelidad": 0.61, "disponibilidad": 0.94 },
  "lineas": [
    {
      "item_id": "h1-007",
      "hijo": "hijo-1",
      "descripcion": "Caja de lapices x12",
      "tipo": "util",
      "estado_resolucion": "RESUELTO_AUTO",

      // El corazón del arreglo de unidades. Tres números distintos que el
      // sistema anterior colapsaba en uno, y de ahí salía sumar 12 cajas
      // cuando la lista pedía 12 lápices.
      "cantidad_pedida":      12,        // en unidad base
      "unidad_base":          "unidad",
      "unidades_por_empaque": 12,
      "unidades_a_comprar":   1,         // techo(12 / 12)

      "producto_elegido": {
        "sku": "TK-C002-PRE",
        "nombre": "Caja De Lapiz Kores Jumbo HB #2 X12 Negro",
        "marca": "Kores",
        "nivel": "premium",
        "personaje": null,
        "imagen_url": "https://...",
        "confianza": 0.91,
        "ofertas": [
          { "tienda": "panamericana", "precio": 18900, "vigente_hasta": "2026-09-28T00:00:00Z" },
          { "tienda": "suescun",      "precio": 17400, "vigente_hasta": "2026-09-24T00:00:00Z" }
        ]
      },
      "alternativas": [ /* hasta 2 más, mismo concepto, otros niveles */ ],
      "subtotal_linea": 17400
    }
  ],
  "consolidaciones": [
    {
      "concepto": "C005 borrador",
      "hijos": ["hijo-1", "hijo-2"],
      "demanda_base": 2,
      "producto": "TK-C005-ECO-CAJA",
      "unidades_a_comprar": 1,
      "ahorro": 1200,
      "explicacion": "Una caja de 10 sale más barata que dos borradores sueltos."
    }
  ]
}
```

### 5.1 Líneas que no son productos

```jsonc
{ "item_id": "h1-021", "tipo": "licencia_digital",
  "descripcion": "Plan lector virtual RAZ-PLUS",
  "url_externa": "https://pagoslearning.com/",
  "nota": "Se adquiere directamente con QUOVIX. No va en el carrito.",
  "subtotal_linea": null }

{ "item_id": "h1-022", "tipo": "no_comprar",
  "descripcion": "Diccionario: el disponible en casa",
  "unidades_a_comprar": 0,
  "nota": "El colegio indica usar el que ya tienes." }

{ "item_id": "h2-004", "tipo": "texto",
  "descripcion": "Don Quijote de la Mancha. Ed Enlace. (primer periodo)",
  "estado_resolucion": "RESUELTO_AUTO",
  "edicion": { "isbn13": "9789580000000", "titulo": "Don Quijote de la Mancha",
               "editorial": "Enlace", "anio_edicion": 2023 },
  "no_consolidable": true,
  "motivo_no_consolidable": "Dos ediciones del mismo título no son sustituibles." }
```

`no_consolidable` es la **regla inversa** de la consolidación entre hermanos: los
borradores se juntan y los textos nunca, y el sistema dice por qué. Sale del mismo dato
—`version_vigente` guarda histórico— y de la misma razón que documenta el modelo editorial.

### 5.1.1 Líneas informativas: lo que el colegio pide y Tukit no puede vender

```jsonc
{ "item_id": "h1-030", "tipo": "texto",
  "descripcion": "Sistema Flex TAC-Lenguaje 1. Ed. Libros y libros",
  "modo_adquisicion": "edicion_exclusiva",
  "informativa": true,
  "instruccion_colegio": "Edición exclusiva para la institución. Se adquiere directamente con la editorial.",
  "precio": null,
  "subtotal_linea": null }
```

`informativa: true` significa **se muestra, no se cobra**. La línea aparece en el kit con la
instrucción textual del colegio, y queda fuera del carrito, del total y del conteo de
cobertura.

Se muestran en vez de ocultarse porque el acudiente necesita saber que esos ítems existen y
cómo conseguirlos: el dolor que la encuesta mide es *recorrer papelerías y perder tiempo*,
y una lista incompleta reproduce ese dolor aunque el carrito se vea más limpio. Decir "esto
lo vende la editorial el 24 de enero en el colegio" es útil; callarlo es dejar al papá con
un hueco que descubre tarde.

Y no se cobran porque prometer lo que no se puede entregar es el modo de falla más caro del
negocio. `FU-08` congela el precio al confirmar, así que una línea que Tukit no controla no
puede entrar al total.

**El total de cada kit incluye solo líneas con `informativa: false`.** El frontend muestra
el conteo aparte: *"3 ítems los gestiona directamente el colegio"*.

### 5.2 Huecos

```jsonc
{ "item_id": "h1-013", "tipo": "util",
  "descripcion": "Block oficio",
  "estado_resolucion": "HUECO_CATALOGO",
  "concepto": "C003 block",
  "atributo_faltante": { "tamano": "oficio" },
  "mensaje": "Entendimos que pides un block tamaño oficio y hoy no lo tenemos.",
  "sustitutos": [ /* del grafo de sustituibilidad, si los hay */ ],
  "subtotal_linea": null }
```

---

### 5.3 El acudiente cambia un producto de su kit

`PUT /v1/trabajos/{id}/kits/{perfil}/lineas/{item_id}/producto` → `200 OK`

```jsonc
// petición
{ "sku": "TK-C001-PRE" }
// respuesta
{ "trabajo_id": "3f9a...", "perfil": "Ahorrador", "item_id": "h1-007", "sku": "TK-C001-PRE" }
```

- Solo se acepta el producto sugerido de esa línea o una de sus `alternativas`. Cualquier otro
  sku responde `422 producto_no_permitido`: el acudiente elige entre lo que una persona revisó.
- El cambio se guarda en el trabajo del acudiente, **nunca** en las líneas del kit, que pueden ser
  el kit canónico de su grado (ADR 0028). `GET /v1/trabajos/{id}` lo aplica al leer, recalcula
  el total y lo devuelve en `cambios` (`{perfil: {item_id: producto}}`). El pago lee ese mismo kit.
- La línea cambiada trae `cambiado_por_acudiente: true` y `sku_sugerido`. El sugerido queda entre
  las `alternativas`; elegirlo de nuevo borra el cambio.
- Si el trabajo tiene dueño, va con su sesión (`Authorization: Bearer`): otra sesión o ninguna
  responde `403 solicitud_ajena`. Un trabajo sin dueño (ruta rápida sin cuenta) no la pide.
- Otros errores: `409 kit_no_publicado`, `409 linea_sin_producto`, `409 linea_consolidada` (se
  compra junto con la de un hermano), `409 producto_sin_precio`, `404 linea_no_existe`.

## 6. La recomendación

Se muestran los tres (`OP-01` lo exige) y se marca **uno**, con la razón en lenguaje llano.
Nunca se ocultan los otros dos.

```jsonc
{
  "perfil": "Ahorrador",
  "razon": "Elegiste precio como lo más importante y el kit queda en $412.000, dentro de tu presupuesto.",
  "dentro_de_presupuesto": true,   // null si no declaró presupuesto; solo false es pasarse
  "pesos_usados": { "precio": 0.35, "marca_exigida": 0.30, "calidad": 0.25, "personaje": 0.10 }
}
```

Recomendar es **escalarizar el frente de Pareto** con los pesos de ese acudiente: los tres
kits son óptimos y cuál conviene depende de preferencias que no están en el catálogo. La
regla, derivada de la encuesta:

- **`Fan`** solo con `personaje_por_hijo` explícito. El personaje quedó último en la P21
  (1,87 contra 2,85 del precio), y tiene sentido: el que paga es el papá y el que quiere el
  personaje es el hijo.
- **`A tu Medida`** si el acudiente eligió el punto medio (`prioridad: "equilibrio"`) o
  declaró un tope. Es el punto del frente con mayor fidelidad cuyo costo cabe en el tope; sin
  tope, el tope implícito es la mitad de camino entre el total del Ahorrador y el del Premium.
  El tope es `presupuesto_por_hijo` tal cual: `disposicion_sobreprecio` no lo estira, porque
  dice cuánto más pagaría por marca sin tope, no cuánto se puede pasar del tope que él mismo
  puso. Si no hay un kit distinto que armar (el tope alcanza para el Premium entero, o no
  alcanza para subir ninguna marca), no se arma y `razon` dice por qué se marca el otro (ADR 0030).
- **Por defecto `Ahorrador`.** 42 de 60 encuestados pagan como máximo 5 % más y 15 exigen
  precio igual o menor.
- **`Premium`** solo si el acudiente pone calidad primero **y** declara ≥10 %.
- Si el recomendado excede el tope, se cae al kit de mejor marca que sí cabe (no al más
  barato) y `razon` lo dice. Si ninguno cabe, se marca el más barato y `razon` dice cuánto
  cuesta: "Ningún kit cabe en tu tope de $400.000: el más barato que se puede armar con esta
  lista cuesta $443.255".

El benchmark Laya vs NSGA-II (rama `bench/laya-vs-nsga`) midió por qué: caer al kit más
barato lograba el 40 % de la calidad posible con presupuesto, mientras el frente ya traía
un kit que cabía y lograba el 94 %. Con esta regla, en las 174 listas del benchmark, el kit
recomendado cabe siempre e iguala la mejor marca posible dentro del tope.

---

## 7. Revisión humana (apps/admin)

| Endpoint | Requisito |
|---|---|
| `GET /v1/admin/cola` | `AD-01`, `AD-03` |
| `GET /v1/admin/trabajos/{id}` | `AD-04` |
| `POST /v1/admin/trabajos/{id}/lineas/{item_id}/validar` | `AD-02` |
| `POST /v1/admin/trabajos/{id}/lineas/{item_id}/sin-coincidencia` | `AD-02` |
| `POST /v1/admin/productos` | `AD-07` — alta manual con precio e imagen |
| `POST /v1/admin/productos/{sku}/no-disponible` | `AD-05` |
| `POST /v1/admin/trabajos/{id}/revision` | `AD-06` — publica al acudiente |

**La sesión (1.12).** Todo `/v1/admin/*` es del equipo: el gateway valida el Bearer contra
`GET /v1/sesiones/actual` antes de reenviar, y sin sesión responde `401 sesion_invalida`, sin
rol `admin` u `operador` `403 acceso_denegado`, y si Identidad no responde
`503 identidad_no_disponible`. La única excepción es `POST /v1/admin/sugerencias` (la sugerencia
de un acudiente desde la web pública). La misma sesión cierran las escrituras de consola que
viven fuera de `/v1/admin`: `PATCH`/`DELETE /v1/catalogo/productos/{sku}`,
`POST /v1/catalogo/productos/{sku}/reclasificar` y `PATCH /v1/colegios/{colegio_id}`. Las
llamadas internas entre servicios no pasan por el gateway y no cambian.

La cola se alimenta de `PE-04`: "marcar para revisión de Admin Tukit los ítems con
confianza de extracción por debajo del umbral configurable τ". Toda transición queda en
`operacion.registro_auditoria` con quién y cuándo, que es lo que exigen el criterio de
`AD-02`, `ML-06`, `SG-02` y el criterio de `AD-06`.

`POST .../revision` acepta `{ "decision": "aprobar" | "devolver", "nota": "..." }`. Aprobar
publica y dispara la notificación; devolver reabre el trabajo sin avisar al acudiente.

`POST .../validar` acepta `{ "sku"?, "nota"? }`. Sin `sku` confirma el producto que la línea
tiene en el kit recomendado; un `sku` que no era candidato del renglón (el personaje del Fan, un
producto fijado por kit) se registra como candidato y se valida. Sin producto por ningún lado,
o con un `sku` que el catálogo no conoce, `422 sin_producto_que_validar` con `campo: "sku"`. El
estado se copia a la línea en todos los kits, para que deje de salir como pendiente.

`POST .../sin-coincidencia` deja la línea sin producto ni precio en todos los kits y recalcula
sus totales: "no lo tenemos" no se puede cobrar. Las alternativas se conservan para fijar una
después.

---

## 8. Degradación: degradar, nunca tumbar

Toda dependencia tiene una ruta declarada. Ningún fallo externo devuelve `500` si existe
una respuesta parcial honesta.

| Dependencia | Falla | Qué pasa |
|---|---|---|
| Gemini (percepción) | Sin respuesta | `502` con mensaje accionable; el trabajo queda `fallido` y reintentable |
| Gemini (percepción) | Salida truncada | Se marca la página como incompleta y va a revisión. **Nunca se recorta en silencio** |
| Embeddings | No disponible | Solo canal léxico, y **toda** línea baja a `AMBIGUO` |
| Reranker | No disponible | Se ordena por el canal vectorial, que mide mejor que la fusión |
| Precio vencido | `vigente_hasta` pasado | La línea no entra al total y se marca para revisión |
| Pasarela | Sin respuesta | La orden queda `pendiente_pago`; nunca se confirma sin confirmación |
| Catálogo, en la subida del acudiente (`POST /v1/listas/subir`) | Sin respuesta, 5xx, 408 o 429 | `202`. Lo que no se importó queda guardado con lo ya percibido, y su hijo trae `version_id: null` y `estado: "pendiente"`. El trabajador lo importa cuando el catálogo vuelve, con la misma `clave_idempotencia`: una sola versión (ADR 0040) |
| Catálogo, en el onboarding del admin (`POST /v1/admin/onboarding`) | Sin respuesta, 5xx, 408 o 429 | `503 servicio_no_disponible`; la lista no se guarda y el admin reintenta (ADR 0040) |
| Postgres o RabbitMQ, en los procesos de fondo | Sin respuesta | Barredor, pollers, trabajador, repartidor y publicadores esperan (1 s, el doble cada vez, tope de 30 s) y siguen; un error de programación los termina (ADR 0041). Con broker, un evento sin publicar espera en su bandeja, y un mensaje que se estaba procesando vuelve a su cola sin gastar un intento (ADR 0046) |
| Un consumidor, con broker | El manejo de un evento falla | El mensaje vuelve a su cola a los 10 s; al quinto intento queda en `<cola>.descartados`, con el motivo, y se registra como error (ADR 0046) |
| Redis, en la caché de lecturas y de vectores | Sin respuesta, más de 250 ms o sin `REDIS_URL` | Se calcula como sin caché: la lista se vuelve a leer y los vectores se vuelven a pedir. La respuesta es la misma y no hay degradación que reportar, porque no se pierde nada. Un registro por episodio, no por petición (ADR 0047) |
| Redis, en el límite de tasa del gateway | Sin respuesta, más de 250 ms o sin `REDIS_URL` | El gateway cuenta en su memoria. Con una réplica protege igual; con varias, cada una cuenta por su lado. Nunca un `500` (ADR 0047) |

Las degradaciones se reportan, no se esconden:

```jsonc
"degradaciones": [
  { "dependencia": "reranker", "efecto": "orden por similitud vectorial", "lineas_afectadas": 7 }
]
```

---

## 9. Pago (comercio)

> **Estado en 1.2: implementado contra Wompi sandbox.** Las rutas tienen servicio detrás
> (`comercio`, puerto 8014) y la puerta las rutea; ya no responden `501`. Solo existe el modo de
> **pruebas**: con `WOMPI_MODO=sandbox` el servicio no arranca si alguna llave no es de prueba, y
> con `WOMPI_MODO=falso` (por omisión) una pasarela simulada permite caminar todo el flujo sin
> red. Producción no está en este contrato. Las decisiones están en los ADR 0033 a 0035
> (`docs/arquitectura/adr/`).

| Endpoint | Requisito | Qué hace |
|---|---|---|
| `POST /v1/trabajos/{id}/ordenar` | `FU-01`, `FU-03` | La entrada del navegador (la sirve `inteligencia`): arma la orden desde el kit elegido e inicia el pago |
| `POST /v1/ordenes` | `FU-01` | Re-verifica precios, congela y reserva. Un pendiente idéntico del mismo kit se reutiliza (§9.4) |
| `POST /v1/ordenes/{id}/pago` | `FU-03` | Un intento de pago nuevo: devuelve los datos firmados del widget de Wompi |
| `POST /v1/pagos/{transaccion_id}/sincronizar` | `FU-03` | Pregunta a Wompi por la transacción y la aplica (§9.2) |
| `POST /v1/webhooks/wompi` | `FU-03` | La misma aplicación, por el aviso firmado de Wompi |
| `POST /v1/ordenes/{id}/cancelar` | `FU-01` | Cancela un pendiente, solo si Wompi no tiene un pago aprobado o en curso (§9.3) |
| `GET /v1/ordenes/{id}` | `FU-01` + `UM-03` | Seguimiento: el pedido con líneas, último pago y envío |
| `POST /v1/ordenes/{id}/retracto` | `FU-04` | Registra la devolución y cancela si la transición lo permite |
| `GET /v1/comercio/mis-pedidos` | `UM-03` | Los pedidos del portador del Bearer, para su panel |
| `GET /v1/comercio/mis-pedidos/{id}` | `UM-03` | Uno de sus pedidos, sin datos del reparto, con su línea de tiempo (§9.7). Ajeno: `404` |
| `POST /v1/comercio/mis-pedidos/{id}/pago` | `FU-03` | §9.1 sobre un pedido suyo |
| `POST /v1/comercio/mis-pedidos/{id}/cancelar` | `FU-01` | §9.3 sobre un pedido suyo |
| `GET /v1/comercio/pedidos` | — | Tablero de logística. Solo operador o admin |
| `GET /v1/comercio/pedidos/{id}` | — | Detalle con celular del repartidor e historial. Solo operador o admin |
| `POST /v1/ordenes/{id}/avanzar` | — | Avanza el pedido por la entrega. Solo operador o admin |

La puerta (§12.1) solo expone `POST /v1/ordenes/{id}/avanzar` bajo `/v1/ordenes`: crear, pagar,
leer, cancelar y retractar una orden son llamadas internas (`inteligencia` le habla directo a
`comercio`). El acudiente paga y cancela desde el navegador por `/v1/comercio/mis-pedidos/{id}`,
donde `comercio` comprueba con la sesión que el pedido sea suyo.

Tres invariantes que no se negocian, y siguen siendo los de 1.1:

1. **Re-verificación antes de cobrar** (`UI-05`, `SC-05`): `POST /v1/ordenes` vuelve a leer el
   precio de cada línea en `catalogo`; si cambió, `422 precio_cambiado` y la orden no se cierra.
   Con `catalogo` caído, `503 catalogo_no_disponible`: no se cobra a ciegas.
2. **El precio no se mueve después de confirmar** (`FU-08`, ADR 0012), con un límite nuevo: un
   pedido se puede pagar durante **24 horas**. Después se cobraría un precio viejo, y el acudiente
   vuelve a armar el kit, donde el precio se re-verifica (§9.4).
3. **No se guardan medios de pago** (`SG-03`). La tarjeta, la cuenta y el celular se digitan en el
   widget de Wompi y Tukit nunca los ve. Se persisten la referencia, el id de transacción, el
   estado, el monto y el medio (`tarjeta`, `pse`, `nequi`) que Wompi reporta.

### 9.1 Iniciar un pago: el widget

`POST /v1/ordenes/{id}/pago` crea un **intento** (un pedido puede tener varios: uno rechazado se
reintenta) con su propia referencia, `tukit-<pedido_id>-<n>`. No llama a Wompi: devuelve lo que el
navegador le pasa a `new WidgetCheckout({...})`, ya firmado.

```json
// POST /v1/ordenes/{id}/pago
{ "correo_cliente": "ana@ejemplo.com", "metodo": "pse",
  "url_redireccion": "http://localhost:3000/pago/resultado" }
```

```jsonc
// 201
{ "pago_id": "…", "referencia_wompi": "tukit-…", "transaccion_wompi": null,
  "estado": "iniciado",
  "url_redireccion": null,          // solo la pasarela simulada redirige
  "widget": {
    "publicKey": "pub_test_…", "currency": "COP", "amountInCents": 105603000,
    "reference": "tukit-…",
    "signature": { "integrity": "<sha256(referencia + centavos + COP + secreto)>" },
    "customerData": { "email": "ana@ejemplo.com" },
    "redirectUrl": "http://localhost:3000/pago/resultado" } }
```

La firma de integridad se calcula aquí porque necesita el secreto, que nunca sale del servidor.
`redirectUrl` existe por PSE, que se lleva la pestaña al banco y vuelve por ahí con `?id=`.
El navegador abre el widget **con `bootstrapTransport: "postmessage"`**: por omisión el widget
mete la configuración en la URL de su iframe, y el CDN de Wompi responde 403 cuando ahí aparece
un retorno a `localhost` (ADR 0033). Con `WOMPI_MODO=falso`, `widget` es `null` y
`url_redireccion` apunta a `/pago/simulado`.

Errores: `404 pedido_no_existe` · `409 pedido_no_pagable` (ya no está pendiente) ·
`409 pedido_vencido` (más de 24 horas) · `422 metodo_invalido`.

### 9.2 Confirmar un pago: sincronización y webhook

El navegador nunca confirma un pago. Al terminar, el widget (tarjeta, Nequi) o el retorno de PSE
entregan el id de la transacción, y la página de resultado pide:

```jsonc
// POST /v1/pagos/{transaccion_id}/sincronizar   → 200
{ "pedido_id": "…", "total": 1056030, "estado_pago": "aprobado",
  "estado_pedido": "pagado", "trabajo_id": "…" }
```

`comercio` consulta `GET /v1/transactions/{id}` en Wompi y aplica la respuesta con **el mismo
aplicador que el webhook** (ADR 0034). Eso hace que funcione en `localhost` sin que Wompi pueda
alcanzar el webhook, y que llegar por los dos caminos no aplique dos veces:

- La idempotencia es contra `evento_pasarela_procesado` con la clave `<transacción>:<ESTADO>`:
  `PENDING` y `APPROVED` de la misma transacción son eventos distintos; un reenvío del mismo
  estado es `repetido`.
- Un pago `aprobado` o `reembolsado` **no retrocede**, y un `PENDING` tardío no revive uno
  `rechazado`.
- Un monto distinto del congelado **no aprueba**: el pago queda `rechazado`.
- En la primera aprobación el pedido pasa a `pagado` y `pedido_pagado` se escribe en la bandeja
  de salida en la misma transacción (§10).
- La consulta exige moneda `COP` y, si Wompi dice de qué comercio es, que sea el nuestro.

`estado_pago` es `iniciado` mientras el banco no responde: la página de resultado vuelve a
preguntar cada 3 s, hasta 20 veces. Errores: `404 transaccion_no_existe` (Wompi no la conoce) ·
`404 pago_no_existe` (la conoce, pero no es de un pago de Tukit) · `502 pasarela_no_disponible`
(se reintenta igual que un `iniciado`).

El webhook responde `200` siempre que el cuerpo sea legible, para que Wompi no reintente en bucle
un evento que nunca se va a aceptar: `{"estado": "ignorado", "motivo": "firma_invalida"}` si la
firma no cuadra, `repetido` si ya se aplicó.

### 9.3 Cancelar

`POST /v1/ordenes/{id}/cancelar` cancela un pedido `pendiente_pago` y libera su reserva de
inventario. Antes **busca en Wompi, con la llave privada, cada intento que siga `iniciado`**,
porque un PSE puede estar en curso o ya aprobado sin que Tukit lo sepa (ADR 0035):

| Lo que encuentra | Respuesta |
|---|---|
| Nada, o solo rechazos | `200` con el pedido `cancelado` y la reserva `liberada` |
| Un pago aprobado | Lo aplica y no cancela: `409 pedido_ya_pagado` |
| Un pago en curso | No cancela: `409 pago_en_curso` |
| Wompi no responde | No cancela: `502 pasarela_no_disponible` |
| El pedido ya no está pendiente | `409 pedido_no_cancelable` |

Si aun así llega una aprobación para un pedido cancelado, el pedido no se mueve (`cancelado` es
terminal), el pago queda `aprobado` y se escribe una **`incidencia`** en la bandeja de salida con
`motivo: "pago_tras_cancelacion"`: el acudiente recibe el aviso y operación ve el caso en su
tablero.

### 9.4 Vigencia y un pedido por kit

- **Vigencia.** Un pedido se puede pagar durante 24 horas desde su `creado_en`; no hay columna
  nueva. Vencido, `POST /pago` responde `409 pedido_vencido`. Se puede cancelar, para liberar lo
  reservado.
- **Un pendiente por kit.** `POST /v1/ordenes` con `trabajo_id`: si el acudiente ya tiene un
  pendiente **idéntico y vigente** para ese kit (mismos productos, cantidades, precios y entrega),
  responde ese mismo pedido y el pago nuevo es otro intento sobre él. Si cambió algo, los
  pendientes anteriores se cancelan con la consulta de §9.3; uno con pago en curso o aprobado, o
  con Wompi caído, se deja como está. Las órdenes sin `trabajo_id` no se deduplican.

### 9.5 El lado del navegador

`apps/web` no habla con estas rutas directamente: lo hace a través de sus rutas de servidor, con
la sesión de la cookie.

| Ruta de `apps/web` | Llama a | Qué agrega |
|---|---|---|
| `POST /api/trabajos/{id}/ordenar` | `POST /v1/trabajos/{id}/ordenar` | — |
| `POST /api/pagos/{transaccion_id}/sincronizar` | §9.2 | — |
| `GET /api/pedidos/{id}` | `GET /v1/comercio/mis-pedidos/{id}` | El detalle para la pantalla de resultado; exige sesión. La página `/pedidos/{id}` lo lee del lado del servidor, sin pasar por esta ruta |
| `POST /api/pedidos/{id}/pagar` | `POST /v1/comercio/mis-pedidos/{id}/pago` | Exige sesión (`401`), que el pedido sea del acudiente (un ajeno es `404`), que siga pendiente y vigente; el correo sale de la sesión |
| `POST /api/pedidos/{id}/cancelar` | `POST /v1/comercio/mis-pedidos/{id}/cancelar` | Las mismas comprobaciones, menos la vigencia |

Las tres reenvían el Bearer de la cookie: `comercio` vuelve a comprobar que el pedido sea del
portador, así que la verificación de `apps/web` es una cortesía para el mensaje, no la puerta.

**Nota de trazabilidad:** `FU-03` nombra **Wompi**, que entrega PSE, Nequi y tarjeta en una sola
integración. La integración vive tras el puerto `PasarelaPago` (`comercio/pasarela.py`), con el
adaptador `WompiSandbox` y uno falso para las pruebas y el desarrollo sin red.

### 9.6 La entrega (nuevo en 1.8)

`entrega` se copia congelada en el `envio` del pedido (ADR 0015). Los tres primeros campos son
los de siempre; el resto es opcional, y un checkout de 1.7 sigue cerrando sin ellos.

| Campo | Largo | Qué es |
|---|---|---|
| `destinatario`, `direccion`, `ciudad` | 256, 512, 128 | Obligatorios |
| `departamento` | ≤ 128 | Lo pre-llena Google o lo escribe el acudiente |
| `indicaciones` | ≤ 512 | "Apartamento, torre, interior o indicaciones" |
| `localidad` | ≤ 64 | El nombre canónico de una de las 20 de Bogotá (`LOCALIDADES_BOGOTA` en `@tukit/contrato`). El formulario la exige en Bogotá y la deja vacía fuera; el servidor solo valida el largo |
| `google_place_id` | ≤ 512 | El `id` del lugar que el acudiente eligió de las sugerencias. Si edita la dirección después, no viaja |

`inteligencia` descarta cualquier otro campo (coordenadas incluidas) antes de llamar a
`comercio`. Un largo de más es `400 entrada_invalida` (con `campo`), en los dos servicios. El
`envio` que se lee de vuelta trae `localidad` y `google_place_id` (o `null`); con ellos `apps/admin` arma el
enlace `https://www.google.com/maps/search/?api=1&query=…&query_place_id=…`
(`enlaceGoogleMaps`).

### 9.7 La línea de tiempo del acudiente (nuevo en 1.8)

`GET /v1/comercio/mis-pedidos/{id}` responde el mismo pedido de antes más `linea_de_tiempo`. La
arma `comercio` (`dominio/linea_de_tiempo.py`), dueño de la máquina de estados; el navegador la
pinta y no recalcula nada.

```json
{"linea_de_tiempo": {
  "pasos": [
    {"paso": "creado",         "estado": "hecho",  "fecha": "2026-10-01T13:00:00+00:00"},
    {"paso": "pagado",         "estado": "hecho",  "fecha": "2026-10-01T13:05:00+00:00"},
    {"paso": "en_preparacion", "estado": "hecho",  "fecha": "2026-10-02T14:00:00+00:00"},
    {"paso": "despachado",     "estado": "actual", "fecha": "2026-10-03T09:00:00+00:00",
     "repartidor_nombre": "Luis Gómez"},
    {"paso": "en_reparto",     "estado": "futuro", "fecha": null},
    {"paso": "entregado",      "estado": "futuro", "fecha": null}],
  "especial": null,
  "entrega_estimada": "2026-10-04T17:00:00+00:00",
  "pago_pendiente": null}}
```

- **Seis pasos, siempre en este orden**, cada uno `hecho`, `actual` o `futuro`. El `actual` es el
  estado del pedido **ahora**, no el paso más lejano al que llegó: tras
  `en_reparto → incidencia → en_preparacion`, despachado y en reparto vuelven a `futuro`.
- **Las fechas no se inventan.** Creado, de `pedido.creado_en`; pagado, del pago aprobado; el
  resto, de la última fila del historial que llegó a ese paso; entregado, si no, de
  `envio.entregado_en`. Sin dato, `null`. Un `futuro` nunca lleva fecha.
- **`especial`**: `null`, `{"tipo": "incidencia", "tipo_incidencia", "fecha"}` (el pedido queda en
  el paso desde el que salió) o `{"tipo": "cancelado", "fecha"}`. Un cancelado no tiene paso
  `actual`: los alcanzados quedan `hecho`. El barredor y el retracto no escriben historial, así
  que un cancelado por vencimiento trae `fecha: null`.
- **`pago_pendiente`**: solo en `pendiente_pago`, `{"vence_en", "vencido"}` con la vigencia de
  §9.4.
- **Lo que nunca trae:** quién hizo cada avance (`actor_id`, `actor_correo`), la `nota` del staff
  ni el celular del repartidor. Del despacho solo viaja `repartidor_nombre`. La función recibe
  vistas recortadas a propósito y no puede filtrarlos.

Los tipos son `LineaDeTiempoPedido` y `PedidoDelAcudiente` en `@tukit/contrato`
(`miPedido` los devuelve), con `ETIQUETA_PASO_PEDIDO` para los nombres visibles.

---

## 10. Notificación (operacion)

> **Estado en 1.1: media implementada, y la mitad que falta es la que entrega.** Al aprobar
> un trabajo, `inteligencia` escribe el evento `kits_publicados` en su bandeja de salida,
> en la MISMA transacción que la publicación. Pero **no hay repartidor** que la lea ni
> servicio `operacion` que la consuma, así que hoy no sale ni correo ni wa-link. Es
> exactamente la deuda que el manifiesto documenta del sistema anterior (la mitad
> transaccional escrita y la de entrega ausente), con la diferencia de que esta vez está
> anotada donde se va a leer. El frontend no puede contar con el aviso: tiene que sondear
> `GET /v1/trabajos/{id}`.

Puerto `Notificador` (`FU-10`) con dos adaptadores en v1:

- **Correo** (`FU-02`), que ya es requisito.
- **wa-link** (`FU-11`): `https://wa.me/<numero>?text=<mensaje con turno>`. Es la vía
  **reactiva**, la que el acudiente inicia. `FU-11` gobierna el número de solicitud que va
  en el enlace y la caducidad del aviso.

El SRS difiere a v2+ "la integración con WhatsApp Business para notificaciones
**proactivas** y no solo reactivas", así que empujar mensajes queda fuera de v1 por
decisión ya tomada, no por omisión. El puerto existe para que la Cloud API oficial entre
después sin tocar el dominio.

El contenido **no repite el correo ni el celular**: los referencia por identificador. Es la
deuda que el manifiesto documenta en `operacion.notificacion`, donde el servicio anterior
persistía el correo real del acudiente y el derecho al olvido no lo borraba.

**Un evento, un aviso (desde 1.8, ADR 0042).** La bandeja entrega cada evento al menos una vez,
así que puede entregarlo otra vez (por ejemplo, si RabbitMQ se cae justo después del envío). La
`notificacion` guarda de qué evento sale, y un evento que ya tiene su aviso `enviada` no se vuelve
a enviar. Un envío que falló sí se reintenta.

### 10.1 Cómo viajan los eventos (nuevo en 1.10)

Ningún cliente HTTP ve los eventos. Se describen aquí porque son el contrato entre servicios.

El evento se escribe siempre en la `bandeja_salida` del productor, en la misma transacción del
cambio. Lo que depende del modo es cómo sale de ahí (ADR 0046):

- **Sin `RABBITMQ_URL`,** como en 1.9: el repartidor y los sondeadores leen la bandeja del
  productor, y el trabajador sondea `trabajo_pipeline`.
- **Con `RABBITMQ_URL`,** el publicador de cada productor lleva su bandeja al exchange topic
  `tukit.eventos`, con el tipo como routing key, y cada consumidor escucha su cola.

| Tipo | Productor | Carga | Cola, con broker |
|---|---|---|---|
| `kits_publicados` | inteligencia | `trabajo_id`, `publicado_en` y `usuario_id` (nuevo en 1.10) | `operacion.avisos` |
| `pedido_pagado`, `incidencia`, `pedido_despachado`, `pedido_en_reparto`, `pedido_entregado` | comercio | sin cambios | `operacion.avisos` |
| `colegio_verificado` | catalogo | sin cambios | `identidad.colegios` |
| `lista_verificada`, `lista_aprobada` | catalogo | sin cambios | `inteligencia.listas` |
| `trabajo_encolado` (nuevo en 1.10, solo con broker) | inteligencia | `trabajo_id` | `inteligencia.trabajos` |
| `pedido_solicitado` | inteligencia | sin cambios | ninguna: el broker lo descarta, como el repartidor lo omite sin broker |

El cuerpo del mensaje es un sobre:

```jsonc
{
  "evento_id": 42,                 // el id en la bandeja del productor
  "origen": "comercio",            // el productor; con evento_id, identifica el evento
  "tipo": "pedido_pagado",
  "agregado_tipo": "pedido",
  "agregado_id": "<uuid>",
  "carga": { "pedido_id": "<uuid>", "usuario_id": "<uuid>" },   // la de la bandeja, tal cual
  "correlacion_id": "<id o null>"
}
```

Las propiedades AMQP repiten lo que sirve para mirar una cola sin abrir el mensaje: `message_id`
es `<origen>:<evento_id>`, `type` es el tipo y `app_id` el origen. La entrega es persistente.

**Al menos una vez.** Un evento puede llegar dos veces, y cada consumidor lo tolera: operación da
un aviso por evento (arriba), identidad es idempotente y el sondeador de listas anota los eventos
que procesó.

**Lo que falla queda visible.** Un mensaje cuyo manejo falla vuelve a su cola a los 10 s. Al
quinto intento queda en `<cola>.descartados`, con el motivo en la cabecera `tukit-motivo`. Una
caída de la base o del broker no cuenta como intento.

---

## 11. Errores

```json
{ "error": "presupuesto_invalido",
  "mensaje": "El presupuesto por hijo debe ser un entero positivo en pesos.",
  "campo": "preferencias.presupuesto_por_hijo" }
```

`400` entrada inválida · `404` no existe · `409` estado incompatible (por ejemplo, revisar
un trabajo ya publicado) · `422` entrada válida que el dominio rechaza · `429` demasiadas
peticiones (§11.1) · `501` ruta especificada en este contrato sin servicio detrás todavía ·
`502` dependencia externa caída · `503` servicio no disponible.

`501` se agregó en 1.1 y la distinción con `404` no es formalismo. Un `404` dice "te
equivocaste de URL" y manda a revisar el cliente; un `501` dice "la URL es la correcta y el
backend todavía no la sirve" y manda a esperar. Confundirlas cuesta una tarde buscando un
error que no está. El cuerpo trae la sección de este documento donde la ruta se especifica:

```json
{ "error": "no_implementado",
  "mensaje": "/v1/ordenes esta en el contrato (seccion 9) y todavia no hay servicio detras. No cambies el cliente: la URL es la correcta.",
  "seccion_contrato": "9" }
```

Desde 1.2 `/v1/ordenes` sí tiene servicio detrás; el ejemplo queda porque muestra la forma del
cuerpo, que es la misma para cualquier ruta declarada sin servicio.

Nunca se devuelve al cliente lo que el cliente acaba de enviar en un mensaje de error: el
manejador de validación del sistema anterior devolvía la contraseña recibida, y es uno de
los defectos ya documentados. El manejador de errores de validación de los tres servicios
reescribe la respuesta por omisión del framework, que incluye el valor recibido en `input`,
y deja solo `{error, mensaje, campo}`.

### 11.1 Demasiadas peticiones (nuevo en 1.11)

El gateway cuenta cada petición antes de reenviarla (ADR 0047). Si pasa un tope, responde así:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
```
```json
{ "error": "demasiadas_peticiones",
  "mensaje": "Hiciste demasiadas peticiones en poco tiempo. Vuelve a intentarlo en 42 segundos.",
  "reintentar_en_segundos": 42 }
```

`Retry-After` y `reintentar_en_segundos` son el mismo número de segundos, mínimo 1. El `mensaje`
ya trae la espera, en segundos o en minutos, y es el que se muestra. En `@tukit/contrato` el
cuerpo es `ErrorDemasiadasPeticiones`.

**Los topes.** Estos son los de por omisión, y cada uno se cambia por entorno:

| Nivel | Rutas | Ventana | Por token | Por IP |
|---|---|---|---|---|
| General | todo `/v1/*` | 60 s | 300 | 1.200 |
| Estricto | cada una de las de abajo, por separado | 600 s | 30 | 60 |

Las estrictas son estas, todas con `POST`:

- `/v1/listas/subir`;
- `/v1/trabajos`, `/v1/trabajos/{trabajo_id}/reintentar` y `/v1/trabajos/aplicar-canonico`;
- `/v1/admin/onboarding` y `/v1/admin/onboarding/{version_id}/preview`;
- `/v1/sesiones`, `/v1/cuenta` y `/v1/registro`;
- `/v1/catalogo/emparejar`.

Una estricta cuenta también en el general, y cada una tiene su propio cupo: los intentos de entrar
no gastan el de las subidas. Una ruta desconocida también cuenta.

**Lo que no cuenta:** `/v1/servicios`, `/v1/webhooks/*`, las preflight `OPTIONS` y lo que no es
`/v1/*` (`/salud`, `/health/*`).

**A quién se cuenta.** Cada petición cuenta dos claves por nivel, y tienen que pasar las dos: la
del token, si trae `Authorization: Bearer`, y la de la IP. Sin token solo cuenta la IP. El gateway
no valida el token para contar (eso sigue siendo de identidad), así que inventar uno en cada
petición no da cupo.

**Lo que el gateway espera de `X-Forwarded-For`:**

- Que lo escriba un proxy de confianza. Por omisión es la misma máquina (`127.0.0.1` y `::1`), que
  es donde corre la web; `TUKIT_PROXIES_CONFIANZA` acepta IP y redes separadas por comas.
- Que cada proxy agregue a la derecha la IP de quien le habló, como hace cualquier proxy. El
  gateway recorre la cabecera de derecha a izquierda, y la IP del cliente es la primera que no es
  de confianza. Si todas lo son, es la de más a la izquierda.
- Si la conexión no viene de un proxy de confianza, la cabecera se ignora y cuenta la IP de la
  conexión.
- El cliente de servidor de `@tukit/contrato` reenvía el `X-Forwarded-For` de la petición que
  recibió Next.js. Next.js la pone con la dirección del socket solo si no viene, así que en
  producción la web va detrás de un proxy que la escriba: si no, el navegador puede escribirla.

**Qué hace el cliente.**

- No reintenta solo.
- Los manejadores de Next.js pasan el `429` tal cual, con su `Retry-After`.
- La web y la consola muestran el `mensaje`. Si el `429` llega sin cuerpo (un proxy de por medio),
  `conEspera` arma `error`, `mensaje` y `reintentar_en_segundos` a partir de `Retry-After`.
- La pantalla de espera deja de sondear, dice que la solicitud sigue avanzando y ofrece un botón
  para volver a consultar.

El `429` de esta sección es el de la puerta al cliente. Los `429` del catálogo a inteligencia del
§8 son otra cosa: una dependencia interna que pide esperar.

---

## 12. La superficie de lectura (nueva en 1.1)

Hasta la 1.0 este contrato especificaba el pipeline y nada más, y esa omisión bloqueaba al
frontend en la primera pantalla: el catálogo existía en la base, con 100 conceptos y 347
productos con precio, y no lo exponía nadie. Sin esto no hay nada que pintar hasta que un
acudiente crea un trabajo, que es justo al revés de como se usa el producto.

Toda esta sección es de **solo lectura**. La única ruta que no es `GET` es
`POST /v1/catalogo/emparejar`, y tampoco escribe: es `POST` porque recibe una lista de
renglones en el cuerpo. Lo que escribe catálogo pasa por la cola de propuestas y por la
mano de una persona, porque una búsqueda por texto trae productos reales que no son lo
pedido (pedir `punzon punta metalica` devuelve correctores de punta fina).

### 12.1 Dónde vive todo esto

El backend son **cuatro procesos**. El frontend habla con uno solo.

| Proceso | Puerto | Qué atiende |
|---|---|---|
| **gateway** | **8010** | **La URL base. Es la única que el frontend debe conocer** |
| identidad | 8011 | `/v1/colegios`, `/v1/grados`, `/v1/contactos` |
| catalogo | 8012 | `/v1/catalogo/*`, `/v1/listas*` |
| inteligencia | 8013 | `/v1/trabajos*`, `/v1/admin/*` |
| comercio | 8014 | `/v1/ordenes*`, `/v1/pagos*`, `/v1/webhooks/wompi`, `/v1/comercio/*` |

```
TUKIT_API_URL=http://127.0.0.1:8010
```

> **Frontend:** `TUKIT_API_URL` es obligatoria y apunta al gateway (`:8010` en local). No
> hay valor por defecto: si falta, la app falla de entrada a proposito. `apps/web/.env.ejemplo`
> y `apps/admin/.env.ejemplo` ya la traen con el valor correcto.

El bloque empieza en 8010 y no en 8000 ni en 8080 por una razón aburrida y real: los dos
son el puerto por omisión de medio mundo (uvicorn, `http.server`, Django, cualquier
servidor de desarrollo de Java o Node) y en la máquina donde esto se escribió los dos
estaban tomados por proyectos ajenos. Los cuatro seguidos desde 8010 se recuerdan igual de
fácil y no chocan. Se cambian con `make arriba PUERTO_GATEWAY=9000`.

La puerta **rutea por prefijo declarado**, no con comodín. Una ruta que no esté en su mapa
devuelve `404 ruta_desconocida` con la lista de las que sí existen, en vez de reenviarla a
un servicio al azar. Las que este contrato define y todavía no tiene nadie detrás
devuelven `501 no_implementado` (§11). Antes de reenviar, la puerta cuenta la petición y puede
responder `429 demasiadas_peticiones` (§11.1), y en `/v1/admin/*` exige la sesión del equipo (§7).

`GET /v1/servicios` dice si los tres de atrás responden. Existe porque `GET /salud` en la
puerta contesta `ok` con los tres caídos, y esa es la clase de sonda que hace perder una
tarde.

```bash
curl http://127.0.0.1:8010/v1/servicios
```
```json
{"servicios": {
   "catalogo":     {"url": "http://127.0.0.1:8012", "arriba": true},
   "identidad":    {"url": "http://127.0.0.1:8011", "arriba": true},
   "inteligencia": {"url": "http://127.0.0.1:8013", "arriba": true}},
 "todos_arriba": true}
```

**CORS.** Los tres servicios y la puerta permiten `http://localhost:3000` y
`http://127.0.0.1:3000` sin configurar nada. Se sobreescribe con `TUKIT_CORS_ORIGENES`,
separando con comas. Los orígenes de desarrollo no se heredan en producción.

**Documentación viva.** Cada servicio publica su OpenAPI: `http://127.0.0.1:8012/docs`,
`:8013/docs`, `:8011/docs`. Este documento manda; el OpenAPI sirve para generar tipos.

### 12.2 Paginación, y el mismo sobre para todo

Toda colección responde igual, para que el componente de paginación se escriba una vez:

```jsonc
{ "total": 100, "pagina": 1, "por_pagina": 50, "conceptos": [ /* ... */ ] }
```

`pagina` empieza en 1. `por_pagina` va de 1 a **200**; pedir más es `400`, no una lista
recortada en silencio. `total` viene siempre, también cuando cabe en una página, porque
"cuántos hay" es la pregunta que decide si se pinta el paginador.

### 12.3 Catálogo

#### `GET /v1/catalogo/categorias`

Las 49 categorías con cuántos conceptos tiene cada una. Es lo que alimenta la navegación
lateral sin tener que traer los 100 conceptos para contarlos.

```json
{"total": 49, "categorias": [{"categoria": "Borradores", "conceptos": 1}]}
```

#### `GET /v1/catalogo/conceptos`

Un **concepto** es la necesidad abstracta que el colegio pide (`cuaderno`), no un producto
comercial. Es la capa que el sistema anterior no tenía y por la que la variabilidad
terminológica colombiana (`esfero` = `bolígrafo`) no tenía dónde vivir.

| Parámetro | Qué hace |
|---|---|
| `categoria` | Exacta, de `/v1/catalogo/categorias` |
| `tipo_item` | `util`, `texto`, `libro_libre`, `licencia_digital`, `no_comprar`, `diferido`, `uniforme`, `otro` |
| `busqueda` | Texto en el nombre canónico |
| `con_producto` | `true` solo los surtidos, `false` solo los huecos |
| `pagina`, `por_pagina` | §12.2 |

El orden por omisión es **por demanda medida** (`frecuencia_demanda`, de las 3.610 líneas
del corpus) y no alfabético: el orden de una pantalla de catálogo tiene que ser el de lo
que los colegios de verdad piden, y alfabético pondría `abaco` antes que `cuaderno`.

```bash
curl 'http://127.0.0.1:8010/v1/catalogo/conceptos?categoria=Borradores&por_pagina=1'
```
```json
{"total": 1, "pagina": 1, "por_pagina": 1,
 "conceptos": [{
   "codigo": "C005",
   "nombre": "borrador",
   "categoria": "Borradores",
   "tipo_item": "util",
   "sinonimos": ["borrador", "borrador nata", "borrador miga pan", "goma limpiatipo", "borrador nata grande"],
   "admite_personaje": false,
   "atributos_discriminantes": ["tipo"],
   "atributos_descriptivos": [],
   "frecuencia_demanda": 153,
   "productos": 3,
   "niveles_disponibles": 3}]}
```

**`atributos_discriminantes` y `atributos_descriptivos` son cosas distintas y se pintan
distinto.** El discriminante **filtra**: si el renglón dice `block oficio` y ningún block
declara `tamano: oficio`, no se ofrece otro. El descriptivo solo le cuenta al acudiente qué
está comprando y no descarta a nadie. De 155 pares concepto-atributo declarados
obligatorios, solo 81 los pide alguna lista; usarlos todos como restricción dura descartaba
candidatos válidos.

`niveles_disponibles` es cuántos de los tres niveles tiene el concepto. Un concepto con
menos de tres no puede ofrecer una opción distinta en cada kit, y eso el frontend lo puede
avisar antes de que el acudiente se extrañe.

#### `GET /v1/catalogo/conceptos/{codigo}`

El concepto con sus productos, ordenados `economico → confiable → premium` y no como los
devuelve la base (alfabético, que da `confiable` primero). `404 concepto_no_existe`.

#### `GET /v1/catalogo/productos`

| Parámetro | Qué hace |
|---|---|
| `concepto` | Código de concepto (`C005`) |
| `nivel` | `economico`, `confiable`, `premium`. Un valor inventado es `400`, no una lista vacía |
| `personaje` | Nombre exacto, sin distinguir mayúsculas |
| `con_personaje` | `true` solo los que tienen, `false` solo los que no |
| `busqueda` | Texto en el nombre o la marca |
| `con_precio` | `true` solo los que tienen precio vigente |

`nivel` y `personaje` son **ejes ortogonales**: un cuaderno de Spiderman también tiene nivel
de calidad de marca. La taxonomía anterior ponía `licencia` al lado de los tres niveles, y
bajo ella un cuaderno con personaje perdía su nivel y el optimizador se quedaba sin puntaje
con que compararlo.

#### `GET /v1/catalogo/productos/{sku}`

El producto con **todas** sus ofertas. Comparar precio entre tiendas es el núcleo de la
propuesta de valor y era literalmente inexpresable en el esquema anterior, donde `precio` y
`proveedor` eran columnas del producto.

```bash
curl http://127.0.0.1:8010/v1/catalogo/productos/TK-C005-ECO
```
```json
{"sku": "TK-C005-ECO",
 "nombre": "Set Borrador X3 Negro Eterna",
 "marca": "ETERNA",
 "nivel": "economico",
 "personaje": null,
 "imagen_url": "https://exitocol.vteximg.com.br/arquivos/ids/32010789/image-...jpg",
 "descripcion": null,
 "unidad_base": "unidad",
 "unidades_por_empaque": 3,
 "atributos": {},
 "quality_score": 0.4,
 "concepto": {"codigo": "C005", "nombre": "borrador"},
 "precio_desde": 4400,
 "tiendas": 1,
 "ofertas": [
   {"tienda": "exito", "tienda_nombre": "Éxito", "tipo_tienda": "minorista",
    "url": "https://www.exito.com/set-borrador-x3-negro-eterna-124157264/p",
    "disponible": true,
    "precio": 4400,
    "vigente_desde": "2026-09-02T05:00:00+00:00",
    "vigente_hasta": null,
    "fuente_precio": "scraper",
    "metodo_vinculacion": "ean",
    "confianza_vinculacion": 1.0}]}
```

Tres campos que conviene no malinterpretar:

- **`disponible` tiene tres valores, no dos.** `null` significa "la fuente no reporta
  existencias", que no es lo mismo que "no hay". El canal mayorista nunca las reporta, y
  pintar `null` como agotado escondería ofertas legítimas por una observación que nunca se
  hizo.
- **`precio` es `null` cuando no se conoce, y eso no es cero.** Una oferta sin precio no se
  puede comparar, pero tampoco se esconde: existe y el acudiente puede ir a mirarla. Van al
  final del orden.
- **`unidades_por_empaque` es de a cuántas viene**, y `unidad_base` en qué se cuentan. Con
  los dos, el frontend dice "una caja de 3" donde la base dice "3". Sin ellos sale el error
  del carrito que sumaba doce cajas cuando la lista pedía doce lápices.

Las ofertas vienen **ordenadas por precio**, las que lo tienen primero.

#### `GET /v1/catalogo/tiendas`

```json
{"total": 7, "tiendas": [{"slug": "exito", "nombre": "Éxito", "tipo": "minorista",
                          "url_base": "https://www.exito.com", "ofertas": 177}]}
```

#### `POST /v1/catalogo/emparejar`

Empareja renglones de texto libre contra el catálogo. **No escribe nada.** Es el mismo
código que usa la etapa de resolución del pipeline, expuesto por HTTP porque
`inteligencia` no puede leer la base de `catalogo` ni importar su paquete (invariantes 1 y
3 del manifiesto). El frontend lo puede usar para una vista previa mientras el acudiente
escribe.

```bash
curl -X POST http://127.0.0.1:8010/v1/catalogo/emparejar \
  -H 'Content-Type: application/json' \
  -d '{"renglones": ["2 cuadernos cuadriculados grandes", "block oficio"]}'
```
```jsonc
{"total": 2, "emparejamientos": [
  {"texto": "2 cuadernos cuadriculados grandes",
   "texto_corregido": "2 cuadernos cuadriculados grandes",
   "estado": "reconocido",
   "concepto_codigo": "C001", "concepto_nombre": "cuaderno",
   "parecido": 1.0,
   "atributos_impuestos": {"rayado": "cuadriculado", "materias": 1},
   "motivo": "",
   "opciones": [
     {"sku": "TK-C001-ECO-CARS", "nombre": "Cuaderno Cars Mediano Cuadriculado 100 hojas...",
      "nivel": "economico", "personaje": "cars", "marca": "CUADERNOS NORMA",
      "atributos": {"hojas": 100, "rayado": "cuadriculado", "materias": 1},
      "precio_cop": 15900, "cumple": true,
      "imagen_url": "https://...", "unidad_base": "unidad", "unidades_por_empaque": 1,
      "producto_id": "…uuid…"}]},

  {"texto": "block oficio",
   "estado": "abstencion",
   "concepto_codigo": "C003", "concepto_nombre": "block",
   "parecido": 0.867,
   "atributos_impuestos": {"tamano": "oficio"},
   "motivo": "El renglon pide block con tamano=oficio y ninguno de los 5 productos lo declara. No ofrezco otro.",
   "opciones": []}]}
```

`estado` es el vocabulario **del catálogo**, no el `EstadoResolucion` de §1.2:

| `estado` | Significado | Equivale a |
|---|---|---|
| `reconocido` | Hay concepto y hay productos que cumplen | `RESUELTO_AUTO` si `parecido ≥ τ`, si no `AMBIGUO` |
| `abstencion` | Se entendió el concepto y ningún producto declara el atributo exigido | `HUECO_CATALOGO` |
| `hueco_catalogo` | Se entendió el concepto y no hay ningún producto | `HUECO_CATALOGO` |
| `sin_match` | No se entendió qué pide | `SIN_MATCH` |

La diferencia entre `abstencion` y `sin_match` es la que permite decir *"no tengo block
oficio"* en vez de ofrecer origami con confianza. `abstencion` no es un fallo: es el
sistema negándose a inventar.

`texto_corregido` trae la corrección ortográfica contra el léxico del catálogo. Osito
imprime `SHSRPIE` y `TAOLLA` y el modelo las copia; sin este paso el catálogo diría que no
las reconoce teniendo marcador y toalla.

Como mucho **500 renglones** por petición (`422 demasiados_renglones`). Una lista de un
grado no tiene 500.

### 12.4 Colegios, sedes y grados (servicio `identidad`)

Los colegios **no** viven en `catalogo`: la tenencia es de `identidad` (ADR 0013), y
`lista_oficial.colegio_id` es una referencia lógica declarada en el manifiesto. Por eso
`/v1/listas` devuelve `colegio_id` y no el nombre: el nombre se resuelve contra
`/v1/colegios`, que el frontend puede cargar una vez.

```bash
curl http://127.0.0.1:8010/v1/colegios
```
```json
{"total": 17, "colegios": [{"colegio_id": "618e926b-77e1-55d7-8c26-4615830500f6",
                            "nombre": "Colegio 1.1", "sedes": 1}]}
```

- `GET /v1/colegios?busqueda=...`
- `GET /v1/colegios/{colegio_id}` → con sus sedes. `404 colegio_no_existe`
- `GET /v1/grados` → los 15 grados **en orden escolar**, de `Parvulos` a `Once`. Es una
  constante y no una consulta a propósito: derivarla de las listas cargadas haría que un
  colegio sin lista publicada desapareciera del desplegable.

**El directorio de Bogotá (1.8).** Los colegios que Tukit todavía no tiene salen del directorio
oficial, que vive en una sola copia en `@tukit/contrato/directorio-colegios.json`
(`[{dane, nombre, localidad, imageURL}]`, lo regenera `identidad` y conserva cada `imageURL`).
`apps/web` y `apps/admin` lo sirven estático en `/directorio-colegios.json` para buscar en el
navegador sin llamar a ningún servicio. El logo de un colegio es su `logo_url` de `identidad`; si
no tiene, el `imageURL` del directorio con su mismo DANE; si tampoco, sus iniciales
(`logoDeColegio`, ADR 0045).

#### `POST /v1/contactos`

Convierte un correo en un identificador, y es lo que hace cumplible la regla de §2: el
trabajo referencia al acudiente **por identificador y nunca copiando el correo**, para que
el derecho al olvido lo alcance en un solo sitio. Idempotente por correo.

```json
// 201
{"usuario_id": "…uuid…", "creado": true}
```

El frontend normalmente **no** necesita llamarlo: `POST /v1/trabajos` lo hace por dentro con
el bloque `contacto`. Está expuesto por si hace falta registrar antes. Leer un contacto
(`GET /v1/contactos/{usuario_id}`, correo y celular) es solo entre servicios: el gateway no lo
expone (1.12).

**Lo que NO hay en identidad, y la ausencia es deliberada:** ninguna ruta devuelve un
estudiante, un nombre de menor ni una matrícula. Esa superficie necesita autenticación y
control por clasificación de dato, y abrirla sin eso sería el defecto que documenta el
Anexo M. Hay una prueba que lee el OpenAPI publicado y falla si aparece alguna.

### 12.5 Listas oficiales

#### `GET /v1/listas`

| Parámetro | Qué hace |
|---|---|
| `colegio_id` | UUID, de `/v1/colegios` |
| `grado` | Tal como lo nombra el colegio (`Cuarto`) |
| `anio_lectivo` | Entero. Hoy todo es 2026 |

```bash
curl 'http://127.0.0.1:8010/v1/listas?grado=Cuarto&por_pagina=1'
```
```json
{"total": 13, "pagina": 1, "por_pagina": 1,
 "listas": [{"lista_id": "ebfb1673-3ddb-5333-bfe0-46084a97e335",
             "colegio_id": "17127bcf-9134-58a4-aae4-6a2bc6f7bf32",
             "sede_id": "c259b3dc-2d55-5674-9626-94c5c921783b",
             "grado": "Cuarto", "anio_lectivo": 2026,
             "version_id": "28b17ec3-f5c8-5971-a6cb-a3159b0c83e3", "version": 1,
             "publicada_en": "2026-09-22T17:08:30.226216+00:00",
             "revisada": false,
             "items": 55}]}
```

`revisada: false` **no es un defecto ni un aviso para el acudiente.** Es la puerta que
habilita salir a una tienda por lo que la lista pide y el catálogo no tiene; una vez
revisada se cierra y no se vuelve a abrir. Hoy las 175 están sin revisar. No lo pintes como
error.

#### `GET /v1/listas/{lista_id}`

Los renglones de la versión vigente, ya resueltos a concepto.

```jsonc
{"lista_id": "…", "colegio_id": "…", "sede_id": "…",
 "grado": "Cuarto", "anio_lectivo": 2026,
 "version_id": "…", "version": 1, "revisada": false,
 "total_items": 55,
 "items": [
   {"item_id": "…", "orden": 1,
    "texto_original": "cuaderno grande cuadriculado cosido de 100 hojas.",
    "cantidad": 7, "unidad": null,
    "tipo_item": "util",            // ya resuelto: el del renglón, o el de su concepto
    "tipo_item_declarado": null,    // lo que el renglón declaró, que puede ser null
    "modo_adquisicion": "mercado_abierto",
    "surtible": true,
    "instruccion_colegio": null, "url_externa": null,
    "atributos": {}, "requiere_revision": false,
    "concepto": {"codigo": "C001", "nombre": "cuaderno"}}]}
```

Dos campos para el mismo dato, y no sobra ninguno. **`tipo_item` viene resuelto**: si el
renglón no declara tipo, hereda el de su concepto. `tipo_item_declarado` dice si el valor
salió del renglón o del concepto, que es lo que necesita quien está curando. La regla
resuelta va en la respuesta para que el cliente no la reimplemente: `null` significa "lo
que diga el concepto", **no** `util`.

`concepto: null` y `requiere_revision: true` van juntos y son honestos: 891 de los 4.719
renglones del corpus (18,9 %) no los cubre todavía el vocabulario de 100 conceptos. Un
renglón sin concepto queda visible como no resuelto en vez de forzarse al más parecido.

`surtible: false` significa que Tukit no lo puede poner en el carrito (§1.1.1). Esos
renglones **siempre** traen `instruccion_colegio`: una línea que dice "esto no te lo
vendemos" sin decir dónde conseguirlo deja al acudiente peor que antes.


### 12.6 El ciclo completo, con lo que de verdad responde hoy

Lo que sigue son las tres llamadas que llevan de "no hay nada" a "los kits en pantalla",
ejecutadas contra el backend sembrado.

**(1) Crear el trabajo.** Entrada (a) de §2: el colegio ya publicó la lista.

```bash
curl -X POST http://127.0.0.1:8010/v1/trabajos \
  -H 'Content-Type: application/json' \
  -d '{"contacto": {"correo": "papa@ejemplo.com"},
       "hijos": [{"referencia": "hijo-1",
                  "colegio_id": "17127bcf-9134-58a4-aae4-6a2bc6f7bf32",
                  "grado": "Cuarto"}],
       "preferencias": {"presupuesto_por_hijo": 700000}}'
```
```json
{"trabajo_id": "d1aac882-7119-48ea-87a7-34bb9f64c21d",
 "estado": "encolado",
 "estimado_segundos": 180,
 "consultar_en": "/v1/trabajos/d1aac882-7119-48ea-87a7-34bb9f64c21d",
 "degradaciones": []}
```

**(2) Consultar hasta que cambie de estado.** Con el camino de hoy (lista oficial ya
cargada, sin llamar a ningún modelo) tarda **menos de un segundo**, no los 180 que estima.
El estimado se deja alto porque la entrada por archivo sí llamará a Gemini.

```bash
curl http://127.0.0.1:8010/v1/trabajos/d1aac882-7119-48ea-87a7-34bb9f64c21d
```
```jsonc
{"estado": "espera_revision",
 "origen": "colegio_grado",
 "hijos": [{"referencia": "hijo-1", "colegio_id": "…", "grado": "Cuarto", "anio_lectivo": null}],
 "etapas": [
   {"nombre": "percepcion",    "estado": "ok", "ms": 30,
    "detalle": {"listas": [{"hijo": "hijo-1", "grado": "Cuarto", "items": 55, "lista_id": "…"}],
                "sin_lista": []}},
   {"nombre": "normalizacion", "estado": "ok", "ms": 0,   "detalle": {"renglones": 55}},
   {"nombre": "resolucion",    "estado": "ok", "ms": 596, "detalle": {"emparejados": 36, "a_revision": 13}},
   {"nombre": "optimizacion",  "estado": "ok", "ms": 1,   "detalle": {"kits": 3, "recomendado": "Ahorrador"}}],
 "kits": [],
 "recomendado": null,
 "degradaciones": [],
 "error": null, "mensaje": null,
 "creado_en": "2026-09-22T17:14:02.118Z", "terminado_en": null, "nota_revision": null}
```

**`kits` va vacío hasta que el estado sea `publicado`. No es un error.** Es la razón de ser
de `espera_revision` y de `AD-06`: el acudiente nunca ve un kit sin revisar. La barra de
progreso se pinta con `etapas`, que existen desde el momento de crear (las cuatro en
`pendiente`) para que la espera tenga forma.

`detalle` por etapa es nuevo en 1.1 y es lo que permite decirle algo útil al acudiente:
`percepcion.detalle.sin_lista` nombra a los hijos para los que no había lista publicada, y
`resolucion.detalle.a_revision` dice cuántas líneas dudosas hay.

**(3) Aprobar, que hoy es una llamada manual.**

```bash
curl -X POST http://127.0.0.1:8010/v1/admin/trabajos/{id}/revision \
  -H 'Content-Type: application/json' -d '{"decision": "aprobar"}'
```

> **Atajo de desarrollo.** Con `TUKIT_AUTOPUBLICAR=1` el trabajo pasa directo a
> `publicado` y este paso no hace falta. El servicio lo anuncia a gritos al arrancar,
> porque una válvula silenciosa acaba puesta en producción. **Por omisión está apagada** y
> el contrato es el que manda: sin revisión humana no hay publicación.

Y ahí sí, los kits. La petición declaró un tope de $700.000, así que además del Ahorrador y
el Premium se arma `A tu Medida` y es el marcado (§6). Sin personaje no hay `Fan`:

```jsonc
{"estado": "publicado",
 "kits": [ /* ordenados por total, de menor a mayor */
   {"perfil": "Ahorrador",
    "total": 462395,
    "objetivos": {"costo": 462395, "fidelidad": 0.535, "disponibilidad": 0.628},
    "informativas": 5,
    "consolidaciones": [],
    "lineas": [ /* ver 12.7 */ ]},
   {"perfil": "A tu Medida", "total": 695000 /* ilustrativo: la mejor marca que no pasa del tope */,
    "objetivos": {…}, "lineas": […]},
   {"perfil": "Premium", "total": 864943, "objetivos": {…}, "lineas": […]}],
 "recomendado": {"perfil": "A tu Medida",
                 "razon": "Es la mejor marca que cabe en tu tope de $700.000.",
                 "dentro_de_presupuesto": true}}
```

`informativas` es nuevo en 1.1: cuántas líneas del kit se muestran y no se cobran. Es el
número del aviso que pide §5.1.1 (*"5 ítems los gestiona directamente el colegio"*), y
tenerlo ya contado ahorra recorrer las líneas.

### 12.7 Las dos formas de una línea de kit

**Con producto**, que es la normal:

```json
{"item_id": "e95f4365-c6df-454f-96fa-17b77d689e13",
 "hijo": "hijo-1", "orden": 1,
 "descripcion": "cuaderno grande cuadriculado cosido de 100 hojas.",
 "tipo": "util",
 "estado_resolucion": "RESUELTO_AUTO",
 "cantidad_pedida": 7,
 "unidad_base": "unidad",
 "unidades_por_empaque": 1,
 "unidades_a_comprar": 7,
 "informativa": false,
 "subtotal_linea": 111300,
 "mensaje": null,
 "producto_elegido": {"sku": "TK-C001-ECO-CARS",
                      "nombre": "Cuaderno Cars Mediano Cuadriculado 100 hojas Cosido CUADERNOS NORMA",
                      "marca": "CUADERNOS NORMA",
                      "nivel": "economico",
                      "personaje": "cars",
                      "imagen_url": "https://…",
                      "precio": 15900},
 "alternativas": []}
```

**Informativa**, que se muestra y no se cobra:

```json
{"item_id": "2ffc28d8-a3e2-4a72-9038-ee39a6d506c0",
 "hijo": "hijo-1", "orden": 12,
 "descripcion": "Plan lector virtual RAZ-PLUS",
 "tipo": "licencia_digital",
 "estado_resolucion": "RESUELTO_AUTO",
 "cantidad_pedida": 1,
 "unidades_a_comprar": 0,
 "informativa": true,
 "subtotal_linea": null,
 "instruccion_colegio": "El colegio indica que se adquiere por plataforma externa. Sigue el enlace o las instrucciones que el colegio publico en su lista.",
 "alternativas": []}
```

Cinco reglas sobre estas líneas que el frontend necesita tener claras:

1. **`subtotal_linea = precio × unidades_a_comprar`**, no `× cantidad_pedida`. Siete
   cuadernos sueltos a 15.900 son 111.300; doce lápices en caja de doce son **una** caja.
   `unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)`.
2. **El total del kit suma solo las líneas con `informativa: false`.** Prometer lo que no
   se puede entregar es el modo de falla más caro del negocio.
3. **`producto_elegido` no está cuando no hay producto.** Se omite la clave entera, no
   viene en `null`. Pasa con `SIN_MATCH`, con `HUECO_CATALOGO` y con toda línea informativa.
4. **`alternativas` viene siempre**, lista vacía si no hay. Hasta dos productos más del
   mismo concepto, en otros niveles, con `sku`, `nombre`, `nivel`, `precio_cop` e
   `imagen_url`.
5. **Una línea informativa puede tener `tipo: "util"`.** El tipo dice qué clase de cosa es
   y el modo de adquisición dice quién puede venderla; un útil que el colegio cerró a una
   plataforma es papel comprable que Tukit no surte. Decide `informativa`, no `tipo`.

Cuando la línea es un texto escolar de mercado abierto sale con
`estado_resolucion: "SIN_MATCH"` y `unidades_a_comprar: 0`: la resolución por ISBN contra
`edicion_libro` todavía no está conectada, y decirlo es mejor que ofrecer una edición al
azar. Se ve, no se cobra y se explica.

### 12.8 La cola de revisión (`apps/admin`)

| Endpoint | Qué hace |
|---|---|
| `GET /v1/admin/cola` | Trabajos en `espera_revision`, del más viejo al más nuevo, con `lineas_a_revisar` |
| `GET /v1/admin/trabajos/{id}` | El mismo lector del acudiente **con los kits forzados**: Admin tiene que ver lo que todavía no se publica |
| `POST /v1/admin/trabajos/{id}/lineas/{item_id}/validar` | `{"sku": "…", "motivo": "…", "actor": "…uuid…"}`. Deja la línea en `RESUELTO_AUTO` |
| `POST /v1/admin/trabajos/{id}/lineas/{item_id}/sin-coincidencia` | Deja la línea en **`HUECO_CATALOGO`**, no en `SIN_MATCH` |
| `POST /v1/admin/trabajos/{id}/revision` | `{"decision": "aprobar"\|"devolver", "nota": "…"}` |
| `POST /v1/admin/onboarding` | Solo staff (Bearer de operador o admin, desde 1.8). Multipart con `archivo`, `grado`, `anio_lectivo` y el colegio (abajo). Percibe el PDF o la imagen y lo importa a la cola |

**El colegio del onboarding (1.8)** se designa de una de tres formas, como en la subida del
acudiente:

- `colegio_id` de un colegio que Tukit ya tiene: igual que en 1.7.
- `colegio_dane` + `colegio_nombre`, elegido del directorio: el id se deriva del DANE y
  `colegio_datos` viaja al catálogo, completado con el directorio de `identidad`.
- Solo `colegio_nombre`, escrito a mano: el id se deriva del nombre normalizado.

En las dos últimas el colegio todavía no existe. La cola muestra su nombre y lo crea en
`identidad` al aprobar la lista. Sin ninguna de las tres, `422 colegio_requerido` con
`campo: "colegio"`, antes de leer el archivo. `apps/admin` reconduce un DANE que ya es de un
colegio existente a su `colegio_id`.

**La sesión (1.8).** Antes que nada, inteligencia valida el Bearer contra
`GET /v1/sesiones/actual`, con la misma semántica que `/v1/admin/acudientes`. Sin sesión
responde `401 sesion_invalida`, sin rol de operador o admin `403 acceso_denegado`, y si
Identidad no responde `503 identidad_no_disponible`, que falla cerrado. Así, quien no puede
subir no gasta una lectura del archivo. `apps/admin` reenvía como Bearer el token de la
cookie `tukit_sesion`, y sin cookie responde `401` sin llamar a inteligencia.

`sin-coincidencia` marca `HUECO_CATALOGO` a propósito. Si una persona miró la línea,
entendió qué pedía y concluyó que no lo tenemos, eso ya no es "no te entendí". Solo el
hueco se puede responder con una alternativa y solo el hueco alimenta la métrica de qué le
falta al catálogo.

`actor` es opcional hoy porque no hay autenticación; cuando la haya saldrá del token. Toda
decisión queda en `transicion_resolucion` con quién y cuándo (`AD-25`, `AD-26`).

`devolver` reabre el trabajo y lo vuelve a procesar **sin avisarle al acudiente**. Aprobar
un trabajo ya publicado es `409 estado_incompatible`: no es idempotente, es un segundo
aviso.

### 12.9 Lo que está declarado y todavía no funciona

Sin rodeos, porque el frontend necesita saber contra qué puede programar hoy.

| Qué | Estado | Qué pasa si lo llamas |
|---|---|---|
| §12.3, §12.4, §12.5 completas | **Funcionan** con datos reales | 100 conceptos, 347 productos con precio, 7 tiendas, 17 colegios, 175 listas, 4.719 renglones |
| `POST /v1/trabajos` entrada (a), colegio y grado | **Funciona** | Los kits del §5, con lista verificada sin volver a percibir. Pasan por revisión humana salvo la ruta rápida (`aplicar-canonico`) |
| Entrada (b), un archivo | **Funciona por otra ruta** | `POST /v1/trabajos` sigue siendo solo JSON (`multipart` es `400`). Los PDF entran por `POST /v1/listas/subir` (`multipart`), van a la cola de revisión de listas y al aprobarse arman el kit. Necesita `GEMINI_API_KEY`. Con el catálogo caído responde `202` y la lista llega a la cola cuando el catálogo vuelve (§8) |
| Optimizador | **NSGA-II** (pymoo), con enumeración exacta en listas chicas | Frente de 4 objetivos (costo, fidelidad, disponibilidad, personaje), sembrado con la heurística y la escalera de costo marginal. `Ahorrador` y `Premium` siempre; `Fan` y `A tu Medida` a pedido (ADR 0029, 0030) |
| Consolidación entre hermanos | **Funciona**, probada | Solo se dispara cuando a dos hijos les toca el mismo sku y el empaque alcanza |
| Notificación (§10) | **Funciona por correo** | El repartidor de `operacion` recibe `kits_publicados` y los eventos del pedido por su cola de RabbitMQ, o sin broker de las bandejas, y envía el correo (por consola si no hay SMTP), una vez por evento (§10). El wa-link se genera pero no se envía solo |
| Pago (§9) | **Funciona contra Wompi sandbox** | Widget, sincronización, webhook y cancelación. Sin llaves (`WOMPI_MODO=falso`) una pasarela simulada camina el mismo flujo. No hay modo de producción |
| Autenticación | **Funciona** (sesiones de `identidad`, `Authorization: Bearer`) | La exigen la cuenta del acudiente, "Mis solicitudes", cancelar, editar hijos y cambiar productos de un kit con dueño, y el admin. La superficie de lectura (catálogo, colegios, `GET /v1/trabajos/{id}`) sigue abierta |
| Cifrado de `pesos_usados` | **Puerto sí, cifrado no** | Pasa por el puerto `Cifrador`; sin `TUKIT_LLAVE_CIFRADO` el adaptador guarda en claro y lo dice al arrancar |
| Ejecución de fondo | **Funciona con el trabajador** | El trabajo queda `encolado` en `trabajo_pipeline` y el trabajador lo toma: con RabbitMQ por su aviso `trabajo_encolado`, sin broker sondeando la tabla (§10.1). Uno que quedó `procesando` por una caída lo retoma el trabajador a los 15 minutos |
