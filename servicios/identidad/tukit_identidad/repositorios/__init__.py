"""El SQL de Identidad contra su propia base, detras de nombres de metodo.

No hay un Protocol de repositorio: es una sola implementacion (`RepoIdentidad`)
que las pruebas ejercen contra SQLite real, no un doble. El router (o, en el
caso de autorizacion, quien necesite resolver un permiso) abre la sesion y le
pide cada paso; el repo no decide negocio ni conoce HTTP (ADR 0019).
"""

from .identidad import RepoIdentidad

__all__ = ["RepoIdentidad"]
