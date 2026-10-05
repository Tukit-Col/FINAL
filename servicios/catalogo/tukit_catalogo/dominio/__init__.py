"""El dominio puro de Catalogo: reglas sin FastAPI, sin SQLAlchemy, sin HTTP.

Nada aqui hace una consulta ni conoce una peticion (ADR 0019, la regla de
dependencia apunta hacia adentro): son funciones que reciben datos planos (una
`fila` cuyos campos se leen por atributo, un dict de cambios) y devuelven datos
planos o levantan `ErrorDominio`. Los shapers de la respuesta publica, el orden
de las ofertas y la validacion de una edicion viven aqui porque ninguno necesita
la base para responder. El SQL que las alimenta vive en `repositorios/`.
"""
