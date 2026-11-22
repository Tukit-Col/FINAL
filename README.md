# Tukit

Armado asistido de kits escolares. Un acudiente sube la lista de útiles que le dio el
colegio, el sistema la interpreta, la normaliza contra un catálogo canónico y le arma kits
optimizados que balancean precio, calidad y preferencias.

Este repositorio reemplaza a los dieciséis anteriores. No es una reescritura: el trabajo
bueno y probado se porta, y lo que cambia es el modelo de dominio, que era donde estaban
los defectos.

Toda la documentación (contrato de la API, ADR, requisitos, diseños, informes y el documento
de los algoritmos) está en [`docs/`](docs/README.md), clasificada y con su índice.

```bash
make preparar     # entorno y dependencias
make fronteras    # verifica las fronteras de arquitectura
make verificar    # todo lo que corre la integración continua
```

## Requisitos

- **Python 3.12+** y [`uv`](https://github.com/astral-sh/uv) (gestiona el venv y las
  dependencias del workspace).
- **Node 20+** y **npm** (los frontends son un workspace de npm, no pnpm).
- **Postgres 16 con `pgvector`** — o **Docker**, que lo levanta por ti con `make bd-arriba`
  (imagen `pgvector/pgvector:pg16`). Sin Docker necesitas Postgres 16 local y `make bd-crear`.
- **RabbitMQ 3.13 o 4.x**, opcional. Sin él, los procesos de fondo sondean las bases. Con
  Docker, `make bd-arriba` lo levanta junto a Postgres.
- **Redis 7 u 8**, opcional. Sin él no hay caché, y el límite de tasa cuenta en la memoria de la
  puerta. Con Docker, `make infra-arriba` lo levanta.

## Levantar el backend completo

```bash
make preparar     # entorno y dependencias
make bd-arriba    # Postgres con las 5 bases y RabbitMQ   (con Docker)
make bd-crear     # las 5 bases + extensiones  (sin Docker, Postgres 16 local)
make backend      # migra, siembra y levanta los cuatro procesos HTTP
make humo         # golpea la API y falla si algún endpoint viene vacío
```

`make backend` encadena `bd-migrar`, `bd-sembrar` y `arriba`, y las tres son idempotentes:
volver a correrlo sobre una base ya sembrada no duplica nada.

`bd-crear` existe porque el compose crea las bases con su script de init y un Postgres
instalado en la máquina nunca pasa por ahí, así que el arranque desde cero se quedaba a
medias en el primer paso. Con Docker no hace falta.

El frontend apunta a **`http://127.0.0.1:8010`** y no necesita saber nada más:

```
TUKIT_API_URL=http://127.0.0.1:8010
```

| Proceso | Puerto | Qué atiende |
|---|---|---|
| **gateway** | **8010** | La única URL que el frontend conoce. Rutea por prefijo declarado y limita la tasa |
| identidad | 8011 | `/v1/colegios`, `/v1/grados`, `/v1/contactos` |
| catalogo | 8012 | `/v1/catalogo/*`, `/v1/listas*` |
| inteligencia | 8013 | `/v1/trabajos*`, `/v1/admin/*` |

`make estado` pregunta a la puerta cuáles de los tres responden; `make abajo` los detiene.

`make arriba` lanza también los procesos de fondo: el trabajador, los sondeadores, el repartidor
y el barredor. Antes pregunta si RabbitMQ responde en `RABBITMQ_URL`, que por omisión es
`amqp://guest:guest@localhost:5672/`. Si responde, los lanza con el broker y suma los tres
publicadores de bandeja. Si no responde, o si `RABBITMQ_URL` está vacía, sondean las bases como
antes (ADR 0046).

Lo mismo hace con Redis en `REDIS_URL`, que por omisión es `redis://localhost:6379/0`. Si
responde, catálogo, inteligencia y la puerta arrancan con él: una lista ya leída no se vuelve a
leer, el vector de un renglón no se vuelve a pedir y el contador del límite de tasa es compartido.
Si no responde, o con `make arriba REDIS_URL=`, arrancan sin caché y la puerta cuenta en su memoria
(ADR 0047). `make prueba-redis` corre las pruebas contra Redis, en la base 15.
Cada servicio publica su OpenAPI en `/docs`. La fuente de verdad, de todas formas, es
[el contrato](CONTRATO_API.md), que desde la versión 1.1 documenta la
superficie de lectura completa con ejemplos de respuestas reales.

