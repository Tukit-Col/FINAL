"""El dominio de Operacion: las reglas del caso, como calculo puro.

Nada aqui importa FastAPI, SQLAlchemy ni httpx (ADR 0019, la regla de
dependencia apunta hacia adentro). Son funciones y dataclasses que reciben datos
planos —una categoria en texto, una prioridad, un instante— y devuelven datos
planos o una decision tipada. Las tablas de verdad (SLA, prioridad, orden,
categorias del acudiente) viven en `modelos/base.py` y se reusan desde aqui: no
se duplican, para no partir en dos la fuente de esas reglas.

Operacion NO declara un puerto de repositorio: como en Comercio, sus reglas son
calculo puro y no llaman a la base, asi que un Protocol con una sola
implementacion seria una indireccion sin uso.
"""
