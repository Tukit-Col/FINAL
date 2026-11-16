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
from tukit_operacion.notificador import (
    Contacto,
    Correo,
    NotificadorFalso,
    asunto_de,
    destino_enviable,
    html_de,
    texto_de,
)

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
    assert html_de("plantilla_inexistente", {}) is None


def test_encabezado_logo_con_url_absoluta(monkeypatch):
    monkeypatch.setenv("TUKIT_PUBLIC_URL", "https://tukit.example/")
    cuerpo = html_de("kits_publicados", {"lugar": "x", "enlace": "https://tukit.example/kits/x"})
    assert 'src="https://tukit.example/marca/icon-192.png"' in cuerpo
    assert 'alt="TUKIT"' in cuerpo and 'width="48"' in cuerpo


def test_encabezado_cae_a_texto_sin_url_publica(monkeypatch):
    monkeypatch.delenv("TUKIT_PUBLIC_URL", raising=False)
    cuerpo = html_de("kits_publicados", {"lugar": "x", "enlace": "https://tukit.co/kits/x"})
    assert 'src="cid:logo-tukit"' in cuerpo  # sin URL publica el logo viaja adjunto
    monkeypatch.setenv("TUKIT_PUBLIC_URL", "/marca")  # relativa: no vale en un correo
    assert 'src="cid:logo-tukit"' in html_de("kits_publicados", {})


def test_demas_correos_llevan_html_con_marco_y_escapan():
    cuerpo = html_de("pedido_pagado", {"pedido": "<i>1</i>", "turno": "7"})
    assert cuerpo and "Recibimos tu pago" in cuerpo and "&lt;i&gt;" in cuerpo


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


def test_todos_los_correos_llevan_enlace_y_pie_legal(monkeypatch):
    from tukit_operacion.notificador import _PLANTILLAS, destino_de, pie_texto

    monkeypatch.setenv("TUKIT_PUBLIC_URL", "https://tukit.example")
    for plantilla in _PLANTILLAS:
        cuerpo = html_de(plantilla, {"pedido": "AB12", "turno": "7", "enlace": "https://tukit.example/kits/x"})
        assert cuerpo and f'href="{destino_de(plantilla, {"enlace": "https://tukit.example/kits/x"})}"' in cuerpo
        assert "BAJA" in cuerpo and "Ley 1581" in cuerpo and "/legal/privacidad" in cuerpo
    assert "BAJA" in pie_texto() and "Ley 1581" in pie_texto()


def test_logo_va_adjunto_y_pedidos_no_muestran_caso(monkeypatch):
    monkeypatch.delenv("TUKIT_PUBLIC_URL", raising=False)
    mensaje = Correo()._armar("a@b.co", "pedido_pagado", {"pedido": "AB12", "turno": "7", "caso": "CAS1"})
    assert b"image/png" in bytes(mensaje) and "CAS1" not in mensaje.get_body(("html",)).get_content()


def test_ningun_correo_habla_de_turno(monkeypatch):
    from tukit_operacion.notificador import _PLANTILLAS, texto_de

    monkeypatch.setenv("TUKIT_PUBLIC_URL", "https://tukit.example")
    datos = {"pedido": "7F3A9C21", "caso": "AB12CD34", "lugar": "Colegio X, grado 3", "repartidor": "Luis"}
    for plantilla in _PLANTILLAS:
        assert "urno" not in (html_de(plantilla, datos) or "")
        assert "urno" not in texto_de(plantilla, datos)


def test_barra_de_fases_marca_la_fase_de_cada_aviso():
    esperado = {
        "pedido_pagado": "Pago confirmado",
        "pedido_en_preparacion": "Preparando tu kit",
        "pedido_despachado": "Despachado",
        "pedido_en_reparto": "En reparto",
        "pedido_entregado": "Entregado",
    }
    for plantilla, fase in esperado.items():
        cuerpo = html_de(plantilla, {"pedido": "7F3A9C21", "repartidor": "Luis"})
        assert f"Ahora: <b" in cuerpo and f">{fase}</b>" in cuerpo
    for plantilla in ("incidencia", "pedido_cancelado", "kits_publicados", "caso_respuesta"):
        assert "Ahora:" not in html_de(plantilla, {"pedido": "7F3A9C21"})


