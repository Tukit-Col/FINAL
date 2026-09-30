# Tukit

Armado asistido de kits escolares. Un acudiente sube la lista de útiles que le dio el
colegio, el sistema la interpreta, la normaliza contra un catálogo canónico y le arma kits
optimizados que balancean precio, calidad y preferencias.

Este repositorio reemplaza a los dieciséis anteriores. No es una reescritura: el trabajo
bueno y probado se porta, y lo que cambia es el modelo de dominio, que era donde estaban
los defectos.

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

## Levantar el backend completo

```bash
make preparar     # entorno y dependencias
make bd-arriba    # Postgres con las 5 bases   (con Docker)
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
| **gateway** | **8010** | La única URL que el frontend conoce. Rutea por prefijo declarado |
| identidad | 8011 | `/v1/colegios`, `/v1/grados`, `/v1/contactos` |
| catalogo | 8012 | `/v1/catalogo/*`, `/v1/listas*` |
| inteligencia | 8013 | `/v1/trabajos*`, `/v1/admin/*` |

`make estado` pregunta a la puerta cuáles de los tres responden; `make abajo` los detiene.
Cada servicio publica su OpenAPI en `/docs`. La fuente de verdad, de todas formas, es
[el contrato](arquitectura/CONTRATO_API.md), que desde la versión 1.1 documenta la
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

El `.env` del backend se copia de [`.env.ejemplo`](.env.ejemplo). Todo tiene defaults de
desarrollo, así que puedes arrancar sin tocarlo. Dos variables son opcionales pero mejoran
la demo:

- `GEMINI_API_KEY` — habilita la búsqueda semántica del catálogo. Sin ella el emparejamiento
  cae a solo léxico.
- `WOMPI_*` — la pasarela de pago. `WOMPI_MODO=falso` (por defecto) usa una pasarela simulada;
  no necesitas llaves reales para caminar el checkout.

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

---

## Cómo está organizado, y por qué así

Un monorepo con **siete desplegables independientes y cinco bases de datos separadas**.

```
servicios/     identidad  catalogo  inteligencia  comercio  operacion  ingesta  gateway
apps/          web  admin  colegio
libs/          py/tukit_comun   go/tukitgo
arquitectura/  manifiesto.toml + las funciones de aptitud
datos/         corpus, conceptos, conjuntos de referencia
infra/         compose de Postgres 16 + pgvector (cinco bases), despliegue
```

Un repositorio no es un desplegable. Que el código viva junto y se despliegue por separado
son dos decisiones distintas, y aquí se toman distinto a propósito: el
[ADR 0014](../Arquitectura/adr/0014-monorepo-con-despliegue-independiente.md) lo argumenta
con la norma 42010 y el modelo 4+1, que separan la vista de desarrollo de la vista física.

La razón concreta de haber juntado el código: mover una función de redacción a la librería
compartida, en la estructura anterior, exigió editar **siete archivos `pyproject.toml`** y
publicar un tag antes de que algo instalara. Aquí es un commit.

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
[`PERFILADO_PIPELINE.md`](../Arquitectura/PERFILADO_PIPELINE.md) y contradice la intuición
de partida en algo importante: la latencia del pipeline **sí** era CPU de Python, un 96,3 %,
pero el 95,3 % del total lo producía **una sola línea** que reconstruía un grafo de
NetworkX completo en cada ítem. Construirlo cuesta 1.673 ms; consultarlo, 0,137 ms.

Cacheándolo, una lista de veinte ítems baja de 35,1 s a 1,7 s. Reescribir en Go lo que
queda daría, por la ley de Amdahl, entre 20,0 % y 21,7 %, y casi todo sería reimplementar
pymoo, que no tiene equivalente en Go y con el que se produjeron los resultados de
hipervolumen de la tesis.

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
[plan](../Arquitectura/PLAN_TUKIT_V2.md).

La otra mitad de la superficie compartida es el [contrato de la API](arquitectura/CONTRATO_API.md).
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
- **El optimizador es una heurística, no NSGA-II.** Los tres kits salen, son comparables y
  usan el mismo vocabulario de objetivos que usaría el frente de Pareto, pero no son un
  frente. Cambiarlo es reemplazar `optimizador.elegir_por_perfil` y nada más; lo que ya es
  definitivo (la aritmética de unidades, que lo informativo no se cobre, la regla de
  recomendación) está probado aparte para que sobreviva al reemplazo.
- **El pipeline corre como tarea del propio proceso.** Un trabajo en vuelo cuando el
  servicio se reinicia queda en `procesando` hasta que alguien lo reencole con
  `POST /v1/trabajos/{id}/reintentar`. El estado sí está en la base, que es lo que hace
  posible el rescate; lo que falta es el trabajador que lo haga solo.
- **La bandeja de salida de Inteligencia no tiene repartidor.** Al publicar un trabajo se
  escribe `kits_publicados` en la misma transacción y nadie lo recoge, así que el aviso al
  acudiente no sale. Es la misma deuda que el manifiesto documenta del sistema anterior.
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
