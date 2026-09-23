# Una imagen para los cuatro procesos HTTP, parametrizada por el modulo que corre.
#
# El quinto invariante dice que cada servicio construye su imagen y se despliega
# por separado, y esto NO lo contradice: la imagen es la misma receta y el
# desplegable sigue siendo uno por servicio, con su propio comando, su propio
# puerto y su propia base. Lo que se comparte es el Dockerfile, igual que se
# comparte el `alembic.ini` sin que eso junte las historias de migracion.
#
# Se hace asi porque hoy los cuatro son Python 3.12 con las mismas tres
# dependencias de web y difieren en una linea. Cuatro Dockerfile identicos
# salvo el `CMD` es el mismo copiar y pegar que el ADR 0014 vino a quitar: el
# quinto se desincroniza. El dia que uno necesite algo propio (modelos
# descargados en `inteligencia`, por ejemplo) se le saca su Dockerfile y este
# se queda con los demas.

FROM python:3.12-slim

# `uv` para instalar: resuelve el espacio de trabajo entero con un solo lock,
# que es justo lo que el monorepo ya usa en local. Sin el habria que decidir
# aqui un orden de instalacion que el lock ya decidio.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Las dependencias primero y el codigo despues. Es el orden que hace util la
# cache de capas: cambiar una linea de un servicio no reinstala nada.
COPY pyproject.toml ./
COPY libs/py/tukit_comun/pyproject.toml libs/py/tukit_comun/
COPY servicios/identidad/pyproject.toml servicios/identidad/
COPY servicios/catalogo/pyproject.toml servicios/catalogo/
COPY servicios/inteligencia/pyproject.toml servicios/inteligencia/
COPY servicios/gateway/pyproject.toml servicios/gateway/

COPY libs/ libs/
COPY servicios/ servicios/
COPY datos/ datos/
COPY arquitectura/ arquitectura/

RUN uv pip install --system --no-cache \
    "sqlalchemy>=2.0" "pydantic>=2.9" "pydantic-settings>=2.5" "pgvector>=0.3" \
    "asyncpg>=0.29" "alembic>=1.13" \
    "fastapi>=0.115" "uvicorn[standard]>=0.30" "httpx>=0.27"

# Los cuatro paquetes se resuelven por ruta y no instalados, que es como
# tambien corren las pruebas. Asi el contenedor ejecuta EXACTAMENTE el mismo
# arbol que la maquina de quien lo escribio.
ENV PYTHONPATH=/app/libs/py/tukit_comun:/app/servicios/identidad:/app/servicios/catalogo:/app/servicios/inteligencia:/app/servicios/gateway
ENV PYTHONUNBUFFERED=1

# Lo sobreescribe cada servicio en el compose. Sin valor por omision util, un
# `docker run` sin argumentos no diria que falta.
CMD ["python", "-c", "import sys; sys.exit('Elige un servicio: python -m tukit_<servicio>.api')"]