`make humo` es la función de aptitud de la capa HTTP. No comprueba que responda `200`: un
endpoint que devuelve `{"total": 0}` responde `200` perfectamente, y una base migrada y sin
sembrar se ve igual de sana que una sembrada hasta que alguien abre la pantalla. Cada
comprobación exige contenido, y la última recorre el ciclo entero: crear un trabajo,
esperarlo, aprobarlo y verificar que salgan tres kits con uno recomendado.

---

## Levantar el frontend

Dos apps de Next.js 16 en el mismo workspace de npm: la pública (`web`, acudiente) y el
back-office (`admin`, operación). Ambas hablan solo con el gateway.

```bash
npm install        # instala los dos workspaces desde la raíz
npm run dev:web    # app pública    → http://127.0.0.1:3000
npm run dev:admin  # back-office    → http://127.0.0.1:3001
```

Cada app lee su origen de datos de un `.env.local` propio. Siempre habla con el backend
real a traves del gateway: solo hay que decirle donde esta. `TUKIT_API_URL` es obligatoria
— si falta, la app falla de entrada a proposito (no hay default silencioso).

```bash
# apps/web/.env.local  y  apps/admin/.env.local
TUKIT_API_URL=http://127.0.0.1:8010
```

### Dirección en el checkout

La dirección de entrega se busca en OpenStreetMap y se confirma moviendo un pin en el mapa
(ADR 0049). No necesita llave ni configuración.

El `.env` del backend se copia de [`.env.ejemplo`](.env.ejemplo). Todo tiene defaults de
desarrollo, así que puedes arrancar sin tocarlo. Dos variables son opcionales pero mejoran
la demo:

- `GEMINI_API_KEY` — habilita la búsqueda semántica del catálogo. Sin ella el emparejamiento
  cae a solo léxico.
- `WOMPI_*` — la pasarela de pago. `WOMPI_MODO=falso` (por defecto) usa una pasarela simulada;
  no necesitas llaves reales para caminar el checkout.

## Compartir la curaduría de listas

Curar una lista (decidir a qué concepto corresponde cada renglón y cerrarla en la cola)
queda en la base local, que es de una sola máquina. Para que llegue a los demás viaja por
git como CSV:

```bash
make curaduria-exportar   # base -> datos/  (luego git add datos/ && git commit)
make curaduria-importar   # datos/ -> base  (después de un git pull)
```

| Archivo | Qué lleva |
|---|---|
| `datos/curaduria/listas_revisadas.csv` | Un renglón por ítem de la última versión revisada de cada lista, con el concepto por código |
| `datos/catalogo/conceptos.csv` | Los conceptos creados curando se agregan; los existentes se actualizan |
| `datos/curaduria/colegios.csv`, `sedes.csv` | Los colegios que esas listas nombran, para que la lista no quede huérfana |
| `datos/catalogo/productos_canonicos.csv`, `ofertas_tienda.csv`, `precios_oferta.csv`, `productos_procedencia.csv` | Los productos aprobados en la cola, los reclasificados de concepto y sus **atributos corregidos a mano** (lo que hace que el filtro de atributos encuentre producto) |

En Windows, `.\tukit.ps1 exportar` e `.\tukit.ps1 importar` hacen lo mismo.

Los vectores de búsqueda semántica no viajan (no se versionan): después de importar,
`make bd-enriquecer` los calcula para los productos nuevos. Gasta cupo de Gemini Embedding
(una petición por producto); sin correrlo el emparejamiento funciona igual, solo por palabras.

`curaduria-importar` corre `bd-cargar` primero (una lista no entra sin sus conceptos) y es
idempotente: una lista que ya dice lo mismo no se toca, y una que cambió crea una versión
nueva en vez de sobreescribir. No viajan el PDF original ni el contacto del colegio.

