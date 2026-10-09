"""NFR-MAN-01: firma, expiracion y falla cerrada del token de sesion de Identidad.

`dominio/sesiones.py` es el dominio que decide si una peticion trae sesion: el
token es `base64url(payload).firma` (HMAC-SHA256) y el gateway lo comprueba sin
importar codigo de Identidad, asi que el FORMATO es un contrato. Las pruebas
existentes fijan la ida y vuelta feliz; aqui se fija lo que las hace confiables:

- el payload lleva solo `sub`, `vp` y `exp` (ni correo ni roles) y la vigencia
  se mide con un reloj INYECTADO, nunca con el de la maquina;
- un token alterado (payload, firma, llave distinta, forma rara) se rechaza
  devolviendo `None`, sin lanzar: es la promesa "falla CERRADA" del docstring;
- las firmas se recalculan en la prueba con `hmac` de la stdlib, de forma
  independiente, para que la prueba no valide el codigo con el propio codigo;
- el hash de clave PBKDF2 solo valida contra su propio formato.

Un token con caracteres no ASCII hoy LANZA en vez de devolver `None`
(`sesiones.py:150-151`); esa prueba va marcada como defecto conocido.

Sobre la llave por defecto (H-C-06): sin `TUKIT_LLAVE_SESION` el modulo firma
con `_LLAVE_DESARROLLO`, una cadena publica en el repositorio, y solo avisa con
un `print` a la salida estandar en cada firma/lectura. Quien despliegue sin la
variable no obtiene ningun error: cualquiera puede acunar tokens validos. La
prueba de abajo caracteriza esa conducta (avisa y funciona); que ademas avise
AL ARRANCAR, como promete el docstring, se prueba en `test_identidad_api_arranque`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import types
import uuid

import pytest
from tukit_identidad.dominio import sesiones
from tukit_identidad.dominio.sesiones import (
    VIDA_SEGUNDOS,
    emitir_token,
    hashear_clave,
    leer_token,
    verificar_clave,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

LLAVE_PRUEBA = "llave-ficticia-de-prueba-identidad"
INICIO = 1_000_000.0


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _firmar_cuerpo(cuerpo: str, llave: str = LLAVE_PRUEBA) -> str:
    """Firma un cuerpo ya codificado, con HMAC-SHA256 de la stdlib."""
    firma = hmac.new(llave.encode("utf-8"), cuerpo.encode("ascii"), hashlib.sha256).digest()
    return f"{cuerpo}.{_b64(firma)}"


def _forjar(crudo: bytes, llave: str = LLAVE_PRUEBA) -> str:
    """Un token con firma VALIDA sobre un cuerpo arbitrario (para probar que la
    firma sola no basta: el contenido tambien tiene que tener forma)."""
    return _firmar_cuerpo(_b64(crudo), llave)


def _payload(token: str) -> dict:
    cuerpo = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)))


@pytest.fixture(autouse=True)
def _llave_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    """Una llave propia: las pruebas no dependen del entorno ni usan la de desarrollo."""
    monkeypatch.setenv(sesiones.VARIABLE_LLAVE, LLAVE_PRUEBA)


def _reloj_fijo(monkeypatch: pytest.MonkeyPatch, ahora: float) -> None:
    """Sustituye SOLO el `time` visto por `sesiones`; el reloj global no se toca."""
    monkeypatch.setattr(sesiones, "time", types.SimpleNamespace(time=lambda: ahora))


class TestFormatoDelToken:
    def test_el_payload_lleva_solo_sub_vp_y_exp(self):
        """Contrato con el gateway: lo justo para revocar y caducar. Ni el
        correo ni un rol viajan en el token, porque se quedarian viejos."""
        uid = uuid.uuid4()
        token = emitir_token(uid, version_permisos=7, ahora=INICIO)

        assert _payload(token) == {"sub": str(uid), "vp": 7, "exp": int(INICIO) + VIDA_SEGUNDOS}

    def test_la_firma_es_hmac_sha256_del_cuerpo_con_la_llave_del_entorno(self):
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)
        cuerpo, firma = token.split(".")

        assert firma
        assert token == _firmar_cuerpo(cuerpo)
        # base64url sin relleno: el token cabe en una cabecera sin escapar nada.
        assert "=" not in token
        assert "+" not in token
        assert "/" not in token

    def test_la_vida_del_token_son_ocho_horas(self):
        assert VIDA_SEGUNDOS == 8 * 60 * 60


class TestExpiracionConRelojInyectado:
    def test_vale_hasta_que_vence_y_deja_de_valer_despues(self):
        uid = uuid.uuid4()
        token = emitir_token(uid, version_permisos=3, ahora=INICIO)
        vence = INICIO + VIDA_SEGUNDOS

        assert leer_token(token, ahora=INICIO) is not None
        assert leer_token(token, ahora=vence - 1) == {"sub": str(uid), "vp": 3, "exp": int(vence)}
        assert leer_token(token, ahora=vence + 1) is None

    def test_sin_reloj_inyectado_lee_la_hora_actual_de_sesiones(self, monkeypatch: pytest.MonkeyPatch):
        """Con `ahora=None` el modulo consulta `time.time()`: se sustituye ese
        reloj (y solo ese) para fijar la hora, tanto al emitir como al leer."""
        _reloj_fijo(monkeypatch, 5_000.0)
        token = emitir_token(uuid.uuid4(), version_permisos=1)
        assert _payload(token)["exp"] == 5_000 + VIDA_SEGUNDOS

        _reloj_fijo(monkeypatch, 5_000.0 + VIDA_SEGUNDOS - 1)
        assert leer_token(token) is not None
        _reloj_fijo(monkeypatch, 5_000.0 + VIDA_SEGUNDOS + 1)
        assert leer_token(token) is None

    def test_un_token_emitido_en_1970_ya_vencio_para_el_reloj_real(self):
        """Prueba que `ahora` es del llamador y que sin el la hora real manda:
        un token con `exp` en 1970 no puede seguir vigente."""
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=0.0)
        assert leer_token(token) is None


class TestTokenAlteradoSeRechaza:
    def test_cambiar_la_version_de_permisos_sin_refirmar_invalida_el_token(self):
        """El atacante sube `vp` o extiende `exp` editando el cuerpo y deja la
        firma original: la firma ya no cuadra con el cuerpo."""
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)
        cuerpo, firma = token.split(".")
        editado = {**_payload(token), "vp": 99, "exp": int(INICIO) + 10**9}
        cuerpo_editado = _b64(json.dumps(editado, separators=(",", ":")).encode("utf-8"))

        assert leer_token(f"{cuerpo_editado}.{firma}", ahora=INICIO) is None
        # El original sigue valiendo: el rechazo es por la alteracion, no por el reloj.
        assert leer_token(f"{cuerpo}.{firma}", ahora=INICIO) is not None

    def test_la_firma_de_otro_token_no_se_puede_trasplantar(self):
        a = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)
        b = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)

        cuerpo_a = a.split(".")[0]
        firma_b = b.split(".")[1]
        assert leer_token(f"{cuerpo_a}.{firma_b}", ahora=INICIO) is None

    @pytest.mark.parametrize("firma", ["", "AAAA", "firmafalsa"])
    def test_una_firma_vacia_corta_o_falsa_no_vale(self, firma: str):
        cuerpo = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO).split(".")[0]
        assert leer_token(f"{cuerpo}.{firma}", ahora=INICIO) is None

    def test_un_token_firmado_con_otra_llave_no_vale_y_rotar_la_llave_revoca_todo(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Cambiar `TUKIT_LLAVE_SESION` es la palanca de emergencia: todos los
        tokens emitidos con la llave anterior dejan de valer de golpe."""
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)
        assert leer_token(token, ahora=INICIO) is not None

        monkeypatch.setenv(sesiones.VARIABLE_LLAVE, "otra-llave-ficticia")
        assert leer_token(token, ahora=INICIO) is None

    @pytest.mark.parametrize("token", ["", "sin-punto", "a.b.c", "....", ".", "cuerpo."])
    def test_una_forma_rara_devuelve_none_en_vez_de_lanzar(self, token: str):
        assert leer_token(token, ahora=INICIO) is None


