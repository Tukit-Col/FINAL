"""Adaptadores de salida a la propia base de Comercio: el SQL, y nada más.

La otra mitad de la ADR 0019: si `dominio/` es el qué-decide-el-negocio libre
de framework, `repositorios/` es el cómo-se-guarda. Aquí vive todo el SQLAlchemy
Core que antes estaba embebido en los manejadores de `api.py` —los `insert` del
checkout, las lecturas del tablero, los serializadores de proyección—. El router
abre la sesión, construye el repo atado a esa conexión y le delega la
persistencia; el repo no conoce FastAPI ni HTTP.

No hay un `Protocol` de repositorio: es una sola implementación (SQL contra la
base del servicio) que las pruebas ejercen contra SQLite real, no un doble. Un
puerto con una única implementación jamás sustituida sería indirección sin uso
(ADR 0019, y la regla de no abstraer de más). El puerto que sí gana su sitio es
`PasarelaPago`, que tiene dos adaptadores.
"""

from .pedidos import RepoPedidos

__all__ = ["RepoPedidos"]
