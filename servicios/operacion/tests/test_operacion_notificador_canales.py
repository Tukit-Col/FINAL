"""NFR-MAN-01: los canales del puerto `Notificador` (wa-link, correo, falso, compuesto) y sus plantillas.

El repartidor depende del puerto, no de SMTP ni de wa.me. Aqui se fija lo que
cada adaptador promete: wa-link arma un enlace con el numero limpio y el texto
codificado (o falla sin celular), el correo imprime a consola cuando no hay
servidor y habla SMTP en un hilo cuando lo hay (con un `smtplib.SMTP` de mentira:
ninguna conexion real), el falso solo anota, y el compuesto elige canal y cae a
correo. Las plantillas rellenan variables de negocio y no revientan por una clave
nueva ni por una variable ausente.

Importa porque es lo ultimo que toca el aviso antes de salir hacia una persona: un
fallo de envio tiene que volver como `Envio(exito=False)` para que el repartidor
reintente (no como excepcion, que aborta toda la pasada), y el dato de contacto no
puede filtrarse al texto, a la consola ni al detalle de un error. Los contactos
son ficticios.
"""

from __future__ import annotations

import smtplib
import threading
import urllib.parse
from types import SimpleNamespace
from typing import Any

import pytest
from tukit_operacion import notificador
from tukit_operacion.notificador import (
    Contacto,
    Correo,
    Envio,
    NotificadorCompuesto,
    NotificadorFalso,
    WaLink,
    notificador_desde_entorno,
    texto_de,
)

pytestmark = pytest.mark.nfr("NFR-MAN-01")

USUARIO = "22222222-2222-5222-8222-222222222222"
CORREO = "acudiente.ficticio@example.test"
CELULAR = "3000000000"
DATOS = {"turno": "AB12CD34", "pedido": "99FF00AA", "enlace": "https://tukit.example.test/kits/abc"}