class TestContenidoFirmadoPeroMalFormado:
    """La firma valida no vuelve bueno un contenido que no es un payload: quien
    llama debe seguir recibiendo `None` (falla cerrada), no una excepcion."""

    def test_un_cuerpo_que_no_es_json_se_rechaza(self):
        assert leer_token(_forjar(b"esto no es json"), ahora=INICIO) is None

    def test_un_cuerpo_con_bytes_que_no_son_utf8_se_rechaza(self):
        assert leer_token(_forjar(b"\xff\xfe\x00"), ahora=INICIO) is None

    def test_un_cuerpo_que_no_es_base64_se_rechaza(self):
        assert leer_token(_firmar_cuerpo("%%%"), ahora=INICIO) is None

    @pytest.mark.parametrize("crudo", [b"[1,2,3]", b"null", b'"texto"', b"42"])
    def test_un_json_que_no_es_un_objeto_se_rechaza(self, crudo: bytes):
        assert leer_token(_forjar(crudo), ahora=INICIO) is None

    def test_un_objeto_sin_exp_se_rechaza(self):
        """Sin `exp` el token no caducaria nunca: se trata como invalido."""
        crudo = json.dumps({"sub": str(uuid.uuid4()), "vp": 1}).encode("utf-8")
        assert leer_token(_forjar(crudo), ahora=INICIO) is None

    def test_un_objeto_con_exp_futuro_y_firma_valida_se_acepta(self):
        """El contrapeso de las anteriores: lo unico que cambia es la forma."""
        sub = str(uuid.uuid4())
        crudo = json.dumps({"sub": sub, "vp": 2, "exp": INICIO + 60}).encode("utf-8")
        assert leer_token(_forjar(crudo), ahora=INICIO) == {"sub": sub, "vp": 2, "exp": INICIO + 60}


