"""La subida de listas de un acudiente: PDFs entran, se vuelven versiones pendientes.

A diferencia de `POST /v1/trabajos` (que arma un kit desechable) y de
`POST /v1/admin/onboarding` (la subida de un administrador, un PDF por vez),
`POST /v1/listas/subir` es la puerta del acudiente del §2: el hogar sube el PDF
de cada hijo y cada uno se percibe y se importa al catalogo como una VERSION
PENDIENTE de esa (colegio, grado), ligada al padre por su `contacto_referencia`
(el `usuario_id` que Identidad emite; nunca su correo ni telefono). No se crea
ningun trabajo: el padre espera a que un administrador apruebe la version.

Lo que se fija aqui es el contrato de esa puerta: que el contacto se registre
una sola vez, que cada hijo se percibe y se importe, que dos hijos del mismo
(colegio, grado) compartan una sola version (no una que pise a la otra), y que
un archivo rechazado por percepcion no toque el catalogo ni devuelva el archivo.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from tukit_inteligencia import api
from tukit_inteligencia.api import app
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida

COLEGIO = "11111111-1111-5111-8111-111111111111"
OTRO_COLEGIO = "22222222-2222-5222-8222-222222222222"


class CatalogoImportador:
    """Doble del puerto del catalogo: registra cada `importar_lista`."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []
        self._proximo = 0

    async def importar_lista(
        self,
        *,
        colegio_id: str,
        grado: str,
        anio_lectivo: int,
        items: list[dict],
        documento_base64: str,
        percepcion_cruda: list[dict],
        contacto_referencia: str | None = None,
        preferencias: dict | None = None,
        colegio_datos: dict | None = None,
        origen: str = "onboarding",
    ) -> dict:
        self._proximo += 1
        version_id = f"ver-{self._proximo}"
        self.llamadas.append(
            {
                "colegio_id": colegio_id,
                "grado": grado,
                "anio_lectivo": anio_lectivo,
                "items": items,
                "documento_base64": documento_base64,
                "percepcion_cruda": percepcion_cruda,
                "contacto_referencia": contacto_referencia,
                "preferencias": preferencias,
                "colegio_datos": colegio_datos,
                "origen": origen,
            }
        )
        return {"version_id": version_id, "tarea_id": f"tar-{self._proximo}", "items": len(items)}


class IdentidadDoble:
    """Doble de Identidad: devuelve un id fijo y guarda con que se le llamo."""

    def __init__(self, usuario_id: str | None = "usr-1") -> None:
        self.usuario_id = usuario_id
        self.llamadas: list[dict] = []
        self.usuario_por_token: dict[str, str] = {}

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append({"correo": correo, "celular": celular})
        return self.usuario_id

    async def usuario_del_token(self, token: str) -> str | None:
        return self.usuario_por_token.get(token)

    async def datos_directorio(self, dane: str) -> dict | None:
        # El DANE no esta en el directorio (o Identidad no responde): la subida
        # degrada a nombre+dane, que es justo lo que estas pruebas comprueban.
        return None


@pytest.fixture()
def catalogo():
    return CatalogoImportador()


@pytest.fixture()
def identidad():
    return IdentidadDoble()


@pytest.fixture()
async def cliente(motor, catalogo, identidad, monkeypatch):
    app.state.motor = motor
    app.state.catalogo = catalogo
    app.state.identidad = identidad

    # Percepcion por omision: una pagina, grado "Cuarto", dos items (uno sin
    # cantidad). Cada prueba que necesite otra cosa monkeypatchea `_LEER`.
    def _renderizar(_contenido: bytes) -> list[bytes]:
        return [b"p1"]

    def _leer(_png: bytes, _numero: int) -> PaginaLeida:
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[
                ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
                ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
            ],
        )

    monkeypatch.setattr(api, "_RENDERIZAR", _renderizar)
    monkeypatch.setattr(api, "_LEER", _leer)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


