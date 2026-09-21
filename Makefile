# Ejecutor de tareas del monorepo.
#
# Un solo comando por intencion, independiente del lenguaje del servicio. El
# arbol mezcla Python, Go y TypeScript, y sin esto cada quien recuerda una
# invocacion distinta.

.DEFAULT_GOAL := ayuda
.PHONY: ayuda preparar fronteras prueba lint formato verificar limpiar \
        bd-arriba bd-abajo bd-limpiar bd-esquema

PY := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

COMPOSE := docker compose -f infra/docker-compose.yml

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
# habilita la extension; el esquema de cada servicio lo materializa su propio
# `python -m tukit_<servicio>`. Ver infra/docker-compose.yml.

bd-arriba:  ## Levanta Postgres (5 bases + pgvector) y espera a que este listo
	@$(COMPOSE) up -d
	@echo "Esperando a Postgres..."
	@$(COMPOSE) exec -T postgres sh -c 'until pg_isready -U tukit -q; do sleep 1; done'
	@echo "Postgres listo en localhost:5432 (usuario tukit)."

bd-abajo:  ## Detiene Postgres, conservando los datos
	@$(COMPOSE) down

bd-limpiar:  ## Detiene Postgres y BORRA los datos (volumen incluido)
	@$(COMPOSE) down -v

# PYTHONPATH explicito para `python -m`: pytest usa el pythonpath del pyproject,
# pero `python -m` no. Se listan la libreria compartida y cada servicio portado.
ESQUEMA_PATH := libs/py/tukit_comun:servicios/identidad:servicios/catalogo

bd-esquema:  ## Materializa el esquema de los servicios portados (identidad, catalogo)
	@$(PY) -c 'import asyncpg' 2>/dev/null || uv pip install asyncpg
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_identidad
	@PYTHONPATH="$(ESQUEMA_PATH)" $(PY) -m tukit_catalogo
