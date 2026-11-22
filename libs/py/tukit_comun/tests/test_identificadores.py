from __future__ import annotations

import uuid

from tukit_comun.cifrado import CifradorEnClaro, cifrador_desde_entorno
from tukit_comun.identificadores import derivar


class TestLaMismaLlaveDaElMismoIdentificador:
    def test_dos_servicios_llegan_al_mismo_uuid_sin_coordinarse(self):
        assert derivar("colegio", "2.4") == derivar("colegio", "2.4")

    def test_llaves_distintas_no_colisionan(self):
        assert derivar("colegio", "2.4") != derivar("colegio", "2.5")
        assert derivar("colegio", "2.4") != derivar("sede", "2.4")

    def test_es_un_uuid_version_5(self):
        assert derivar("colegio", "2.4").version == 5

    def test_el_valor_es_el_que_ya_esta_en_la_base(self):
        esperado = uuid.uuid5(uuid.NAMESPACE_URL, "tukit:colegio:2.4")
        assert derivar("colegio", "2.4") == esperado

    def test_acepta_varias_partes(self):
        assert derivar("lista", "2.4", "Cuarto", "2026") == uuid.uuid5(
            uuid.NAMESPACE_URL, "tukit:lista:2.4:Cuarto:2026"
        )


class TestElCifradoNoMiente:
    def test_el_adaptador_por_omision_dice_que_no_cifra(self):
        cifrador = CifradorEnClaro()
        assert cifrador.nombre == "en_claro"
        assert cifrador.cifra_de_verdad is False
        assert cifrador.cifrar(b"pesos").startswith(b"claro:")

    def test_lo_que_entra_vuelve_a_salir_igual(self):
        cifrador = CifradorEnClaro()
        pesos = {"precio": 0.35, "calidad": 0.25}
        assert cifrador.descifrar_json(cifrador.cifrar_json(pesos)) == pesos

    def test_descifrar_nada_es_nada_y_no_un_error(self):
        assert CifradorEnClaro().descifrar_json(None) is None

    def test_sin_llave_en_el_entorno_cae_al_adaptador_que_avisa(self, monkeypatch):
        monkeypatch.delenv("TUKIT_LLAVE_CIFRADO", raising=False)
        assert cifrador_desde_entorno().nombre == "en_claro"

    def test_una_llave_mal_formada_degrada_en_vez_de_tumbar(self, monkeypatch, capsys):
        monkeypatch.setenv("TUKIT_LLAVE_CIFRADO", "esto-no-es-una-llave")
        cifrador = cifrador_desde_entorno()
        assert cifrador.nombre == "en_claro"
        assert "EN CLARO" in capsys.readouterr().out
