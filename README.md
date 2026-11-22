# Tukit

Armado asistido de kits escolares. Un acudiente sube la lista de útiles que le dio el
colegio, el sistema la interpreta, la normaliza contra un catálogo canónico y le arma kits
optimizados que balancean precio, calidad y preferencias.

```bash
make preparar     # entorno y dependencias
make fronteras    # verifica las fronteras de arquitectura
make verificar    # todo lo que corre la integración continua
```

## Estructura

```
servicios/     identidad  catalogo  inteligencia  comercio  operacion  gateway
apps/          web  admin
libs/          py/tukit_comun   ts/tukit-contrato
arquitectura/  manifiesto.toml y las pruebas de fronteras
datos/         catálogo, listas, colegios y curaduría
ensayos/       experimentos y bancos de prueba
infra/         compose de Postgres 16 + pgvector (una base por servicio), RabbitMQ y Redis
```

Cada servicio tiene su propia base, su propia imagen y su propio historial de migraciones.
El contrato de la API está en [`CONTRATO_API.md`](CONTRATO_API.md): las apps y `libs/ts/tukit-contrato`
se derivan de él.

### Invariantes

Los cuatro primeros los verifica `arquitectura/test_fronteras.py` en cada integración; si
fallan, la construcción se rompe.

1. Ningún servicio importa código de otro servicio. Solo de `libs/`.
2. Ningún servicio declara una tabla de un dominio ajeno.
3. Ningún servicio se conecta a la base de otro.
4. Toda referencia a otro dominio está declarada en `arquitectura/manifiesto.toml`.
5. Cada servicio construye su imagen y se despliega por separado.

`arquitectura/test_fronteras_se_activan.py` introduce una infracción de cada tipo y comprueba
que se detecte.

### Dónde vive cada cosa

| Paquete o módulo | Responsabilidad |
|---|---|
| `inteligencia/optimizador/` | `tipos`, `candidatos` (filtros duros y heurística por perfil), `preferencias`, `frente` (enumeración exacta y NSGA-II), `lineas` (consolidación y personaje), `recomendacion` (MAUT) y `armado` (`armar_los_tres`, punto de entrada) |
| `inteligencia/trabajos/` | `base` (tablas, configuración, excepciones), `pipeline` (creación y etapas), `lectura`, `solicitudes`, `revision`, `versiones`, `cambios`, y `formas` y `anclas` como ayudantes compartidos |
| `catalogo/extraccion.py` | Reglas puras: empaque, atributos y personaje desde el nombre o la ficha. `enriquecer.py` solo orquesta el lote |
| `catalogo/clasificacion.py` | Reglas puras: de un renglón de lista a un concepto. `descubrir.py` conserva la revisión y el alta |
| `tukit_comun/` | Base de datos, outbox, broker, caché, HTTP con resiliencia, telemetría y lectura del encabezado `Authorization` |

Dentro de cada paquete las dependencias van en un solo sentido y no hay ciclos. La ruta de
consulta del catálogo (`consulta.py`) lee de `extraccion` y `clasificacion`, no de los CLI.

## Requisitos