def test_pagado_muestra_el_total_y_enlaza_a_la_linea_de_tiempo(monkeypatch):
    monkeypatch.setenv("TUKIT_PUBLIC_URL", "https://tukit.example")
    pid = "11112222-0000-4000-8000-000000000000"
    cuerpo = html_de("pedido_pagado", {"pedido": "11112222", "total": 609343, "enlace": f"https://tukit.example/pedidos/{pid}"})
    assert "$609.343" in cuerpo and f'href="https://tukit.example/pedidos/{pid}"' in cuerpo


def test_variantes_de_cancelacion_incidencia_y_retoma():
    con = html_de("pedido_cancelado", {"pedido": "AB", "reembolso": True})
    sin = html_de("pedido_cancelado", {"pedido": "AB", "reembolso": False})
    assert "te devolvemos el pago" in con and "No se hizo ning&uacute;n cobro" in sin
    cobro = html_de("incidencia", {"pedido": "AB", "motivo": "pago_tras_cancelacion"})
    assert "ya estaba cancelado" in cobro and "Devolvemos un pago" in cobro
    assert "Retomamos tu pedido" in html_de("pedido_en_preparacion", {"pedido": "AB", "retoma": True})


class _IdentidadDosColegios(IdentidadContacto):
    def __init__(self) -> None:
        super().__init__()
        self.colegios: list[str] = []

    async def nombre_colegio(self, colegio_id: str) -> str | None:
        self.colegios.append(colegio_id)
        return {"c1": "Colegio A", "c2": "Colegio B"}.get(colegio_id)


async def test_repartidor_nombra_todas_las_listas_del_hogar(
    motor_operacion,  # noqa: F811
    motor_origen,  # noqa: F811
    monkeypatch,
):
    monkeypatch.setenv("TUKIT_WEB_URL", "https://tukit.co")
    engine, bandeja, trabajo = motor_origen
    async with engine.begin() as conexion:
        await conexion.execute(insert(trabajo).values(id=TRABAJO, usuario_id=uuid.uuid4()))
        await conexion.execute(
            insert(bandeja).values(
                tipo="kits_publicados",
                agregado_tipo="trabajo_pipeline",
                agregado_id=TRABAJO,
                carga={
                    "colegio_id": "c1",
                    "grado": "Septimo",
                    "listas": [
                        {"colegio_id": "c1", "grado": "Septimo"},
                        {"colegio_id": "c1", "grado": "Jardin"},
                        {"colegio_id": "c2", "grado": "5"},
                    ],
                },
                intentos=0,
            )
        )
    notificador = NotificadorFalso()
    identidad = _IdentidadDosColegios()
    reparto = _repartidor(motor_operacion, engine, notificador, identidad)
    await reparto.pasada()
    texto = notificador.enviados[0]["texto"]
    assert "Colegio A, grados Septimo y Jardin y Colegio B, grado 5" in texto
    # Un nombre por colegio distinto, no por lista.
    assert sorted(identidad.colegios) == ["c1", "c2"]


def test_html_kit_listo_lista_cada_lista_y_dice_los_kits():
    datos = {
        "lugar": "Colegio X, grados Septimo y Jardin",
        "listas": ["Colegio X, grado Septimo", "Colegio X, grado Jardin"],
        "enlace": "https://tukit.co/kits/x",
    }
    cuerpo = html_de("kits_publicados", datos)
    assert "Armamos los kits de Colegio X, grados Septimo y Jardin" in cuerpo
    assert ">Listas<" in cuerpo
    assert "Colegio X, grado Septimo<br>Colegio X, grado Jardin" in cuerpo
    # Una sola lista: la fila sigue llamandose "Lista" y el texto en singular.
    uno = html_de("kits_publicados", {"lugar": "Colegio X, grado 3", "listas": ["Colegio X, grado 3"]})
    assert ">Lista<" in uno and "Armamos la lista de Colegio X, grado 3" in uno


