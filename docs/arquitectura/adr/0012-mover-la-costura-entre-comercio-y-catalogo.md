# ADR 0012 — Mover la costura entre Comercio y Catálogo, y unificar el maestro de productos

- **Estado:** aceptada (sesión de aprobación del OE2, 2026-09-21; ver `ACTA_APROBACION_OE2.md`)
- **Objetivos afectados:** OE2 principalmente, OE4 en la ejecución
- **Relación con el WBS:** afecta los paquetes de diseño de la fase 2 y el refactor de la fase 4
- **Supersede parcialmente:** ADR 0001 (consolidación de catorce servicios a seis)

## Contexto

El ADR 0001 consolidó catorce servicios documentados a seis más una pasarela. La
consolidación fue en la dirección correcta, pero se hizo agrupando por **afinidad temática**
—todo lo de comercio junto, todo lo de búsqueda junto— y no por un criterio de ingeniería.
Eso dejó dos costuras mal puestas, y la evidencia es verificable en el código.

**Primera evidencia: el catálogo está partido entre dos servicios sin un dueño claro.** La
tabla `productos_catalogo` está declarada como modelo en MS-Comercio y también en
MS-Busqueda. La relación entre las dos copias no es la de dos maestros simétricos, y la
precisión importa para planear la migración: **Comercio es el maestro, Búsqueda mantiene una
réplica con pérdida** alimentada por RabbitMQ sin confirmación, y el banco de pruebas de
extremo a extremo actúa como un segundo escritor no coordinado sobre esa réplica.

El problema es que **cada copia tiene algo que la otra no**. La de Comercio tiene el stock;
la de Búsqueda tiene los embeddings. Ninguna se puede descartar, y por eso el catálogo no ha
podido salir de Comercio: lo que lo retiene ahí es el inventario, no el catálogo.

Los precios, en cambio, **no están duplicados**, y conviene decirlo porque una versión previa
de este análisis lo afirmó por error. `precios_proveedor_producto` en Comercio tiene una
llave foránea a `proveedores` y un `precio_unitario` entero: es el **costo contractual** que
Tukit le paga a un mayorista. `precios_historico` en Búsqueda tiene `producto_id`, `precio` y
`fecha_actualizacion`: es la **serie de precio público observada** por el scraper. Son dos
conceptos distintos que además caen en lados opuestos de la asimetría de recuperación, y
unificarlos habría sido un error.

Aun así, la conclusión se sostiene: se paga el costo completo de cinco instancias de Postgres
separadas sin obtener propiedad clara del dato más consultado del sistema.

**Segunda evidencia, y es la determinante: el catálogo y los pedidos son los dos conjuntos
de datos más distintos del sistema, y hoy conviven en el mismo servicio y la misma base.**

| Dimensión | Catálogo | Pedidos y pagos |
| --- | --- | --- |
| Origen | Tiendas externas, scrapers | El usuario, irrepetible |
| Si se pierde | Se reconstruye en horas volviendo a scrapear | Se pierde dinero y se incumple la ley |
| Objetivo de punto de recuperación | Horas | **Cero** |
| Frescura aceptable | Días | Instantánea |
| Consistencia | Eventual por naturaleza | Fuerte, obligatoria |
| Patrón de escritura | Ráfagas masivas del scraper | Goteo transaccional |

Son opuestos en todas las dimensiones que determinan cómo se respalda, se ajusta y se
recupera un almacén de datos. Y comparten instancia. Una corrida de scraper con un error
puede tomar bloqueos en la misma base donde se confirman pagos.

Conviene descartar de entrada el argumento de volumen, porque no aplica y distrae. Con el
SOM proyectado de 1.500 kits el primer año y la demanda concentrada en las seis semanas de
temporada, el pico es del orden de 95 pedidos diarios, o sea 0,001 escrituras por segundo.
Aun multiplicando por diez, sobra capacidad por tres órdenes de magnitud sobre una
instancia modesta. **Ninguna frontera de este sistema se justifica por rendimiento**, y eso
es liberador: permite trazarlas por las razones correctas.

## Decisión

**El catálogo sale de MS-Comercio, se unifica con el de MS-Busqueda y pasa a ser un
servicio propio con un único maestro. MS-Comercio conserva solo lo que toca dinero.**

De esa decisión se derivan cuatro consecuencias de diseño:

1. **Un solo dueño, y el corte pasa por el stock.** `productos_catalogo`, `tiendas` y la
   serie de precio público observado viven exclusivamente en Catálogo. El costo contractual
   con proveedores se queda en Comercio, porque es dato interno con recuperación cero.
   La pieza que desbloquea todo es **extraer el inventario a su propia tabla en Comercio**:
   hoy el stock es una columna de `productos_catalogo` y se decrementa dentro de la
   transacción del pedido, y es exactamente eso lo que ata el catálogo al servicio
   transaccional. Sin esa extracción, ni el catálogo puede mudarse ni el modelo de reserva
   del ADR sobre pagos cierra.
   La migración promueve la copia de Búsqueda, que tiene los embeddings, y retira la de
   Comercio, que se queda solo con lo que era realmente suyo.
2. **Políticas de respaldo divergentes**, que es el propósito de fondo. Catálogo admite un
   objetivo de punto de recuperación de horas porque es reconstruible; Comercio exige cero
   y recuperación a un punto en el tiempo.