- **Python 3.12+** y [`uv`](https://github.com/astral-sh/uv).
- **Node 20+** y **npm** (las apps son un workspace de npm).
- **Postgres 16 con `pgvector`**, o **Docker**, que lo levanta con `make bd-arriba`. Sin Docker
  hace falta Postgres 16 local y `make bd-crear`.
- **RabbitMQ 3.13 o 4.x**, opcional. Sin él, los procesos de fondo sondean las bases.
- **Redis 7 u 8**, opcional. Sin él no hay caché y el límite de tasa cuenta en la memoria del
  gateway. Con Docker, `make infra-arriba` lo levanta.

## Levantar el backend

```bash
make preparar     # entorno y dependencias
make bd-arriba    # Postgres con las bases y RabbitMQ   (con Docker)
make bd-crear     # las bases + extensiones             (sin Docker, Postgres 16 local)
make backend      # migra, siembra y levanta los procesos
make humo         # golpea la API y falla si algún endpoint viene vacío
```

`make backend` encadena `bd-migrar`, `bd-sembrar` y `arriba`, y las tres son idempotentes.
`make estado` pregunta al gateway cuáles servicios responden y `make abajo` los detiene.

| Proceso | Puerto | Qué atiende |
|---|---|---|
| **gateway** | **8010** | La única URL que conocen las apps. Rutea por prefijo y limita la tasa |
| identidad | 8011 | Colegios, sedes, grados y contacto |
| catalogo | 8012 | Conceptos, productos, ofertas, listas y emparejamiento |
| inteligencia | 8013 | Trabajos y cola de revisión |
| comercio | 8014 | Pedidos, inventario, pagos y entrega |
| operacion | 8015 | Casos, notificaciones, auditoría y telemetría |

`make arriba` lanza también los procesos de fondo: trabajador, sondeadores, repartidor y
barredor. Si RabbitMQ responde en `RABBITMQ_URL` (por omisión `amqp://guest:guest@localhost:5672/`),
los lanza con el broker y suma los publicadores de bandeja y los de supresión; si no, sondean las
bases. Con Redis hace lo mismo en `REDIS_URL` (por omisión `redis://localhost:6379/0`):
catálogo, inteligencia y el gateway arrancan con caché y con el contador de límite compartido; con
`make arriba REDIS_URL=` arrancan sin él. `make prueba-redis` y `make prueba-colas` corren las
pruebas contra Redis y RabbitMQ.

Cada servicio publica su OpenAPI en `/docs`. `make humo` exige contenido en cada respuesta y
recorre el ciclo completo: crear un trabajo, esperarlo, aprobarlo y verificar que salgan los
kits con uno recomendado.

El `.env` del backend se copia de [`.env.ejemplo`](.env.ejemplo). Todo tiene valores de
desarrollo, y dos variables son opcionales:

- `GEMINI_API_KEY`: habilita la búsqueda semántica del catálogo. Sin ella el emparejamiento es solo léxico.
- `WOMPI_*`: la pasarela de pago. `WOMPI_MODO=falso` (por defecto) usa una pasarela simulada.

## Levantar las apps

Dos apps de Next.js 16: la pública (`web`, acudiente) y el back-office (`admin`, operación).
Ambas hablan solo con el gateway.

```bash
npm install        # instala los workspaces desde la raíz
npm run dev:web    # app pública  → http://127.0.0.1:3000
npm run dev:admin  # back-office  → http://127.0.0.1:3001
```

Cada app necesita `TUKIT_API_URL` en su `.env.local`; si falta, falla de entrada.

```bash
# apps/web/.env.local  y  apps/admin/.env.local
TUKIT_API_URL=http://127.0.0.1:8010
```

La dirección de entrega del checkout se busca en OpenStreetMap y se confirma moviendo un pin en
el mapa; no necesita llave.

## Pruebas

```bash
make fronteras        # arquitectura/
make prueba           # servicios, libs y ensayos, sin RabbitMQ ni Redis
make lint             # ruff
make tipos            # mypy (estricto en tukit_comun)
npm test              # contrato, web y admin
npm run typecheck     # tsc
npm run lint          # eslint
```

## Datos y curaduría de listas

`datos/` guarda los colegios, las listas y el catálogo. Curar una lista (decidir a qué
concepto corresponde cada renglón y cerrarla en la cola) queda en la base local; para que llegue
a los demás viaja por git como CSV:

```bash
make curaduria-exportar   # base -> datos/  (luego git add datos/ && git commit)
make curaduria-importar   # datos/ -> base   (después de un git pull)
```

En Windows, `.\tukit.ps1 exportar` e `.\tukit.ps1 importar` hacen lo mismo.

| Archivo | Qué lleva |
|---|---|
| `datos/curaduria/listas_revisadas.csv` | Un renglón por ítem de la última versión revisada de cada lista, con el concepto por código |
| `datos/curaduria/colegios.csv`, `sedes.csv` | Los colegios que esas listas nombran |
| `datos/catalogo/conceptos.csv` | Los conceptos creados curando se agregan; los existentes se actualizan |
| `datos/catalogo/productos_canonicos.csv`, `ofertas_tienda.csv`, `precios_oferta.csv`, `productos_procedencia.csv` | Los productos aprobados, los reclasificados y sus atributos corregidos a mano |

Los vectores de búsqueda semántica no se versionan: después de importar, `make bd-enriquecer` los
calcula para los productos nuevos (una petición a Gemini por producto). `curaduria-importar` corre
`bd-cargar` primero y es idempotente: una lista que ya dice lo mismo no se toca, y una que cambió
crea una versión nueva. No viajan el PDF original ni el contacto del colegio.

Exporta antes de hacer `git pull`: `bd-cargar` actualiza los conceptos desde el CSV y un
sinónimo agregado en la base y no exportado se perdería. Los códigos de concepto nuevos
(`C100`, `C101`…) se numeran en cada base, así que dos personas creando conceptos a la vez
chocarían.

## Usuarios de prueba

Las seis cuentas demo entran con la clave **`demo1234`**; las siembra `make bd-sembrar`. Para
cambiarla: `python -m tukit_identidad.sembrar_acceso --clave otra`.

| Correo | Rol | Dónde aterriza |
|---|---|---|
| `mama@ejemplo.com`, `papa@ejemplo.com` | acudiente | web · :3000 · `/dashboard` |
| `operador@tukit.co`, `admin@tukit.co` | operador, admin | admin · :3001 · `/` (cola de revisión) |
| `rectoria@colegio.edu.co`, `docente@colegio.edu.co` | colegio_admin, colegio_docente | portal de colegio, aún sin construir |

El enrutado por rol vive en `libs/ts/tukit-contrato/src/origen.ts::destinoDe`.

## Pagos de prueba con Wompi

Con `WOMPI_MODO=falso` el pago abre una pantalla simulada que aprueba sola (con
`?resultado=rechazado` se fuerza el rechazo) y no sale a la red. Con `WOMPI_MODO=sandbox` lleva al
checkout real de Wompi en modo de **pruebas**: no se mueve dinero. Comercio se niega a arrancar si
alguna llave no es de prueba, y no existe un modo de producción.

Las llaves salen de [comercios.wompi.co](https://comercios.wompi.co) → *Desarrolladores*, con el
interruptor en modo de pruebas, y van en el `.env` de la raíz:

| Variable | Dónde está en el panel | Empieza por |
|---|---|---|
| `WOMPI_LLAVE_PUBLICA` | Llave pública | `pub_test_` |
| `WOMPI_LLAVE_PRIVADA` | Llave privada | `prv_test_` |
| `WOMPI_SECRETO_EVENTOS` | Secretos → Eventos | `test_events_` |
| `WOMPI_SECRETO_INTEGRIDAD` | Secretos → Integridad | `test_integrity_` |

Reinicia el stack con esas variables cargadas: en Linux o macOS, `set -a; . ./.env; set +a; make arriba`;
en Windows, `tukit.ps1` carga el `.env` solo.

El pago se abre con el [widget de Wompi](https://docs.wompi.co/docs/colombia/widget-checkout-web/),
un modal sobre el kit. Con tarjeta y Nequi el acudiente no sale de Tukit; PSE lleva la pestaña al
banco y vuelve a `/pago/resultado?id=<transacción>`, página que le pregunta a Wompi de servidor a
servidor cómo quedó el pago (`POST /v1/pagos/{id}/sincronizar`). El checkout de Wompi responde 403
cuando una URL suya lleva un retorno a `localhost` o a una IP privada, por eso el widget se abre con
`bootstrapTransport: "postmessage"`; si el modal se queda girando, es esto.

En "Mis pedidos" un pedido pendiente se paga o se cancela sin rearmar el kit, durante 24 horas.
Cancelar le pregunta antes a Wompi si hay un pago en curso. En modo falso los montos simulados
viven en la memoria de Comercio: si lo reinicias entre "Pagar" y la aprobación obtendrás
`transaccion_no_existe`.

Datos de prueba ([docs.wompi.co](https://docs.wompi.co/docs/colombia/datos-de-prueba-en-sandbox/)):

| Medio | Dato | Resultado |
|---|---|---|
| Tarjeta | `4242 4242 4242 4242`, cualquier CVC de 3 dígitos y fecha futura | Aprobado |
| Tarjeta | `4111 1111 1111 1111`, cualquier CVC de 3 dígitos y fecha futura | Rechazado |
| Nequi | `3991111111` | Aprobado |
| Nequi | `3992222222` | Rechazado |
| PSE | Banco "Banco que aprueba" (código `1` por API) | Aprobado |
| PSE | Banco "Banco que rechaza" (código `2` por API) | Rechazado |

El webhook `POST /v1/webhooks/wompi` también confirma el pago, pero Wompi tiene que poder
alcanzarlo. Para probarlo desde tu máquina expón el gateway (`cloudflared tunnel --url http://127.0.0.1:8010`)
y pega `https://<túnel>/v1/webhooks/wompi` en el panel de Wompi. Sin túnel, la página de resultado
confirma igual.

## Producción: llaves obligatorias

**Regla:** todo servidor real corre con `TUKIT_ENTORNO=produccion`, y con eso el código exige las
dos llaves. Sin ellas identidad e inteligencia no arrancan (`ConfiguracionInsegura`); no hay forma
de saltarse el chequeo con un aviso en consola.

| Variable | Qué protege | Se genera con |
|---|---|---|
| `TUKIT_LLAVE_SESION` | La firma de los tokens. Sin ella se usa la de desarrollo, que está en este repo público: cualquiera fabricaría una sesión de admin. Mínimo 32 caracteres. | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `TUKIT_LLAVE_CIFRADO` | Los datos personales derivados (nombres de los hijos, preferencias). Sin ella se guardan en claro. | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Las llaves no se suben a git ni se comparten por chat. Lo guardado en claro antes de poner
`TUKIT_LLAVE_CIFRADO` se sigue leyendo (lleva el prefijo `claro:`); lo nuevo sale cifrado. Cambiar
una llave de cifrado ya usada deja ilegible lo que cifró: no se rota sin migrar los datos.

## Base de datos

`libs/py/tukit_comun` tiene el motor, las sesiones y la configuración por entorno, y `infra/`
levanta un Postgres 16 con pgvector que hospeda las bases. Ningún servicio escribe el nombre de su
base: se lo pide a la librería.

```bash
make bd-arriba     # Postgres con las bases + pgvector y pg_trgm
make bd-migrar     # lleva cada base a la última revisión de SU servicio, + índices
make bd-deriva     # falla si el esquema migrado y los modelos no dicen lo mismo
make bd-verificar  # comprueba que extensiones e índices existan
make bd-abajo      # detiene, conservando datos   (bd-limpiar los borra)

make bd-revision m='agrega tal cosa' s=catalogo   # genera una revisión nueva
make bd-esquema    # create_all, atajo de desarrollo
```

Las metas usan el contenedor de `infra/` si está levantado y, si no, un Postgres local; cada una
imprime cuál usó.

**Migraciones.** Cada servicio tiene su `alembic.ini` y su carpeta `migraciones/`, y la fuente de
verdad del esquema son las migraciones, no `bd-esquema`. `make bd-deriva` compara el esquema que
dejan las migraciones con el que declaran los modelos y atrapa lo que ninguna otra prueba ve, por
ejemplo una restricción declarada en el modelo que la migración no crea. Las llaves marcadas
`use_alter` las omite el autogenerador y hay que agregar el `op.create_foreign_key` a mano.

**Índices.** `bd-indices` crea los de la búsqueda híbrida (HNSW sobre el embedding y GIN de
trigramas sobre el nombre) desde `infra/postgres/indices/`; no se declaran en los modelos porque
son sintaxis exclusiva de Postgres y las pruebas de dominio corren en SQLite.

**Extensiones.** El script de init las crea en volúmenes nuevos y `tukit_comun.bd` las vuelve a
pedir con `IF NOT EXISTS` antes de crear tablas.

### Limitaciones conocidas

- Sin RabbitMQ, tres procesos leen la base de otro servicio: el repartidor lee las bandejas de
  inteligencia y de comercio, y los dos sondeadores la de catálogo. El manifiesto declara esas
  lecturas como el respaldo sin broker.
- `make bd-deriva` necesita un Postgres vivo y no corre en integración continua.
- El bloque `api` del compose no se ha ejecutado; el camino verificado es `make arriba`.
