"""El dominio puro de Identidad: reglas sin FastAPI, sin SQLAlchemy, sin HTTP.

Nada aqui hace una consulta ni conoce una peticion (ADR 0019, la regla de
dependencia apunta hacia adentro): son `dataclass` y funciones que reciben
datos planos y devuelven datos planos. El hasheo de clave y la firma de
tokens (`sesiones.py`), el ambito sobre el que se pregunta un permiso
(`autorizacion.py`) y el lookup del directorio DUEB (`directorio.py`) viven
aqui porque ninguno necesita la base para responder. Las consultas que SI
tocan la base (`puede`, `roles_vigentes`, `campos_visibles`,
`matriculas_visibles`) viven en `repositorios/identidad.py`.
"""