Exporta **antes** de hacer `git pull`: `bd-cargar` actualiza los conceptos desde el CSV, y
un sinónimo agregado en la base y no exportado se perdería. Los códigos de concepto nuevos
(`C100`, `C101`…) se numeran en cada base, así que dos personas creando conceptos a la vez
chocarían; mientras sea una sola persona la que cura, no pasa.

Los criterios para curar (cuándo crear un concepto, qué tipo darle, dónde va un sinónimo) y
el registro de lo curado están en [`docs/registros/CURADURIA_CATALOGO.md`](docs/registros/CURADURIA_CATALOGO.md).

## Usuarios de prueba

Las seis cuentas demo entran con la misma clave: **`demo1234`**. No es un secreto, es un
banco de pruebas (así lo dice el propio sembrador). Las siembra `make bd-sembrar`; para
re-sembrar con otra clave: `python -m tukit_identidad.sembrar_acceso --clave otra`.

| Correo | Rol | Dónde aterriza | Ruta |
|---|---|---|---|
| `mama@ejemplo.com` | acudiente | web · :3000 | `/dashboard` |
| `papa@ejemplo.com` | acudiente | web · :3000 | `/dashboard` |
| `operador@tukit.co` | operador | admin · :3001 | `/` (cola de revisión) |
| `admin@tukit.co` | admin | admin · :3001 | `/` (cola de revisión) |
| `rectoria@colegio.edu.co` | colegio_admin | portal de colegio* | `/portal` |
| `docente@colegio.edu.co` | colegio_docente | portal de colegio* | `/portal` |

\* El portal de colegio está enrutado pero aún no construido; hoy solo existen la app web
(:3000) y el back-office (:3001).

El enrutado por rol vive en `libs/ts/tukit-contrato/src/origen.ts::destinoDe`: `admin` y
`operador` van al back-office, `colegio_*` al portal de colegio, y el resto al dashboard del
acudiente.

## Pagos de prueba con Wompi

una pantalla "Procesando pago de prueba" que aprueba sola (con `?resultado=rechazado` se fuerza el rechazo); no sale a la red. Con `WOMPI_MODO=sandbox` lleva al
"Aprobar pago" y "Rechazar pago"; no sale a la red. Con `WOMPI_MODO=sandbox` lleva al
checkout real de Wompi (`https://checkout.wompi.co/p/`), pero en modo de **pruebas**: no se
mueve dinero. Es un candado a propósito: Comercio se niega a arrancar si alguna llave no es de
prueba, y no existe un modo de producción en esta rama.