@pytest.fixture(autouse=True)
def _sin_smtp_en_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    for nombre in ("HOST", "PORT", "USER", "PASSWORD", "DESDE"):
        monkeypatch.delenv(f"TUKIT_SMTP_{nombre}", raising=False)


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Un `smtplib.SMTP` de mentira que anota cada paso. `registro.falla` elige donde se cae."""
    registro = SimpleNamespace(conexiones=[], falla=None)

    class SMTPFalso:
        def __init__(self, host: str, puerto: int, timeout: float | None = None) -> None:
            if registro.falla == "conectar":
                raise ConnectionRefusedError("conexion rechazada")
            self.host, self.puerto, self.timeout = host, puerto, timeout
            self.hilo = threading.get_ident()
            self.pasos: list[str] = []
            self.credenciales: tuple[str, str] | None = None
            self.mensaje: Any = None
            registro.conexiones.append(self)

        def __enter__(self) -> SMTPFalso:
            return self

        def __exit__(self, *args: object) -> bool:
            self.pasos.append("cerrar")
            return False

        def starttls(self) -> None:
            self.pasos.append("starttls")

        def login(self, usuario: str, clave: str) -> None:
            self.pasos.append("login")
            if registro.falla == "login":
                raise smtplib.SMTPAuthenticationError(535, b"credenciales rechazadas")
            self.credenciales = (usuario, clave)

        def send_message(self, mensaje: Any) -> None:
            self.pasos.append("enviar")
            if registro.falla == "enviar":
                raise smtplib.SMTPRecipientsRefused({})
            self.mensaje = mensaje

    monkeypatch.setattr(notificador.smtplib, "SMTP", SMTPFalso)
    return registro


class TestLasPlantillas:
    def test_rellena_las_variables_de_negocio(self):
        assert texto_de("pedido_pagado", DATOS) == (
            "Recibimos tu pago del pedido 99FF00AA. Turno AB12CD34. Te avisamos cuando salga."
        )

    def test_kits_publicados_lleva_el_enlace_de_precompra(self):
        texto = texto_de("kits_publicados", DATOS)

        assert "Turno AB12CD34" in texto
        assert texto.endswith("https://tukit.example.test/kits/abc")

    def test_una_variable_ausente_deja_la_plantilla_sin_rellenar_en_vez_de_reventar(self):
        texto = texto_de("pedido_pagado", {"turno": "AB12CD34"})  # falta `pedido`

        assert texto == "Recibimos tu pago del pedido {pedido}. Turno {turno}. Te avisamos cuando salga."

    def test_una_plantilla_sin_registrar_cae_al_texto_generico(self):
        assert texto_de("plantilla_nueva", DATOS) == "Tienes una novedad en Tukit. Turno AB12CD34."

    def test_las_llaves_dentro_de_un_valor_no_se_interpretan_como_plantilla(self):
        """Un dato con `{turno}` literal sale tal cual: el texto no se formatea dos veces."""
        texto = texto_de("pedido_pagado", {"pedido": "{turno}", "turno": "AB12CD34"})

        assert texto.startswith("Recibimos tu pago del pedido {turno}. Turno AB12CD34.")


class TestWaLink:
    @pytest.mark.parametrize("celular", [None, ""], ids=["nulo", "vacio"])
    async def test_sin_celular_es_un_fallo_de_envio_no_una_excepcion(self, celular):
        envio = await WaLink().enviar(Contacto(USUARIO, celular=celular), "pedido_pagado", DATOS)

        assert envio == Envio(canal="wa_link", exito=False, detalle="sin_celular")

    async def test_el_numero_se_limpia_a_solo_digitos(self):
        envio = await WaLink().enviar(Contacto(USUARIO, celular="+57 (300) 000-0000"), "pedido_pagado", DATOS)

        assert envio.exito is True
        assert envio.canal == "wa_link"
        assert envio.enlace is not None
        assert envio.enlace.startswith("https://wa.me/573000000000?text=")

    async def test_el_mensaje_va_codificado_y_no_rompe_el_enlace(self):
        datos = {"turno": "T1", "pedido": "A&b=c#d?e f\nlinea"}

        envio = await WaLink().enviar(Contacto(USUARIO, celular=CELULAR), "pedido_pagado", datos)

        assert envio.enlace is not None
        consulta = envio.enlace.split("?text=", 1)[1]
        assert not set(consulta) & set("&#? \n=")  # nada que corte o reabra la consulta
        assert urllib.parse.unquote(consulta) == texto_de("pedido_pagado", datos)

    async def test_el_enlace_no_lleva_el_correo(self):
        envio = await WaLink().enviar(
            Contacto(USUARIO, correo=CORREO, celular=CELULAR), "kits_publicados", DATOS
        )

        assert CORREO not in (envio.enlace or "")
        assert urllib.parse.quote(CORREO) not in (envio.enlace or "")


class TestCorreoSinServidor:
    async def test_sin_correo_es_un_fallo_de_envio_y_no_toca_a_nadie(self, smtp, capsys):
        envio = await Correo().enviar(Contacto(USUARIO, celular=CELULAR), "pedido_pagado", DATOS)

        assert envio == Envio(canal="correo", exito=False, detalle="sin_correo")
        assert smtp.conexiones == []
        assert capsys.readouterr().out == ""

    async def test_sin_host_imprime_a_consola_el_usuario_y_el_texto_pero_no_el_correo(self, smtp, capsys):
        envio = await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        salida = capsys.readouterr().out
        assert envio == Envio(canal="correo", exito=True, detalle="consola")
        assert salida == f"[correo:consola] -> usuario {USUARIO}: {texto_de('pedido_pagado', DATOS)}\n"
        assert CORREO not in salida  # el log nunca lleva el dato de contacto
        assert smtp.conexiones == []  # modo consola: no se finge un servidor

    async def test_un_host_vacio_cuenta_como_ausente(self, smtp, monkeypatch, capsys):
        monkeypatch.setenv("TUKIT_SMTP_HOST", "")

        envio = await Correo().enviar(Contacto(USUARIO, correo=CORREO), "incidencia", DATOS)

        assert envio.detalle == "consola"
        assert smtp.conexiones == []
        assert "[correo:consola]" in capsys.readouterr().out


class TestCorreoPorSmtp:
    @pytest.fixture(autouse=True)
    def _host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TUKIT_SMTP_HOST", "smtp.example.test")

    async def test_conecta_con_starttls_y_envia_el_mensaje_armado(self, smtp):
        envio = await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        (conexion,) = smtp.conexiones
        assert envio == Envio(canal="correo", exito=True, detalle="smtp")
        assert (conexion.host, conexion.puerto, conexion.timeout) == ("smtp.example.test", 587, 30)
        assert conexion.pasos == ["starttls", "enviar", "cerrar"]  # sin credenciales: no hay login
        mensaje = conexion.mensaje
        assert mensaje["To"] == CORREO
        assert mensaje["From"] == "no-responder@tukit.co"
        assert mensaje["Subject"] == "Novedad en Tukit"
        assert mensaje.get_content().strip() == texto_de("pedido_pagado", DATOS)

    async def test_el_envio_bloqueante_corre_en_otro_hilo_para_no_congelar_el_bucle(self, smtp):
        await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        assert smtp.conexiones[0].hilo != threading.get_ident()

    async def test_el_puerto_sale_del_entorno(self, smtp, monkeypatch):
        monkeypatch.setenv("TUKIT_SMTP_PORT", "2525")

        await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        assert smtp.conexiones[0].puerto == 2525

    async def test_con_usuario_y_clave_inicia_sesion_despues_de_cifrar_el_canal(self, smtp, monkeypatch):
        monkeypatch.setenv("TUKIT_SMTP_USER", "usuario_ficticio")
        monkeypatch.setenv("TUKIT_SMTP_PASSWORD", "clave_ficticia")

        await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        (conexion,) = smtp.conexiones
        assert conexion.pasos == ["starttls", "login", "enviar", "cerrar"]
        assert conexion.credenciales == ("usuario_ficticio", "clave_ficticia")

    @pytest.mark.parametrize(
        ("usuario", "clave"),
        [("usuario_ficticio", None), (None, "clave_ficticia")],
        ids=["solo-usuario", "solo-clave"],
    )
    async def test_credenciales_a_medias_no_inician_sesion(self, smtp, monkeypatch, usuario, clave):
        if usuario:
            monkeypatch.setenv("TUKIT_SMTP_USER", usuario)
        if clave:
            monkeypatch.setenv("TUKIT_SMTP_PASSWORD", clave)

        envio = await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        assert envio.exito is True
        assert "login" not in smtp.conexiones[0].pasos

    async def test_el_remitente_del_objeto_gana_sobre_el_del_entorno(self, smtp, monkeypatch):
        monkeypatch.setenv("TUKIT_SMTP_DESDE", "entorno@example.test")

        await Correo(remitente="avisos@example.test").enviar(
            Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS
        )
        await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        assert [c.mensaje["From"] for c in smtp.conexiones] == ["avisos@example.test", "entorno@example.test"]

    @pytest.mark.parametrize("falla", ["conectar", "login", "enviar"])
    async def test_un_fallo_de_smtp_vuelve_como_envio_fallido_para_que_el_repartidor_reintente(
        self, smtp, monkeypatch, falla
    ):
        monkeypatch.setenv("TUKIT_SMTP_USER", "usuario_ficticio")
        monkeypatch.setenv("TUKIT_SMTP_PASSWORD", "clave_ficticia")
        smtp.falla = falla

        envio = await Correo().enviar(Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS)

        assert envio.canal == "correo"
        assert envio.exito is False
        assert envio.detalle is not None
        assert envio.detalle.startswith("smtp_error: ")
        assert "clave_ficticia" not in envio.detalle  # el detalle del error no filtra la credencial


class TestNotificadorFalso:
    async def test_anota_lo_enviado_sin_el_contacto_y_responde_exito(self):
        falso = NotificadorFalso()

        envio = await falso.enviar(Contacto(USUARIO, correo=CORREO, celular=CELULAR), "pedido_pagado", DATOS)

        assert envio == Envio(canal="correo", exito=True)
        assert falso.enviados == [
            {
                "usuario_id": USUARIO,
                "plantilla": "pedido_pagado",
                "canal": "correo",
                "texto": texto_de("pedido_pagado", DATOS),
            }
        ]
        assert CORREO not in str(falso.enviados)
        assert CELULAR not in str(falso.enviados)

    async def test_el_canal_que_finge_es_configurable(self):
        falso = NotificadorFalso(canal="wa_link")

        envio = await falso.enviar(Contacto(USUARIO), "incidencia", DATOS)

        assert envio.canal == "wa_link"
        assert falso.enviados[0]["canal"] == "wa_link"

    def test_dos_instancias_no_comparten_la_lista_de_enviados(self):
        assert NotificadorFalso().enviados is not NotificadorFalso().enviados


class _Canal:
    """Un canal de mentira con respuesta fija que anota a quien le llegaron envios."""

    def __init__(self, envio: Envio) -> None:
        self.envio = envio
        self.contactos: list[Contacto] = []

    async def enviar(self, contacto: Contacto, plantilla: str, datos: dict[str, object]) -> Envio:
        self.contactos.append(contacto)
        return self.envio


WA_OK = Envio(canal="wa_link", exito=True, enlace="https://wa.me/573000000000?text=x")
WA_FALLA = Envio(canal="wa_link", exito=False, detalle="sin_celular")
CORREO_OK = Envio(canal="correo", exito=True, detalle="smtp")
CORREO_FALLA = Envio(canal="correo", exito=False, detalle="sin_correo")


class TestNotificadorCompuesto:
    async def test_con_celular_y_wa_link_que_sale_no_toca_el_correo(self):
        wa, correo = _Canal(WA_OK), _Canal(CORREO_OK)
        contacto = Contacto(USUARIO, correo=CORREO, celular=CELULAR)

        envio = await NotificadorCompuesto(wa=wa, correo=correo).enviar(contacto, "pedido_pagado", DATOS)

        assert envio is WA_OK
        assert wa.contactos == [contacto]
        assert correo.contactos == []

    async def test_con_celular_pero_wa_link_fallido_cae_a_correo(self):
        wa, correo = _Canal(WA_FALLA), _Canal(CORREO_OK)

        envio = await NotificadorCompuesto(wa=wa, correo=correo).enviar(
            Contacto(USUARIO, correo=CORREO, celular=CELULAR), "pedido_pagado", DATOS
        )

        assert envio is CORREO_OK
        assert len(wa.contactos) == len(correo.contactos) == 1

    async def test_sin_celular_va_directo_a_correo_sin_intentar_wa_link(self):
        wa, correo = _Canal(WA_OK), _Canal(CORREO_OK)

        envio = await NotificadorCompuesto(wa=wa, correo=correo).enviar(
            Contacto(USUARIO, correo=CORREO), "pedido_pagado", DATOS
        )

        assert envio is CORREO_OK
        assert wa.contactos == []

    async def test_si_tambien_falla_el_correo_el_fallo_sale_al_repartidor(self):
        """El compuesto no esconde el ultimo fallo: el repartidor necesita verlo para reintentar."""
        wa, correo = _Canal(WA_FALLA), _Canal(CORREO_FALLA)

        envio = await NotificadorCompuesto(wa=wa, correo=correo).enviar(
            Contacto(USUARIO, celular=CELULAR), "pedido_pagado", DATOS
        )

        assert envio is CORREO_FALLA

    def test_la_composicion_por_omision_es_wa_link_mas_correo(self):
        compuesto = notificador_desde_entorno()

        assert isinstance(compuesto, NotificadorCompuesto)
        assert isinstance(compuesto.wa, WaLink)
        assert isinstance(compuesto.correo, Correo)

    async def test_por_omision_y_sin_smtp_un_contacto_solo_con_correo_acaba_en_consola(self, capsys):
        envio = await notificador_desde_entorno().enviar(
            Contacto(USUARIO, correo=CORREO), "incidencia", DATOS
        )

        assert envio == Envio(canal="correo", exito=True, detalle="consola")
        assert "[correo:consola]" in capsys.readouterr().out

    async def test_por_omision_un_contacto_con_celular_sale_por_wa_link(self):
        envio = await notificador_desde_entorno().enviar(
            Contacto(USUARIO, correo=CORREO, celular=CELULAR), "incidencia", DATOS
        )

        assert envio.canal == "wa_link"
        assert envio.exito is True
        assert (envio.enlace or "").startswith(f"https://wa.me/{CELULAR}?text=")
