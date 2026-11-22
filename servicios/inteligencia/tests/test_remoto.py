from __future__ import annotations

import httpx
import pytest
from tukit_inteligencia.remoto import ClienteIdentidad, RemotoCaido


def _cliente(manejador) -> ClienteIdentidad:
    http = httpx.AsyncClient(transport=httpx.MockTransport(manejador))
    return ClienteIdentidad(base="http://identidad", cliente=http)


async def test_tiene_credencial_responde_el_booleano_de_identidad():
    cliente = _cliente(lambda _p: httpx.Response(200, json={"tiene_credencial": True}))
    assert await cliente.tiene_credencial("u-1") is True


async def test_tiene_credencial_con_un_404_es_remoto_caido_con_la_causa_en_el_mensaje():
    cliente = _cliente(lambda _p: httpx.Response(404, json={"detail": "Not Found"}))
    with pytest.raises(RemotoCaido) as error:
        await cliente.tiene_credencial("u-1")
    assert "reiniciala" in str(error.value)
