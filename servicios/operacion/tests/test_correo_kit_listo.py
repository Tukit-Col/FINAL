"""El correo "Tu kit esta listo": plantilla, privacidad, fallo y idempotencia.

Sin red ni SMTP: el modo consola escribe a un buzon temporal y los dobles
reemplazan a Identidad. Ningun correo real sale."""

from __future__ import annotations

import email
import uuid
from email import policy

from sqlalchemy import insert
from test_repartidor import (  # noqa: F401  (fixtures y ayudas del repartidor)
    CORREO,
    IdentidadContacto,
    _contar_notificaciones,
    _repartidor,
    motor_operacion,
    motor_origen,
)
from tukit_operacion.dominio.reparto import datos_plantilla, lugar_de
from tukit_operacion.notificador import Contacto, Correo, NotificadorFalso, asunto_de, html_de, texto_de

APODO = "Sofi-la-pilosa"
TRABAJO = uuid.UUID("33333333-3333-5333-8333-333333333333")


def _datos(**extra):
    carga = {"colegio_id": "c1", "grado": "3"}
    return datos_plantilla(
        "kits_publicados", TRABAJO, carga, base_web="https://tukit.co", colegio_nombre=extra.get("colegio")
    )


def test_plantilla_lleva_colegio_grado_y_enlace():
    datos = _datos(colegio="Colegio Alamei")
    texto = texto_de("kits_publicados", datos)
    assert "Tu kit esta listo" in texto
    assert "Colegio Alamei, grado 3" in texto
    assert f"https://tukit.co/kits/{TRABAJO}" in texto
    assert asunto_de("kits_publicados") == "Tu kit esta listo"


def test_lugar_degrada_sin_nombre_de_colegio():
    assert lugar_de(None, "3") == "grado 3"
    assert lugar_de(None, None) == "tu lista escolar"


def test_html_escapa_y_no_trae_apodo():
    datos = {"lugar": "<b>Colegio</b>, grado 3", "enlace": "https://tukit.co/kits/x"}
    cuerpo = html_de("kits_publicados", datos)
    assert "&lt;b&gt;" in cuerpo and "<b>Colegio" not in cuerpo
    assert html_de("pedido_pagado", {}) is None


async def test_modo_consola_escribe_eml_sin_apodo(tmp_path, monkeypatch):
    monkeypatch.delenv("TUKIT_SMTP_HOST", raising=False)
    monkeypatch.setenv("TUKIT_BUZON_DIR", str(tmp_path))
    envio = await Correo().enviar(
        Contacto(usuario_id="u1", correo=CORREO), "kits_publicados", _datos(colegio="Colegio Alamei")
    )
    assert envio.exito and envio.detalle == "consola"
    (archivo,) = tmp_path.glob("*.eml")
    mensaje = email.message_from_bytes(archivo.read_bytes(), policy=policy.default)
    assert mensaje["Subject"] == "Tu kit esta listo"
    assert mensaje["To"] == CORREO
    assert "Colegio Alamei" in mensaje.get_body(("plain",)).get_content()
    assert mensaje.get_body(("html",)) is not None
    assert APODO not in archivo.read_text()


async def test_fallo_de_smtp_no_lanza(monkeypatch):
    monkeypatch.setenv("TUKIT_SMTP_HOST", "smtp.invalido.test")

    def explota(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr("tukit_operacion.notificador.smtplib.SMTP", explota)
    envio = await Correo().enviar(Contacto(usuario_id="u1", correo=CORREO), "kits_publicados", _datos())
    assert envio.exito is False


async def test_sin_correo_es_fallo_no_excepcion():
    envio = await Correo().enviar(Contacto(usuario_id="u1"), "kits_publicados", _datos())
    assert envio.exito is False and envio.detalle == "sin_correo"


class _IdentidadConColegio(IdentidadContacto):
    async def nombre_colegio(self, colegio_id: str) -> str | None:
        return "Colegio Alamei"


async def test_repartidor_pone_colegio_y_grado_una_sola_vez(motor_operacion, motor_origen, monkeypatch):  # noqa: F811
    monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.co")
    engine, bandeja, trabajo = motor_origen
    async with engine.begin() as conexion:
        await conexion.execute(insert(trabajo).values(id=TRABAJO, usuario_id=uuid.uuid4()))
        await conexion.execute(
            insert(bandeja).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=TRABAJO,
                # La carga real no trae apodo ni referencia; aun si lo trajera, no se usa.
                carga={"colegio_id": "c1", "grado": "3", "apodo": APODO},
                intentos=0,
            )
        )
    notificador = NotificadorFalso()
    reparto = _repartidor(motor_operacion, engine, notificador, _IdentidadConColegio())
    await reparto.pasada()
    await reparto.pasada()  # una segunda pasada no reenvia
    assert len(notificador.enviados) == 1
    texto = notificador.enviados[0]["texto"]
    assert "Colegio Alamei, grado 3" in texto and APODO not in texto
    filas = await _contar_notificaciones(motor_operacion)
    assert len(filas) == 1 and APODO not in str(filas[0])
