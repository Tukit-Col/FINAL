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


def test_ambito_global_con_id_es_incoherente():
    with pytest.raises(ValueError, match="incoherente"):
        Ambito(AmbitoTipo.GLOBAL, uuid.uuid4())


def test_ambito_no_global_sin_id_es_incoherente():
    with pytest.raises(ValueError, match="incoherente"):
        Ambito(AmbitoTipo.SEDE, None)
