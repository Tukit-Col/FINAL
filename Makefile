# Ejecutor de tareas del monorepo.
#
# Un solo comando por intencion, independiente del lenguaje del servicio. El
# arbol mezcla Python, Go y TypeScript, y sin esto cada quien recuerda una
# invocacion distinta.

.DEFAULT_GOAL := ayuda
.PHONY: ayuda preparar fronteras prueba lint formato verificar limpiar \
        bd-arriba bd-abajo bd-crear bd-limpiar bd-esquema bd-indices bd-verificar \
        bd-migrar bd-revision bd-deriva bd-cargar bd-datos bd-enriquecer bd-completar \
        bd-demanda bd-revisar bd-vista bd-admin bd-nivelar bd-volcar bd-limpiar-candidatos fase1 \
        bd-sembrar bd-colegios bd-listas backend arriba reanudar abajo estado humo \
        api-catalogo api-identidad api-inteligencia api-gateway \
        api-comercio api-operacion repartidor instantanea-metricas

PY := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
ALEMBIC := ../../.venv/bin/alembic

# Servicios con historia de migraciones propia. Gateway no tiene base; los
# cinco con dominio si.
SERVICIOS_CON_MIGRACIONES := identidad catalogo inteligencia comercio operacion

COMPOSE := docker compose -f infra/docker-compose.yml

# Como se habla con Postgres. Hay DOS formas legitimas de tener el motor y el
# ejecutor no deberia obligar a una: el compose de `infra/`, y un Postgres 16
# instalado en la maquina. Docker es lo reproducible, pero exigirlo bloquea a
# quien ya tiene el motor puesto, y esa persona existio: el SQL de indices se
# escribio a ciegas durante dias porque la unica via era un Docker que no
# arrancaba, teniendo al lado un Postgres que servia igual.
#
# Se prefiere el contenedor cuando esta levantado, porque es el entorno que
# reproduce a produccion; si no, se cae al local. La meta dice cual uso, para
# que nadie se pregunte contra que base acaba de correr.
#
# Dos detalles que parecen manias y no lo son, los dos aprendidos colgando la
# meta:
#
# `-w` mas `PGPASSWORD`. Sin `-w`, psql abre un prompt de contrasena y la meta
# se queda esperando para siempre en cuanto corre sin terminal, que es
# exactamente lo que pasa en integracion continua. Con `-w` falla en el acto.
#
# En local se conecta por SOCKET (sin `-h`) y no por TCP. Con `-h localhost`,
# psql negocia GSSAPI antes que la contrasena, y en una maquina con Kerberos a
# medio configurar eso no falla rapido: se queda colgado hasta el tiempo de
# espera. El socket no pasa por ahi. Se puede forzar TCP exportando
# `TUKIT_DB_HOST`, que es lo que hara falta cuando la base no sea local.
PSQL := $(shell if docker compose -f infra/docker-compose.yml ps -q postgres 2>/dev/null | grep -q .; \
	then echo "docker compose -f infra/docker-compose.yml exec -T postgres psql -w"; \
	elif [ -n "$$TUKIT_DB_HOST" ]; then echo "psql -w -h $$TUKIT_DB_HOST -p $${TUKIT_DB_PORT:-5432}"; \
	else echo "psql -w -p $${TUKIT_DB_PORT:-5432}"; fi)
BD_MODO := $(if $(findstring docker,$(PSQL)),contenedor,local)
export PGPASSWORD ?= $(or $(TUKIT_DB_PASSWORD),tukit)
export PGCONNECT_TIMEOUT ?= 10

ayuda:  ## Muestra esta ayuda
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

preparar:  ## Crea el entorno e instala las dependencias
	uv venv --python 3.12
	uv sync --all-packages 2>/dev/null || uv pip install pytest pytest-asyncio ruff

fronteras:  ## Verifica las fronteras de arquitectura (rapido, corre primero)
	@$(PYTEST) arquitectura/ -q

prueba: fronteras  ## Corre toda la suite, empezando por las fronteras
	@$(PYTEST) libs servicios -q

lint:  ## Revisa estilo y errores estaticos
	@$(RUFF) check .
	@$(RUFF) format --check .

formato:  ## Aplica formato
	@$(RUFF) check --fix .
	@$(RUFF) format .

verificar: lint prueba  ## Todo lo que corre la integracion continua

limpiar:  ## Borra artefactos
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .ruff_cache

