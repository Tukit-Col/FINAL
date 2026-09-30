"""El dominio puro de Comercio: reglas de negocio sin framework ni base.

Nada aquí importa FastAPI, SQLAlchemy ni httpx (ADR 0019, la regla de
dependencia apunta hacia adentro). Son `dataclass` y funciones que reciben
datos planos y devuelven datos planos, de modo que las invariantes más caras
del §9 —re-verificar el precio (FU-08), decidir el estado tras el pago— se
prueban con una lista y un `assert`, sin red ni Postgres.

El router (`api.py`) resuelve el I/O —lee Catálogo, abre la sesión— y le pasa
al dominio estructuras ya materializadas; el dominio decide y el router
persiste. Comercio NO declara un puerto de repositorio: sus reglas son cálculo
puro y no llaman a la base, así que un `Protocol` con una sola implementación
sería una indirección sin uso. El único puerto del servicio es `PasarelaPago`
(`pasarela.py`), que sí tiene dos adaptadores.
"""