def _subida(
    hijos: list[dict],
    *,
    contacto: dict | None = None,
    preferencias: dict | None = None,
    archivos: list[tuple[str, bytes]] | None = None,
):
    """Arma el multipart de la subida: `hijos`, `contacto` y `preferencias` como
    JSON, un `archivo`+`referencia` por PDF."""
    if archivos is None:
        archivos = [(h["referencia"], b"%PDF-falso") for h in hijos]
    data: dict[str, str] = {"hijos": json.dumps(hijos)}
    if contacto is not None:
        data["contacto"] = json.dumps(contacto)
    if preferencias is not None:
        data["preferencias"] = json.dumps(preferencias)
    files = []
    for referencia, contenido in archivos:
        files.append(("archivo", (f"{referencia}.pdf", contenido, "application/pdf")))
        files.append(("referencia", (None, referencia)))
    return {"data": data, "files": files}


class TestSubirFeliz:
    async def test_un_hijo_se_percibe_e_importa_como_version_pendiente(self, cliente, catalogo):
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}],
            contacto={"correo": "mama@ejemplo.com", "celular": "+573001112233"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        env = respuesta.json()
        assert env["subidas"] == [{"referencia": "hijo-1", "version_id": "ver-1", "grado": "Cuarto"}]
        assert len(catalogo.llamadas) == 1
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["grado"] == "Cuarto"
        assert llamada["anio_lectivo"] == 2026
        assert llamada["items"][0]["texto_original"] == "2 cuadernos cuadriculados"
        # La subida del acudiente entra como 'sugerencia_padre', no 'onboarding':
        # de eso depende que la cola diga "Un acudiente la subió" y no "El colegio
        # la envió". Regresion de un bug donde `importar_lista` fijaba onboarding.
        assert llamada["origen"] == "sugerencia_padre"

    async def test_el_contacto_se_registra_una_vez_y_solo_viaja_su_id(self, cliente, catalogo, identidad):
        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": OTRO_COLEGIO, "grado": "Cuarto"},
            ],
            contacto={"correo": "mama@ejemplo.com", "celular": "+573001112233"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        env = respuesta.json()
        # Identidad se llama UNA vez para el hogar, no una por hijo.
        assert len(identidad.llamadas) == 1
        assert identidad.llamadas[0]["correo"] == "mama@ejemplo.com"
        # Lo que viaja al catalogo es el id, jamas el correo/telefono.
        assert env["contacto_referencia"] == "usr-1"
        assert all(ll["contacto_referencia"] == "usr-1" for ll in catalogo.llamadas)
        assert "mama@ejemplo.com" not in respuesta.text
        assert "+573001112233" not in respuesta.text

    async def test_con_sesion_no_reregistra_contacto(self, cliente, catalogo, identidad):
        # El acudiente ya viene autenticado (Bearer): su usuario_id sale de la
        # sesion y ES el contacto_referencia. No se re-registra el contacto.
        identidad.usuario_por_token["tok-acudiente"] = "usr-sesion"
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            contacto={"correo": "mama@ejemplo.com", "celular": "+573001112233"},
        )
        respuesta = await cliente.post(
            "/v1/listas/subir", headers={"Authorization": "Bearer tok-acudiente"}, **cuerpo
        )

        assert respuesta.status_code == 202
        env = respuesta.json()
        # Ya venia autenticado: cero registros, y el id de la sesion es la traza.
        assert len(identidad.llamadas) == 0
        assert env["contacto_referencia"] == "usr-sesion"
        assert all(ll["contacto_referencia"] == "usr-sesion" for ll in catalogo.llamadas)

    async def test_dos_hijos_del_mismo_colegio_y_grado_comparten_una_version(self, cliente, catalogo):
        # No se importa dos veces la misma (colegio, grado): la segunda pisaria
        # a la primera. Se importa una vez y los dos hijos apuntan a esa version.
        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Cuarto"},
            ],
            contacto={"correo": "mama@ejemplo.com"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        env = respuesta.json()
        assert len(catalogo.llamadas) == 1
        versiones = {s["version_id"] for s in env["subidas"]}
        assert versiones == {"ver-1"}
        assert {s["referencia"] for s in env["subidas"]} == {"hijo-1", "hijo-2"}

    async def test_las_preferencias_del_hogar_viajan_a_cada_version(self, cliente, catalogo):
        # El paso 3 es del HOGAR: las mismas preferencias viajan con cada version
        # importada, para que el kit de la aprobacion las use.
        preferencias = {
            "pesos": {"precio": 0.6, "marca_exigida": 0.15, "calidad": 0.2, "personaje": 0.05},
            "disposicion_sobreprecio": 0.0,
        }
        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": OTRO_COLEGIO, "grado": "Cuarto"},
            ],
            contacto={"correo": "mama@ejemplo.com"},
            preferencias=preferencias,
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert len(catalogo.llamadas) == 2
        # Cada version lleva ademas QUE hijo la subio: con eso el poller sabe
        # de quien es el personaje al armarle al papa su kit.
        assert [ll["preferencias"] for ll in catalogo.llamadas] == [
            {**preferencias, "referencias_hijo": ["hijo-1"]},
            {**preferencias, "referencias_hijo": ["hijo-2"]},
        ]

    async def test_sin_preferencias_solo_viaja_el_hijo(self, cliente, catalogo):
        cuerpo = _subida([{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert catalogo.llamadas[0]["preferencias"] == {"referencias_hijo": ["hijo-1"]}

    async def test_dos_hijos_en_una_version_guardan_las_dos_referencias(self, cliente, catalogo):
        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Cuarto"},
            ]
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert len(catalogo.llamadas) == 1
        assert catalogo.llamadas[0]["preferencias"]["referencias_hijo"] == ["hijo-1", "hijo-2"]

    async def test_dos_grados_distintos_son_dos_versiones(self, cliente, catalogo, monkeypatch):
        def _leer(_png: bytes, numero: int) -> PaginaLeida:
            grado = "Cuarto" if numero == 1 else "Quinto"
            return PaginaLeida(grados=[grado], completa=True, items=[ItemExtraido(descripcion="lapiz")])

        # Cada PDF rinde una pagina distinta segun su primer byte, para que el
        # grado percibido difiera entre hijos.
        estado = {"n": 0}

        def _renderizar(_contenido: bytes) -> list[bytes]:
            estado["n"] += 1
            return [b"p1"] if estado["n"] == 1 else [b"p2"]

        def _leer_por_pagina(png: bytes, _numero: int) -> PaginaLeida:
            grado = "Cuarto" if png == b"p1" else "Quinto"
            return PaginaLeida(grados=[grado], completa=True, items=[ItemExtraido(descripcion="lapiz")])

        monkeypatch.setattr(api, "_RENDERIZAR", _renderizar)
        monkeypatch.setattr(api, "_LEER", _leer_por_pagina)

        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Quinto"},
            ]
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert len(catalogo.llamadas) == 2
        assert {ll["grado"] for ll in catalogo.llamadas} == {"Cuarto", "Quinto"}


class TestColegioPorDirectorioOEscrito:
    """El acudiente que sube su archivo designa el colegio de dos formas nuevas:
    del directorio de Bogota (trae DANE) o escrito a mano (solo nombre). En los
    dos casos el colegio NO existe todavia en Tukit: nace al aprobar. El backend
    deriva el `colegio_id` de forma estable y pasa los datos del colegio para que
    la cola los muestre y la aprobacion cree la identidad."""

    async def test_colegio_del_directorio_deriva_el_id_del_dane(self, cliente, catalogo):
        from tukit_comun import derivar

        cuerpo = _subida(
            [
                {
                    "referencia": "hijo-1",
                    "colegio_dane": "311001105731",
                    "colegio_nombre": "ACADEMIA CENTRAL DE SISTEMAS",
                    "grado": "Cuarto",
                }
            ],
            contacto={"correo": "mama@ejemplo.com"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        llamada = catalogo.llamadas[0]
        # El id se deriva del DANE con el contrato compartido: el mismo que
        # Identidad usara al crear el colegio en la aprobacion.
        assert llamada["colegio_id"] == str(derivar("colegio", "311001105731"))
        # Los datos del colegio viajan para la cola y la creacion de identidad.
        assert llamada["colegio_datos"]["dane"] == "311001105731"
        assert llamada["colegio_datos"]["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"

    async def test_colegio_escrito_a_mano_deriva_el_id_del_nombre_normalizado(self, cliente, catalogo):
        from tukit_comun import derivar

        # Dos acudientes que escriben el MISMO colegio (aunque con espacios y
        # mayusculas distintas) tienen que converger a la misma version.
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_nombre": "  Gimnasio  Del   Norte ", "grado": "Cuarto"}],
            contacto={"correo": "mama@ejemplo.com"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == str(derivar("colegio", "libre", "gimnasio del norte"))
        assert llamada["colegio_datos"]["nombre"] == "Gimnasio Del Norte"
        assert llamada["colegio_datos"].get("dane") is None

    async def test_sin_colegio_alguno_es_422(self, cliente, catalogo):
        # Ni id, ni dane, ni nombre: no hay a que (colegio, grado) importar.
        cuerpo = _subida([{"referencia": "hijo-1", "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 422
        assert catalogo.llamadas == []

    async def test_colegio_id_de_aliado_conocido_sigue_funcionando(self, cliente, catalogo):
        # La ruta "lista_oficial" (colegio ya aliado) manda `colegio_id` directo
        # y no lleva datos de colegio: no hay identidad que crear.
        cuerpo = _subida([{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["colegio_datos"] is None


class TestSubirRechazado:
    async def test_un_archivo_de_varios_grados_es_422_sin_devolver_el_archivo(
        self, cliente, catalogo, monkeypatch
    ):
        def _leer_multi(_png: bytes, numero: int) -> PaginaLeida:
            grado = "Cuarto" if numero == 1 else "Quinto"
            return PaginaLeida(grados=[grado], items=[ItemExtraido(descripcion="lapiz")])

        monkeypatch.setattr(api, "_RENDERIZAR", lambda _c: [b"p1", b"p2"])
        monkeypatch.setattr(api, "_LEER", _leer_multi)

        marcador = b"%PDF-marcador-secreto-del-cliente"
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            archivos=[("hijo-1", marcador)],
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 422
        assert respuesta.json()["error"] == "lista_de_varios_grados"
        assert base64.b64encode(marcador).decode() not in respuesta.text
        assert "marcador-secreto" not in respuesta.text
        # Nada se importa si un archivo se rechaza: es todo o nada por hogar.
        assert catalogo.llamadas == []

    async def test_sin_archivo_para_un_hijo_es_422(self, cliente, catalogo):
        # Un hijo sin su PDF: falta el `archivo`. Se manda un multipart con los
        # `hijos` pero sin parte `archivo` (un campo de relleno fuerza el
        # encoding multipart en httpx aunque no haya archivos).
        hijos = [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}]
        cuerpo = {
            "data": {"hijos": json.dumps(hijos)},
            "files": [("relleno", (None, "x"))],
        }
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 422
        assert respuesta.json()["campo"] == "archivo"
        assert catalogo.llamadas == []


class TestSubirDegradado:
    async def test_sin_contacto_igual_importa_sin_referencia(self, cliente, catalogo, identidad):
        # Un hogar que no deja contacto: la version igual se importa (perder el
        # aviso es malo, perder la lista por no poder avisar es peor), sin
        # `contacto_referencia`.
        cuerpo = _subida([{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert identidad.llamadas == []
        assert respuesta.json()["contacto_referencia"] is None
        assert catalogo.llamadas[0]["contacto_referencia"] is None
