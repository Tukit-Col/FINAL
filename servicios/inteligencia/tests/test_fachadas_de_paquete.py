import importlib
import pkgutil

import pytest

PAQUETES = ["tukit_inteligencia.optimizador", "tukit_inteligencia.trabajos"]


def _submodulos(paquete):
    return [
        importlib.import_module(f"{paquete.__name__}.{m.name}")
        for m in pkgutil.iter_modules(paquete.__path__)
    ]


@pytest.mark.parametrize("nombre", PAQUETES)
def test_cada_nombre_de_all_es_el_objeto_de_un_submodulo(nombre):
    paquete = importlib.import_module(nombre)
    submodulos = _submodulos(paquete)
    assert paquete.__all__
    for n in paquete.__all__:
        assert any(getattr(s, n, None) is getattr(paquete, n) for s in submodulos), n
