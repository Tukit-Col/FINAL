# Ejecutor de tareas del monorepo.
#
# Un solo comando por intencion, independiente del lenguaje del servicio. El
# arbol mezcla Python, Go y TypeScript, y sin esto cada quien recuerda una
# invocacion distinta.

.DEFAULT_GOAL := ayuda
.PHONY: ayuda preparar fronteras prueba lint formato verificar limpiar

PY := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff

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