# --- Base de datos (desarrollo local) -------------------------------------
# Un Postgres 16 con pgvector hospeda las cinco bases. El init crea las bases y
# habilita las extensiones (vector y pg_trgm, las dos mitades de la busqueda
# hibrida); el esquema de cada servicio lo materializa su propio
# `python -m tukit_<servicio>`. Ver infra/docker-compose.yml.
#
# El flujo completo desde cero son dos comandos: `bd-arriba` y `bd-esquema`.
# `bd-esquema` encadena `bd-indices` al final, asi que no hay un tercer paso que
# recordar ni una base que quede a medio construir.

bd-arriba:  ## Levanta Postgres (5 bases + extensiones) y espera a que este listo
	@$(COMPOSE) up -d
	@echo "Esperando a Postgres..."
	@$(COMPOSE) exec -T postgres sh -c 'until pg_isready -U tukit -q; do sleep 1; done'
	@echo "Postgres listo en localhost:5432 (usuario tukit)."

bd-crear:  ## Crea el usuario y las 5 bases en un Postgres YA instalado (sin Docker)
	@echo "Motor: $(BD_MODO)"
	@# El compose crea las bases con su script de init; un Postgres instalado
	@# en la maquina no pasa por ahi, asi que el arranque desde cero se
	@# quedaba a medias justo en el primer paso. Esta meta es ese script,
	@# hecho idempotente para poder correrla sobre una instalacion a medias.
	@#
	@# Se conecta con el usuario de la maquina y no con `tukit`, porque el
	@# usuario `tukit` es precisamente lo que puede no existir todavia.
	@psql -w -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='tukit'" | grep -q 1 \
		|| psql -w -d postgres -c "CREATE ROLE tukit LOGIN PASSWORD 'tukit' CREATEDB"
	@for base in identidad catalogo inteligencia comercio operacion; do \
		psql -w -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='tukit_$$base'" | grep -q 1 \
			|| psql -w -d postgres -c "CREATE DATABASE tukit_$$base OWNER tukit"; \
		psql -w -d "tukit_$$base" -q -c "CREATE EXTENSION IF NOT EXISTS vector" \
			-c "CREATE EXTENSION IF NOT EXISTS pg_trgm"; \
		echo "  ok   tukit_$$base"; \
	done

bd-abajo:  ## Detiene Postgres, conservando los datos
	@$(COMPOSE) down

bd-limpiar:  ## Detiene Postgres y BORRA los datos (volumen incluido)
	@$(COMPOSE) down -v

# PYTHONPATH explicito para `python -m`: pytest usa el pythonpath del pyproject,
# pero `python -m` no. Se listan la libreria compartida y cada servicio portado.
ESQUEMA_PATH := libs/py/tukit_comun:servicios/identidad:servicios/catalogo:servicios/inteligencia:servicios/gateway:servicios/comercio:servicios/operacion

# Cada archivo de aqui se llama como el servicio dueno de la base a la que se
# aplica: `catalogo.sql` -> `tukit_catalogo`. La convencion es lo que permite
# que agregar los indices de otro servicio sea crear un archivo y no editar
# esta meta.
INDICES := infra/postgres/indices

bd-esquema:  ## Materializa el esquema de identidad y catalogo, y sus indices
	@$(PY) -c 'import asyncpg' 2>/dev/null || uv pip install asyncpg
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_identidad
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_catalogo
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_inteligencia esquema
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_comercio
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_operacion
	@$(MAKE) --no-print-directory bd-indices