def test_el_remitente_siempre_lleva_direccion(monkeypatch):
    # `make` exporta TUKIT_SMTP_DESDE sin comillas y «TUKIT <tukit.ayuda@gmail.com>»
    # llegaba cortado en «TUKIT»: un From sin direccion, que Gmail acepta y no
    # entrega en la bandeja. Sin direccion se completa con la cuenta SMTP.
    monkeypatch.setenv("TUKIT_SMTP_DESDE", "TUKIT")
    monkeypatch.setenv("TUKIT_SMTP_USER", "tukit.ayuda@gmail.com")
    mensaje = Correo()._armar("a@b.co", "pedido_pagado", {"pedido": "AB12", "turno": "7", "caso": "CAS1"})
    assert mensaje["From"] == "TUKIT <tukit.ayuda@gmail.com>"
    monkeypatch.setenv("TUKIT_SMTP_DESDE", "TUKIT <otro@tukit.co>")
    mensaje = Correo()._armar("a@b.co", "pedido_pagado", {"pedido": "AB12", "turno": "7", "caso": "CAS1"})
    assert mensaje["From"] == "TUKIT <otro@tukit.co>"


def test_el_correo_lleva_fecha_y_message_id():
    # Sin Date ni Message-ID, Gmail acepta el envio por SMTP y luego no lo
    # pone en la bandeja: el E2E marcaba cuatro avisos «enviada» y no llego ninguno.
    mensaje = Correo()._armar("a@b.co", "pedido_pagado", {"pedido": "AB12", "turno": "7", "caso": "CAS1"})
    assert mensaje["Date"]
    assert mensaje["Message-ID"] and mensaje["Message-ID"].startswith("<")


def test_el_asunto_lleva_el_pedido_para_que_cada_aviso_sea_su_propia_conversacion():
    assert asunto_de("pedido_pagado", {"pedido": "8A6E8818"}) == "Recibimos tu pago · pedido 8A6E8818"
    assert asunto_de("caso_respuesta", {"caso": "AB12CD34"}) == "Respondimos tu caso · caso AB12CD34"
    assert asunto_de("kits_publicados", {"listas": []}) == "Tu kit esta listo"
    mensaje = Correo()._armar("a@b.co", "pedido_pagado", {"pedido": "AB12", "turno": "7", "caso": "CAS1"})
    assert mensaje["Subject"] == "Recibimos tu pago · pedido AB12"


def test_los_destinos_de_siembra_y_de_prueba_no_se_envian(monkeypatch):
    monkeypatch.delenv("TUKIT_CORREO_PERMITIDOS", raising=False)
    for falso in ("operador@tukit.co", "x@sub.tukit.co", "a@example.com", "a@ejemplo.com", "a@colegio.test"):
        assert destino_enviable(falso) is False, falso
    for real in ("maria@gmail.com", "papa@colegio.edu.co", "a@tukit.com"):
        assert destino_enviable(real) is True, real


def test_una_excepcion_por_entorno_deja_pasar_una_direccion_bloqueada(monkeypatch):
    monkeypatch.setenv("TUKIT_CORREO_PERMITIDOS", "ayuda@tukit.co, Otra@Tukit.co")
    assert destino_enviable("AYUDA@tukit.co") is True
    assert destino_enviable("operador@tukit.co") is False


async def test_destino_no_enviable_no_abre_smtp_y_se_marca_omitido(monkeypatch):
    monkeypatch.setenv("TUKIT_SMTP_HOST", "smtp.invalido.test")
    monkeypatch.delenv("TUKIT_CORREO_PERMITIDOS", raising=False)

    def no_debe_abrirse(*_a, **_k):
        raise AssertionError("no debia abrir SMTP")

    monkeypatch.setattr("tukit_operacion.notificador.smtplib.SMTP", no_debe_abrirse)
    envio = await Correo().enviar(
        Contacto(usuario_id="u1", correo="operador@tukit.co"), "pedido_pagado", {"pedido": "AB12"}
    )
    assert (envio.exito, envio.omitido, envio.detalle) == (False, True, "destino_no_enviable")
    assert envio.destino_dominio == "tukit.co"
    assert envio.asunto == "Recibimos tu pago · pedido AB12"


async def test_el_envio_lleva_asunto_y_dominio_pero_no_la_direccion(tmp_path, monkeypatch):
    monkeypatch.delenv("TUKIT_SMTP_HOST", raising=False)  # consola: la guarda no aplica
    monkeypatch.setenv("TUKIT_BUZON_DIR", str(tmp_path))
    envio = await Correo().enviar(
        Contacto(usuario_id="u1", correo="maria@gmail.com"), "pedido_pagado", {"pedido": "AB12"}
    )
    assert envio.exito and envio.destino_dominio == "gmail.com"
    assert envio.asunto == "Recibimos tu pago · pedido AB12"
    assert "maria" not in repr(envio)