3. **Búsqueda se parte por exhaustividad contra precisión, no por etapa.** Catálogo responde
   "dado este texto, dame candidatos", porque los datos y el índice vectorial son suyos.
   Inteligencia responde "dados estos candidatos, decide", porque eso es lo que usa GPU y lo
   que cambia cada semana. La pregunta abierta A-04, que proponía partir Búsqueda en tres
   por etapa del pipeline, queda **cerrada por rechazo**: esa costura habría cortado por el
   lugar equivocado.
4. **Las listas oficiales se van con Catálogo**, no con Instituciones. Una lista oficial es
   la demanda y el catálogo es la oferta, y el trabajo documentado en `CATALOGO_LIMPIO.md`
   consistió precisamente en derivar los 99 conceptos a partir de las listas de los 17
   colegios. Separarlos obligaría a cruzar la red para hacer la operación central del
   negocio.

### Una duplicación que sí es correcta

Hay que distinguir dos casos que se parecen y no son lo mismo, porque la regla aplicada sin
matiz llevaría a un error.

Que `productos_catalogo` esté en dos servicios es un **defecto**: dos copias vivas que ambas
pretenden estar al día, sin dueño.

Que `lineas_pedido` guarde el nombre, el precio y la imagen **congelados en el momento de la
compra** no es duplicación, es un **requisito legal y contable**. La factura debe reflejar
lo que se vendió aunque el catálogo cambie mañana. Comercio copia de Catálogo al confirmar,
y desde ese instante la copia es inmutable y es la verdad.

La regla que separa los casos: **copiar un valor congelado en el tiempo es correcto;
mantener dos copias vivas que se pretenden actuales es el defecto.**

## Consecuencias

### Positivas

- Termina la ambigüedad de propiedad del dato más consultado del sistema.
- Cada almacén recibe la política de respaldo, retención y ajuste que su naturaleza exige.
- Un error del scraper deja de poder afectar la base donde se confirman pagos.
- Catálogo puede usar réplicas de lectura y pgvector sin imponérselo al almacén transaccional.
- MS-BFFAdmin pierde su razón de ser: la mayoría de sus agregaciones se vuelven consultas
  locales de Catálogo.
- La justificación de la arquitectura deja de apoyarse en un argumento de escalabilidad que
  los números no sostienen, y pasa a apoyarse en recuperabilidad y perfil de recurso, que sí.

### Negativas, y las asumimos

- **Consistencia eventual en el precio.** El precio que ve el usuario puede diferir del que
  se cobra. Se maneja congelando el precio en la reserva y revalidando contra Catálogo al
  confirmar, con un Caso si la diferencia supera un umbral. Es un problema conocido y con
  solución conocida.
- **Una migración de datos con dos maestros que reconciliar.** Hay que decidir columna por
  columna cuál de las dos definiciones sobrevive, y va a haber filas que solo existen en
  uno de los dos lados.
- **La frontera física no sustituye la disciplina.** Nada impide que alguien copie datos
  ajenos por HTTP y los cachee para siempre, que es la misma duplicación con otro disfraz.
  Por eso esta decisión viene acompañada de una prueba de arquitectura en integración
  continua que falla si un servicio declara un modelo de un dominio que no le pertenece, y
  esa prueba debe entrar **antes** de mover cualquier tabla.
- **Un salto de red en la normalización**, que antes era una consulta local. Es aceptable
  porque el pipeline pasa a ser asincrónico y la latencia deja de estar en un camino
  sincrónico con espera de 90 segundos.

## Alternativas consideradas

| Alternativa | Por qué no |
| --- | --- |
| Dejar los dos maestros y sincronizarlos | Sincronizar dos maestros es la forma más cara de no decidir quién manda. La deriva es cuestión de tiempo |
| Mover todo el catálogo a Comercio | Une lo reconstruible con lo irremplazable bajo una sola política de respaldo, que es el defecto que la decisión corrige |
| Mover todo el catálogo a Búsqueda tal como está | Deja el índice y el maestro juntos, pero le entrega el dato transaccional de proveedores a un servicio de cómputo con otro ritmo de cambio |
| Partir Búsqueda en tres por etapa, según A-04 | Agrega dos saltos de red dentro de una operación ya lenta y coordinación distribuida para lo que hoy son llamadas a función |
| Colapsar todo en un monolito modular | El cálculo de carga lo permitiría, pero borra la frontera de cumplimiento sobre datos de menores y obliga a una sola política de recuperación para datos con objetivos opuestos |

## Evidencia

- `productos_catalogo` declarada como modelo en MS-Comercio y en MS-Busqueda, verificado
  por inspección de `MS-*/app/models/`, con Comercio como maestro y Búsqueda como réplica
  con pérdida alimentada por RabbitMQ sin confirmación.
- `PrecioProveedorProducto` en Comercio, con llave foránea a `proveedores` y
  `precio_unitario` entero, frente a `PrecioHistorico` en Búsqueda, con `producto_id`,
  `precio` y `fecha_actualizacion`: conceptos distintos, no copias.
- El decremento de stock ocurre bajo `SELECT ... FOR UPDATE` sobre el catálogo dentro de la
  transacción del pedido, en `MS-Comercio/app/routers/pedidos.py`, que es el acoplamiento
  que obliga a extraer el inventario antes de mover nada.
- Cinco instancias de Postgres verificadas, una por servicio con base propia.
- Proyección de 1.500 kits del dossier y el cálculo de carga derivado, en la sección 2 de
  `REDISENO_ARQUITECTURA.md`.
- Derivación de 99 conceptos a partir de las listas de 17 colegios, en `CATALOGO_LIMPIO.md`
  y `Conceptos.csv`.