# Va aparte de `bd-esquema` porque no lo hace create_all: SQLAlchemy crea los
# indices declarados en los modelos, pero HNSW y gin_trgm_ops son sintaxis de
# Postgres que no se puede poner en un modelo que tambien corre en SQLite.
# ON_ERROR_STOP para que una extension faltante falle aqui, ruidosamente, y no
# en la primera consulta de busqueda.
bd-indices:  ## Aplica los indices de Postgres que create_all no genera (HNSW, trigramas)
	@echo "Motor: $(BD_MODO)"
	@for sql in $(INDICES)/*.sql; do \
		[ -e "$$sql" ] || continue; \
		servicio=$$(basename "$$sql" .sql); \
		$(PSQL) -q -v ON_ERROR_STOP=1 -U tukit -d "tukit_$$servicio" < "$$sql" || exit 1; \
		echo "[$$servicio] indices aplicados"; \
	done

# Existe porque el SQL de arriba se escribio y se reviso sin poder ejecutarlo:
# la maquina donde se construyo no tenia Docker. Revisar a ojo que una clase de
# operadores exista no es lo mismo que verla crear el indice, y la diferencia
# solo aparece contra un motor vivo. Esto deja la comprobacion en un comando en
# vez de en una nota que nadie vuelve a leer.
#
# Comprueba lo que de verdad importa y no solo que el comando no fallo: que las
# extensiones esten en LAS CINCO bases (no solo en catalogo) y que los indices
# existan con nombre propio. Un indice que no se creo no da error en ninguna
# consulta: solo la vuelve un recorrido secuencial, en silencio.
bd-migrar:  ## Lleva cada base a la ultima revision de SU servicio
	@echo "Motor: $(BD_MODO)"
	@for s in $(SERVICIOS_CON_MIGRACIONES); do \
		( cd servicios/$$s && PYTHONPATH=".:../../libs/py/tukit_comun" \
			$(ALEMBIC) upgrade head ) || exit 1; \
		echo "[$$s] al dia"; \
	done
	@$(MAKE) --no-print-directory bd-indices

bd-revision:  ## Genera una revision comparando modelos contra la base. m='que cambio' s=servicio
	@test -n "$(m)" || { echo "Falta el mensaje: make bd-revision m='agrega tal cosa' s=catalogo"; exit 1; }
	@test -n "$(s)" || { echo "Falta el servicio: s=catalogo"; exit 1; }
	@cd servicios/$(s) && PYTHONPATH=".:../../libs/py/tukit_comun" \
		$(ALEMBIC) revision --autogenerate -m "$(m)"
	@echo
	@echo "LEE la revision antes de aplicarla. Dos cosas que el autogenerador no hace:"
	@echo "  - omite las llaves marcadas 'use_alter'; hay que poner el op.create_foreign_key"
	@echo "  - deja el 'Por que este cambio' vacio, y el diff no lo puede responder"

bd-demanda:  ## Mide contra el corpus que atributo filtra y que atributo solo describe
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.demanda_atributos $(ARGS)

bd-revisar:  ## Revisa una version de lista sin revisar (unica via a las tiendas)
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.descubrir $(ARGS)

bd-cargar:  ## Carga los datos curados del catalogo y reporta que les falta
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.cargador --datos ../../datos/catalogo

bd-datos:  ## Revisa los datos curados sin escribir nada
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.cargador --datos ../../datos/catalogo --solo-validar

bd-enriquecer:  ## Saca empaque, atributos y personaje del nombre; --imagenes va a la red
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.enriquecer $(ARGS)

bd-completar:  ## Llena los conceptos sin producto y los niveles que faltan
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.completar $(ARGS)

bd-vista:  ## Arma el HTML del catalogo para revisarlo con ojos de papa
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.vista $(ARGS)

bd-admin:  ## Levanta la UI de admin para curar el catalogo a mano (CRUD); ARGS=--abrir la abre en el navegador
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.admin $(ARGS)

fase1:  ## Parsea renglones y los empareja con el catalogo. Uso: make fase1 ARGS='--texto "block oficio"'
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) ensayos/fase1.py $(ARGS)

bd-nivelar:  ## Acomoda el nivel para que el precio lo ordene; --escribir guarda
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.nivelar $(ARGS)

bd-volcar:  ## Vuelca los productos de la base a los CSV curados; --escribir guarda
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.volcar $(ARGS)

bd-limpiar-candidatos:  ## Saca del catalogo lo que la maquina metio sin revisar y lo encola; ARGS=--ensayo cuenta
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m migraciones.limpieza_candidatos_a_cola $(ARGS)

bd-sembrar:  ## Siembra SOLO el catalogo curado de productos. Idempotente.
	@$(MAKE) --no-print-directory bd-cargar
	@echo "Colegios y listas ya NO se siembran: se crean de verdad probando (identidad + revisar en la cola)."
	@echo "Para sembrar datos falsos a mano: make bd-colegios / make bd-listas"

bd-colegios:  ## (manual) Siembra los 17 colegios y sus sedes en Identidad. Datos falsos, fuera del sembrado por defecto.
	@cd servicios/identidad && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_identidad.cargador --datos ../../datos/listas $(ARGS)

bd-listas:  ## (manual) Siembra las listas oficiales por colegio y grado. Datos falsos, fuera del sembrado por defecto.
	@cd servicios/catalogo && PYTHONPATH=".:../../libs/py/tukit_comun" \
		../../$(PY) -m tukit_catalogo.cargador_listas --datos ../../datos/listas $(ARGS)

bd-deriva:  ## Falla si el esquema migrado y los modelos no dicen lo mismo
	@$(PY) arquitectura/verificar_deriva.py

# --- La superficie HTTP ----------------------------------------------------
# Seis procesos: cinco servicios con dominio y una puerta de enlace que le da
# al frontend UNA sola URL base, que es la unica direccion que el contrato le
# promete a quien consume.
#
#   8010  gateway       <- lo que el frontend usa
#   8011  identidad     colegios, sedes, grados, contacto
#   8012  catalogo      conceptos, productos, ofertas, listas, emparejar
#   8013  inteligencia  trabajos y cola de revision
#   8014  comercio      pedidos, inventario, pagos (Wompi), entrega
#   8015  operacion     casos/PQRS, notificaciones, auditoria, telemetria
#
# El bloque empieza en 8010 y no en 8000 por una razon aburrida y real: 8000
# es el puerto por omision de medio mundo (uvicorn, http.server, Django) y en
# la maquina donde esto se escribio ya lo tenia otro proyecto. Los cuatro
# seguidos se recuerdan igual de facil y no chocan con nada. Se cambian con
# `make arriba PUERTO_GATEWAY=9000`.
#
# `arriba` los lanza en segundo plano con su pid en `.ejecucion/`. No es un
# supervisor: si uno se cae, se cae y ya. Para desarrollo alcanza, y la
# alternativa (un compose con las cuatro imagenes) esta en infra/ para quien
# tenga Docker. Cada meta `api-*` levanta UNO en primer plano, que es lo que se
# quiere cuando se esta depurando ese.
EJECUCION := .ejecucion
API_PATH := $(ESQUEMA_PATH)

PUERTO_GATEWAY ?= 8010
PUERTO_IDENTIDAD ?= 8011
PUERTO_CATALOGO ?= 8012
PUERTO_INTELIGENCIA ?= 8013
PUERTO_COMERCIO ?= 8014
PUERTO_OPERACION ?= 8015

# Se exportan para que cada proceso sepa donde estan los otros sin que nadie
# escriba una URL en el codigo. Si se cambia un puerto arriba, todo sigue
# cuadrando.
export TUKIT_IDENTIDAD_URL ?= http://127.0.0.1:$(PUERTO_IDENTIDAD)
export TUKIT_CATALOGO_URL ?= http://127.0.0.1:$(PUERTO_CATALOGO)
export TUKIT_INTELIGENCIA_URL ?= http://127.0.0.1:$(PUERTO_INTELIGENCIA)
export TUKIT_COMERCIO_URL ?= http://127.0.0.1:$(PUERTO_COMERCIO)
export TUKIT_OPERACION_URL ?= http://127.0.0.1:$(PUERTO_OPERACION)

api-identidad:  ## Levanta SOLO identidad, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_identidad.api --puerto $(PUERTO_IDENTIDAD)

api-catalogo:  ## Levanta SOLO catalogo, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_catalogo.api --puerto $(PUERTO_CATALOGO)

api-inteligencia:  ## Levanta SOLO inteligencia, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_inteligencia.api --puerto $(PUERTO_INTELIGENCIA)

api-comercio:  ## Levanta SOLO comercio, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_comercio.api --puerto $(PUERTO_COMERCIO)

api-operacion:  ## Levanta SOLO operacion, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_operacion.api --puerto $(PUERTO_OPERACION)

api-gateway:  ## Levanta SOLO la puerta de enlace, en primer plano
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_gateway.api --puerto $(PUERTO_GATEWAY)

repartidor:  ## Reparte los eventos de las bandejas (una pasada; usa s=--seguir para bucle)
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_operacion.repartidor $(s)

instantanea-metricas:  ## Congela el snapshot de hoy de cobertura/match por colegio en metrica_diaria (idempotente; correlo por sesion). Requiere los servicios arriba.
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_operacion.instantanea

poller:  ## Drena lista_verificada del catalogo y arma el kit del padre (una pasada; s=--seguir para bucle)
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_inteligencia.poller $(s)

poller-identidad:  ## Drena colegio_verificado del catalogo y da de alta el colegio aliado (s=--seguir para bucle)
	@PYTHONPATH="$(API_PATH)" $(PY) -m tukit_identidad.poller $(s)

reanudar: arriba  ## Reanuda tras un apagado: solo levanta los procesos, NO siembra (usa `backend` solo para reconstruir de cero)

arriba:  ## Levanta los seis procesos HTTP en segundo plano
	@mkdir -p $(EJECUCION)
	@$(MAKE) --no-print-directory abajo >/dev/null 2>&1 || true
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_identidad.api --puerto $(PUERTO_IDENTIDAD) \
		> $(EJECUCION)/identidad.log 2>&1 & echo $$! > $(EJECUCION)/identidad.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_catalogo.api --puerto $(PUERTO_CATALOGO) \
		> $(EJECUCION)/catalogo.log 2>&1 & echo $$! > $(EJECUCION)/catalogo.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_inteligencia.api --puerto $(PUERTO_INTELIGENCIA) \
		> $(EJECUCION)/inteligencia.log 2>&1 & echo $$! > $(EJECUCION)/inteligencia.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_comercio.api --puerto $(PUERTO_COMERCIO) \
		> $(EJECUCION)/comercio.log 2>&1 & echo $$! > $(EJECUCION)/comercio.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_operacion.api --puerto $(PUERTO_OPERACION) \
		> $(EJECUCION)/operacion.log 2>&1 & echo $$! > $(EJECUCION)/operacion.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_gateway.api --puerto $(PUERTO_GATEWAY) \
		> $(EJECUCION)/gateway.log 2>&1 & echo $$! > $(EJECUCION)/gateway.pid
	@echo "Esperando a que respondan..."
	@for i in $$(seq 1 60); do \
		curl -fs http://127.0.0.1:$(PUERTO_GATEWAY)/v1/servicios 2>/dev/null | grep -q '"todos_arriba":true' && break; \
		sleep 0.5; \
	done
	@# Los tres trabajadores de fondo (§10): sin ellos el aviso al acudiente no
	@# sale (repartidor), el kit del padre no se arma (poller) y un colegio nuevo
	@# nunca se vuelve aliado (poller-identidad). Antes se lanzaban a mano y se
	@# olvidaban; ahora suben con el backend. Cada uno en --seguir con su pid.
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_operacion.repartidor --seguir \
		> $(EJECUCION)/repartidor.log 2>&1 & echo $$! > $(EJECUCION)/repartidor.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_inteligencia.poller --seguir \
		> $(EJECUCION)/poller.log 2>&1 & echo $$! > $(EJECUCION)/poller.pid
	@PYTHONPATH="$(API_PATH)" nohup $(PY) -m tukit_identidad.poller --seguir \
		> $(EJECUCION)/poller-identidad.log 2>&1 & echo $$! > $(EJECUCION)/poller-identidad.pid
	@$(MAKE) --no-print-directory estado

abajo:  ## Detiene los seis procesos HTTP y los tres trabajadores de fondo
	@for s in gateway operacion comercio inteligencia catalogo identidad repartidor poller poller-identidad; do \
		[ -f $(EJECUCION)/$$s.pid ] && kill $$(cat $(EJECUCION)/$$s.pid) 2>/dev/null; \
		rm -f $(EJECUCION)/$$s.pid; \
	done; true
	@echo "Procesos detenidos."

estado:  ## Dice cuales de los seis estan arriba, preguntandoles
	@curl -fs http://127.0.0.1:$(PUERTO_GATEWAY)/v1/servicios | $(PY) -m json.tool \
		|| echo "  La puerta no responde en http://127.0.0.1:$(PUERTO_GATEWAY)"
	@echo "  Base para el frontend: http://127.0.0.1:$(PUERTO_GATEWAY)"

backend: bd-migrar bd-sembrar arriba  ## De cero a backend vivo: migra, siembra y levanta
	@echo
	@echo "Backend listo. El frontend apunta a http://127.0.0.1:$(PUERTO_GATEWAY)"
	@echo "Documentacion viva: http://127.0.0.1:$(PUERTO_CATALOGO)/docs y :$(PUERTO_INTELIGENCIA)/docs"

humo:  ## Golpea los endpoints vivos y falla si alguno no devuelve datos
	@$(PY) arquitectura/humo.py

bd-verificar:  ## Comprueba contra el motor vivo que extensiones e indices existan
	@echo "Motor: $(BD_MODO)"
	@fallas=0; \
	for base in identidad catalogo inteligencia comercio operacion; do \
		for ext in vector pg_trgm; do \
			$(PSQL) -qtA -U tukit -d "tukit_$$base" \
				-c "SELECT 1 FROM pg_extension WHERE extname='$$ext'" 2>/dev/null | grep -q 1 \
				&& echo "  ok   tukit_$$base: $$ext" \
				|| { echo "  FALTA tukit_$$base: $$ext"; fallas=1; }; \
		done; \
	done; \
	for idx in ix_producto_embedding_hnsw ix_producto_nombre_trgm; do \
		$(PSQL) -qtA -U tukit -d tukit_catalogo \
			-c "SELECT 1 FROM pg_indexes WHERE indexname='$$idx'" 2>/dev/null | grep -q 1 \
			&& echo "  ok   tukit_catalogo: $$idx" \
			|| { echo "  FALTA tukit_catalogo: $$idx"; fallas=1; }; \
	done; \
	[ $$fallas -eq 0 ] && echo "Todo en su sitio." || { echo "Faltan piezas: revisa bd-esquema."; exit 1; }
