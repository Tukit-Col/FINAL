"""`Ambito` como dataclass puro: fija el contrato antes de moverlo a dominio/."""

from __future__ import annotations

import uuid

import pytest
from tukit_identidad.dominio.autorizacion import Ambito
from tukit_identidad.modelos import AmbitoTipo


def test_ambito_global_no_lleva_id():
    assert Ambito.global_() == Ambito(AmbitoTipo.GLOBAL, None)


def test_ambito_colegio_lleva_su_id():
    cid = uuid.uuid4()
    assert Ambito.colegio(cid) == Ambito(AmbitoTipo.COLEGIO, cid)


@pytest.mark.parametrize(
    ("tipo", "con_id"),
    [
        (AmbitoTipo.GLOBAL, True),
        (AmbitoTipo.COLEGIO, False),
        (AmbitoTipo.SEDE, False),
        (AmbitoTipo.MATRICULA, False),
    ],
)
def test_un_ambito_incoherente_con_su_identificador_es_un_error(tipo, con_id):
    """El global no lleva id; todo ambito no global lo exige."""
    with pytest.raises(ValueError, match="incoherente"):
        Ambito(tipo, uuid.uuid4() if con_id else None)