class TestTokenNoAscii:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            "H-A-17: leer_token lanza UnicodeEncodeError/TypeError con un token no ASCII en vez "
            "de devolver None (sesiones.py:150-151, fuera del try); via HTTP es un 500 en lugar de 401"
        ),
    )
    @pytest.mark.parametrize("token", ["é.firma", "cuerpo.fírma", "ñ.ñ"])
    def test_un_token_con_caracteres_no_ascii_se_rechaza_sin_lanzar(self, token: str):
        """El docstring promete que un token de forma rara NO lanza. La
        cabecera `Authorization` la controla quien llama (llega decodificada en
        latin-1), asi que es entrada hostil alcanzable sin credenciales."""
        assert leer_token(token, ahora=INICIO) is None


class TestLlaveDeDesarrollo:
    """H-C-06 (llave de sesion por defecto): sin la variable el modulo NO falla."""

    def test_sin_llave_configurada_firma_con_la_publica_y_lo_dice_por_stdout(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        monkeypatch.delenv(sesiones.VARIABLE_LLAVE)
        uid = uuid.uuid4()

        token = emitir_token(uid, version_permisos=1, ahora=INICIO)
        salida = capsys.readouterr().out

        assert sesiones.VARIABLE_LLAVE in salida
        assert "DESARROLLO" in salida
        # Firmado con la llave publica del repositorio: cualquiera la conoce.
        cuerpo = token.split(".")[0]
        assert token == _firmar_cuerpo(cuerpo, llave=sesiones._LLAVE_DESARROLLO)

    def test_con_la_variable_vacia_o_en_blanco_se_trata_como_ausente(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        monkeypatch.setenv(sesiones.VARIABLE_LLAVE, "   ")
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)

        assert "DESARROLLO" in capsys.readouterr().out
        assert token == _firmar_cuerpo(token.split(".")[0], llave=sesiones._LLAVE_DESARROLLO)

    def test_un_token_acunado_con_la_llave_publica_es_aceptado_si_falta_la_configuracion(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Es lo que hace peligroso el despliegue sin variable: no hay ningun
        error, y quien conozca el repositorio puede entrar como cualquier id."""
        monkeypatch.delenv(sesiones.VARIABLE_LLAVE)
        sub = str(uuid.uuid4())
        crudo = json.dumps({"sub": sub, "vp": 1, "exp": INICIO + 60}).encode("utf-8")

        falso = _forjar(crudo, llave=sesiones._LLAVE_DESARROLLO)

        assert leer_token(falso, ahora=INICIO) == {"sub": sub, "vp": 1, "exp": INICIO + 60}

    def test_con_la_llave_configurada_el_token_de_la_llave_publica_no_vale(self):
        crudo = json.dumps({"sub": str(uuid.uuid4()), "vp": 1, "exp": INICIO + 60}).encode("utf-8")
        falso = _forjar(crudo, llave=sesiones._LLAVE_DESARROLLO)

        assert leer_token(falso, ahora=INICIO) is None

    def test_con_la_llave_configurada_no_imprime_ningun_aviso(self, capsys: pytest.CaptureFixture[str]):
        token = emitir_token(uuid.uuid4(), version_permisos=1, ahora=INICIO)
        leer_token(token, ahora=INICIO)

        assert capsys.readouterr().out == ""


class TestHashDeClaveSoloValidaSuFormato:
    def test_el_hash_es_pbkdf2_con_sal_de_16_bytes_y_derivado_de_32(self):
        algoritmo, iteraciones, sal, derivado = hashear_clave("clave-ficticia-1").split("$")

        assert algoritmo == "pbkdf2_sha256"
        assert int(iteraciones) == 240_000
        assert len(base64.b64decode(sal)) == 16
        assert len(base64.b64decode(derivado)) == 32

    def test_el_derivado_coincide_con_pbkdf2_de_la_stdlib(self):
        _, iteraciones, sal, derivado = hashear_clave("clave-ficticia-2").split("$")
        esperado = hashlib.pbkdf2_hmac("sha256", b"clave-ficticia-2", base64.b64decode(sal), int(iteraciones))
        assert base64.b64decode(derivado) == esperado

    def test_una_clave_con_acentos_y_enie_ida_y_vuelta(self):
        guardado = hashear_clave("contraseña-ñandú")
        assert verificar_clave("contraseña-ñandú", guardado) is True
        assert verificar_clave("contrasena-nandu", guardado) is False

    def test_un_algoritmo_distinto_no_valida_aunque_el_derivado_coincida(self):
        """El prefijo manda: un hash etiquetado con otro algoritmo no se compara."""
        _, iteraciones, sal, derivado = hashear_clave("clave-ficticia-3").split("$")
        ajeno = "$".join(["pbkdf2_sha1", iteraciones, sal, derivado])

        assert verificar_clave("clave-ficticia-3", ajeno) is False

    @pytest.mark.parametrize(
        "guardado",
        [
            "pbkdf2_sha256$no-es-un-numero$c2Fs$aGFzaA==",
            "pbkdf2_sha256$240000$@@@$@@@",
            "pbkdf2_sha256$240000$c2Fs$a",
            "a$b$c$d$e",
            "",
        ],
    )
    def test_un_hash_corrupto_se_rechaza_sin_lanzar(self, guardado: str):
        assert verificar_clave("clave-ficticia-4", guardado) is False