Las llaves salen de [comercios.wompi.co](https://comercios.wompi.co) → *Desarrolladores*, con el
interruptor en modo de pruebas. Van en el `.env` de la raíz (copiado de `.env.ejemplo`):

| Variable | Dónde está en el panel | Empieza por |
|---|---|---|
| `WOMPI_LLAVE_PUBLICA` | Llave pública | `pub_test_` |
| `WOMPI_LLAVE_PRIVADA` | Llave privada | `prv_test_` |
| `WOMPI_SECRETO_EVENTOS` | Secretos → Eventos | `test_events_` |
| `WOMPI_SECRETO_INTEGRIDAD` | Secretos → Integridad | `test_integrity_` |

Si no tienes `.env`, cópialo de `.env.ejemplo`. Con `WOMPI_MODO=sandbox` en el `.env`, reinicia
el stack con esas variables cargadas: en Linux/macOS expórtalas en la shell antes de levantarlo
(`set -a; . ./.env; set +a; make arriba`); en Windows, el ayudante local `tukit.ps1` (si lo
usas) carga el `.env` solo.

Elige un kit y paga, desde `localhost` como siempre. El pago se abre con el
[widget de Wompi](https://docs.wompi.co/docs/colombia/widget-checkout-web/), un modal encima del
kit: con tarjeta y Nequi el acudiente no sale de Tukit. El backend firma los datos del widget (el
secreto de integridad no llega al navegador). PSE sí se lleva la pestaña al banco y vuelve por
el `redirectUrl` a `/pago/resultado?id=<transacción>`. Esa página le pregunta a Wompi, de
servidor a servidor, cómo quedó el pago (`POST /v1/pagos/{id}/sincronizar`); lo que dice el
navegador es solo informativo.

Un detalle que cuesta una tarde si no se sabe: el checkout de Wompi responde 403 cuando una URL
suya lleva un retorno a `localhost` o a una IP privada. Por eso el widget se abre con
`bootstrapTransport: "postmessage"`, que le pasa la configuración por mensaje y no por la URL
de su iframe. Si algún día el modal se queda girando sin fin, es esto. El porqué completo está
en el [ADR 0033](docs/arquitectura/adr/0033-pago-con-widget-de-wompi.md).

En "Mis pedidos" del panel, un pedido pendiente se paga o se cancela sin rearmar el kit. Se
puede pagar durante 24 horas; después hay que rearmarlo para ver el precio de hoy. Cancelar le
pregunta antes a Wompi si hay un pago en curso, porque cancelar un PSE que el banco todavía está
aprobando cobraría sin entregar ([ADR 0035](docs/arquitectura/adr/0035-cancelar-solo-con-wompi-consultado.md)).

En modo falso los montos simulados viven en la memoria de Comercio: si lo reinicias entre
"Pagar" y la aprobación, obtendrás `transaccion_no_existe`; empieza de nuevo desde el kit.

Datos de prueba de Wompi (según [docs.wompi.co](https://docs.wompi.co/docs/colombia/datos-de-prueba-en-sandbox/)):

| Medio | Dato | Resultado |
|---|---|---|
| Tarjeta | `4242 4242 4242 4242`, cualquier CVC de 3 dígitos y fecha futura | Aprobado |
| Tarjeta | `4111 1111 1111 1111`, cualquier CVC de 3 dígitos y fecha futura | Rechazado |
| Tarjeta | cualquier otro número | Error |
| Nequi | `3991111111` | Aprobado |
| Nequi | `3992222222` | Rechazado |
| Nequi | cualquier otro número | Error |
| PSE | Banco "Banco que aprueba" (código `1` por API) | Aprobado |
| PSE | Banco "Banco que rechaza" (código `2` por API) | Rechazado |

**Webhook (opcional).** El webhook `POST /v1/webhooks/wompi` también confirma el pago, pero
Wompi tiene que poder alcanzarlo. Para probarlo desde tu máquina expón el gateway con un túnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8010
```

y pega `https://<túnel>/v1/webhooks/wompi` como URL de eventos en el panel de Wompi (modo de
pruebas). Sin túnel no pasa nada malo: la página de resultado confirma igual.

---

## Cómo está organizado, y por qué así

Un monorepo con **siete desplegables independientes previstos (seis con código hoy) y cinco bases de datos separadas**.

```
servicios/     identidad  catalogo  inteligencia  comercio  operacion  gateway
               (ingesta: declarado en el manifiesto, todavía sin código)
apps/          web  admin
               (colegio: previsto, todavía sin construir)
libs/          py/tukit_comun   ts/tukit-contrato
               (go/tukitgo: previsto, todavía sin código)
arquitectura/  manifiesto.toml + las funciones de aptitud
datos/         corpus, conceptos, conjuntos de referencia
infra/         compose de Postgres 16 + pgvector (cinco bases), despliegue
```

Un repositorio no es un desplegable. Que el código viva junto y se despliegue por separado
son dos decisiones distintas, y aquí se toman distinto a propósito: el
ADR 0014 (*monorepo con despliegue independiente*, en el repositorio externo `Arquitectura/`) lo argumenta
con la norma 42010 y el modelo 4+1, que separan la vista de desarrollo de la vista física.

La razón concreta de haber juntado el código: mover una función de redacción a la librería
compartida, en la estructura anterior, exigió editar **siete archivos `pyproject.toml`** y
publicar un tag antes de que algo instalara. Aquí es un commit.

### Dónde vive cada cosa dentro de un servicio

Los módulos grandes se parten por responsabilidad. Cada uno es un paquete que reexporta su API,
así que `from tukit_inteligencia import trabajos, optimizador` sigue funcionando.

| Paquete o módulo | Responsabilidad |
|---|---|
| `inteligencia/optimizador/` | `tipos` (entidades y constantes), `candidatos` (filtros duros y heurística por perfil), `preferencias`, `frente` (enumeración exacta y NSGA-II), `lineas` (consolidación y personaje), `recomendacion` (MAUT), `armado` (`armar_los_tres`, punto de entrada) |
| `inteligencia/trabajos/` | `base` (tablas, configuración, excepciones), `pipeline` (creación y etapas), `lectura`, `solicitudes`, `revision`, `versiones`, `cambios`, más `formas` y `anclas` como ayudantes compartidos |
| `catalogo/extraccion.py` | Reglas puras: empaque, atributos y personaje desde el nombre o la ficha. `enriquecer.py` solo orquesta el lote |
| `catalogo/clasificacion.py` | Reglas puras: de un renglón de lista a un concepto. `descubrir.py` conserva la revisión y el alta |
| `tukit_comun/autenticacion.py` | Lectura del encabezado `Authorization`, igual para todos los servicios |

Dentro de cada paquete las dependencias van en un solo sentido y no hay ciclos: en `optimizador`,
`tipos` no importa de nadie y `armado` importa de los demás. La ruta de consulta del catálogo
(`consulta.py`) lee de `extraccion` y `clasificacion`, no de los CLI `enriquecer` y `descubrir`.

---

## Los cinco invariantes

No son recomendaciones. Los cuatro primeros los verifica `arquitectura/test_fronteras.py`
en cada integración, y rompen la construcción.

1. **Ningún servicio importa código de otro servicio.** Solo de `libs/`.
2. **Ningún servicio declara una tabla de un dominio ajeno.**
3. **Ningún servicio se conecta a la base de otro.** Cinco bases, un dueño cada una.
4. **Toda referencia a otro dominio está declarada** en `arquitectura/manifiesto.toml`.
   Postgres no puede imponerla, así que al menos tiene que estar escrita.
5. **Cada servicio construye su imagen y se despliega por separado.**

### Por qué existen estas pruebas

El defecto más grave del sistema anterior fue que `productos_catalogo` estaba declarada
como maestro en dos servicios a la vez. No pasó por falta de criterio: pasó porque nada
verificaba el criterio. La disciplina humana ya falló una vez en este proyecto.

En términos de arquitectura evolutiva, son **funciones de aptitud**: pruebas automáticas y
continuas sobre una característica arquitectónica. Son la diferencia entre *afirmar* que
hay contextos delimitados y *demostrarlo*.

Y están demostradas: `arquitectura/test_fronteras_se_activan.py` le da de comer una
infracción de cada tipo y comprueba que la detecte. Una función de aptitud que nunca ha
fallado no está probada, podría estar midiendo nada.

---

## Por qué estos siete servicios

La separación **no** se justifica por escalabilidad. Se midió la carga proyectada y sobra
capacidad por unos tres órdenes de magnitud; sostener ese argumento frente a un jurado no
resistiría la primera pregunta. Las tres razones que sí se sostienen:

| Criterio | Qué separa |
|---|---|
| **Recuperabilidad asimétrica** | `inteligencia` es enteramente reconstruible y tolera perder horas; `comercio` no puede perder un byte. Objetivos de punto de recuperación incompatibles en el mismo almacén. (Nota: `catalogo` **también** pasó a RPO cero al entrar el módulo editorial —ADR 0017—, así que entre `catalogo` y `comercio` la frontera hoy la sostiene el perfil de recurso, no esta asimetría.) |
| **Frontera de cumplimiento** | Los datos de menores de edad (Ley 1581 de 2012) viven aislados en `identidad`, con proceso y base propios. |
| **Perfil de recurso** | `inteligencia` es intensiva en CPU y modelos; `comercio` necesita transaccionalidad y disponibilidad. Juntas obligan a dimensionar todo por la más exigente. |

---

## Por qué casi todo es Python

Se midió antes de decidir. El resultado está en
`PERFILADO_PIPELINE.md` (repositorio externo `Arquitectura/`) y contradice la intuición
de partida en algo importante: la latencia del pipeline **sí** era CPU de Python, un 96,3 %,
pero el 95,3 % del total lo producía **una sola línea** que reconstruía un grafo de
NetworkX completo en cada ítem. Construirlo cuesta 1.673 ms; consultarlo, 0,137 ms.

Cacheándolo, una lista de veinte ítems baja de 35,1 s a 1,7 s. Reescribir en Go lo que
queda daría, por la ley de Amdahl, entre 20,0 % y 21,7 %, y casi todo sería reimplementar
pymoo, que no tiene equivalente en Go: con él corre el NSGA-II del optimizador y se
produjeron los resultados de hipervolumen de la tesis.

Por eso **seis de siete componentes son Python**. El único con argumento real para Go es
`ingesta`, y aun ahí sus cuellos de hoy son estructurales y no de lenguaje: los vendedores
se recorren en serie, hay 1,5 s de espera deliberada por producto y no hay pool de
conexiones. Eso se arregla en Python primero, y Go se evalúa después con datos.

La estructura ya es políglota (`libs/go/`, el manifiesto declara el lenguaje de cada
servicio y una prueba lo verifica), así que mover un componente a Go es agregarlo, no
reestructurar.

---

## Estado

Andamiaje con base de datos viva. Existen el manifiesto de las 69 tablas, las funciones de
aptitud con sus pruebas, el ejecutor de tareas y la integración continua con ejecución
selectiva por ruta. **Dos de los siete servicios están portados** (identidad con 16 tablas y
catálogo con 18: modelos SQLAlchemy y pruebas de dominio); los otros cinco se llenan
portando desde los repositorios anteriores, en el orden del
plan `PLAN_TUKIT_V2.md` (repositorio externo `Arquitectura/`).

La otra mitad de la superficie compartida es el [contrato de la API](CONTRATO_API.md).
El manifiesto fija las fronteras de *datos*; el contrato fija las de *conversación*. Son los
dos únicos archivos que varios frentes tocan a la vez, así que se cierran antes de repartir
trabajo.

### La base de datos, de modelo a motor

Los modelos ya no viven solo en las pruebas. `libs/py/tukit_comun` tiene la capa de acceso
compartida —motor y sesiones async, configuración por entorno— y `infra/` levanta un
Postgres 16 con pgvector que hospeda las cinco bases. El nombre de la base nunca se escribe
en el código de un servicio: cada uno se lo pide a la librería pasando su nombre, y la
librería lo deriva o lo lee del entorno, que es lo que mantiene verde la regla 3.

```bash
make bd-arriba     # Postgres con las 5 bases + pgvector y pg_trgm
make bd-migrar     # lleva cada base a la ultima revision de SU servicio, + indices
make bd-deriva     # falla si el esquema migrado y los modelos no dicen lo mismo
make bd-verificar  # comprueba contra el motor que extensiones e indices existan
make bd-abajo      # detiene, conservando datos   (bd-limpiar los borra)

make bd-revision m='agrega tal cosa' s=catalogo   # genera una revision nueva
make bd-esquema    # create_all, atajo de desarrollo: ver mas abajo
```

Las metas de base de datos **no exigen Docker**. Si el contenedor de `infra/` está
levantado lo usan, porque es el entorno que reproduce a producción; si no, se caen a un
Postgres instalado en la máquina. Cada meta imprime cuál de los dos usó. La distinción no
es cosmética: el SQL de índices se escribió a ciegas durante días porque la única vía era
un Docker que no arrancaba, habiendo al lado un Postgres 16 que servía igual.

`bd-verificar` comprueba las extensiones en las cinco bases y los dos índices por nombre,
porque un índice que no se creó no da error en ninguna consulta: solo la vuelve un
recorrido secuencial, en silencio.

#### Migraciones: una historia por servicio

Cada servicio tiene su `alembic.ini` y su carpeta `migraciones/`, porque cada uno tiene su
propia base y se despliega solo; una historia compartida obligaría a desplegarlos juntos.
Lo que se comparte es el arranque, en `tukit_comun.migraciones`, para que el `env.py` de
los cinco no sea el mismo archivo copiado cinco veces.

`bd-esquema` (`create_all`) sigue existiendo como atajo para levantar un entorno de cero en
un comando, pero **la fuente de verdad del esquema son las migraciones**. Los dos caminos
no son equivalentes, y ahí está lo que hay que saber: `create_all` resuelve solo los ciclos
de llaves foráneas, creando las tablas primero y las llaves después con un `ALTER`. Alembic
no. Por eso `make bd-deriva` no es opcional.

Esa meta compara el esquema que dejan las migraciones contra el que declaran los modelos, y
es la única forma de ver una clase de fallo que no aparece de ninguna otra: el modelo
declara una restricción, la migración no la crea, y la suite sigue verde. Las dos primeras
que encontró, el día que se escribió:

- `grupo_variante` y `producto_canonico` se apuntan entre sí. La migración producía la tabla
  **sin esa llave foránea**: un hueco de integridad referencial, en silencio. Las llaves
  marcadas `use_alter` las omite el autogenerador y hay que agregar el `op.create_foreign_key`
  a mano.
- `concepto_ruta_categoria` declaraba una restricción única sobre las mismas tres columnas
  de su llave primaria. Postgres las funde al crear la tabla y la superviviente se queda con
  el nombre de la otra, así que el esquema real dejaba de parecerse al declarado.

Las dos quedaron cubiertas además por pruebas que no necesitan motor, en
`TestElEsquemaSePuedeMigrar`: una revisa que exista un orden válido de creación, la otra que
ninguna restricción única repita una llave primaria.

Encadena `bd-indices` al final porque `create_all` no puede generar los índices de la
búsqueda híbrida: HNSW sobre el embedding y GIN de trigramas sobre el nombre son sintaxis
exclusiva de Postgres, y declararlos en el modelo rompería el mismo modelo contra SQLite,
que es donde corren las pruebas de dominio. Viven en `infra/postgres/indices/`, un archivo
por servicio dueño de su base.

Las extensiones se habilitan en dos sitios a propósito: el script de init las crea en
volúmenes nuevos, y `tukit_comun.bd` las vuelve a pedir con `IF NOT EXISTS` antes de crear
tablas. El init corre **una sola vez**, cuando el volumen está vacío, así que quien levantó
el motor antes de que se agregara `pg_trgm` no lo tendría nunca, y el síntoma no aparece al
arrancar sino mucho después, como un operador inexistente en una consulta que debería
funcionar.

### Deuda conocida, anotada para que no se pierda

- **Las migraciones cubren tres de los cinco servicios.** Identidad, Catálogo e
  Inteligencia tienen su revisión aplicada y sin deriva. Comercio y Operación todavía no
  tienen modelos; se agregan a `SERVICIOS_CON_MIGRACIONES` en el Makefile el día que los
  tengan.
- **Sin RabbitMQ, tres procesos leen la base de otro servicio.** El repartidor lee las
  bandejas de inteligencia y de comercio, y los dos sondeadores la de catálogo. Con
  `RABBITMQ_URL`, cada productor publica su bandeja y nadie lee bases ajenas. El manifiesto
  declara esas lecturas como el respaldo sin broker (ADR 0046). Quitar el respaldo es una
  decisión pendiente.
- **El bloque `api` del compose nunca se ha ejecutado.** La máquina donde se escribió no
  tiene Docker. El camino verificado es `make arriba`, contra el árbol de trabajo.
- **`make bd-deriva` no corre en integración continua.** Necesita un Postgres vivo y la
  suite normal no lo tiene, así que hoy depende de que alguien la invoque. Mientras eso siga
  así, una migración incompleta puede entrar sin que nada la pare.
- El diccionario de datos cubre Identidad y Catálogo; faltan Inteligencia, Comercio y
  Operación. El manifiesto de esos tres se derivó de `ESQUEMA_OBJETIVO.md`.
- De las 53 referencias cruzadas entre bases hay 30 declaradas. Se van declarando a medida
  que cada tabla se implementa, y la función de aptitud solo exige que lo implementado esté
  declarado.
