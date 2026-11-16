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
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from tukit_inteligencia import importaciones, trabajador, trabajos
from tukit_inteligencia.api import app
from tukit_inteligencia.modelos import Base
from tukit_inteligencia.percepcion import ItemExtraido, PaginaLeida
from tukit_inteligencia.remoto import RemotoCaido

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
        clave_idempotencia: str | None = None,
        referencias: list[str] | None = None,
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
                "clave_idempotencia": clave_idempotencia,
                "referencias": referencias,
            }
        )
        return {"version_id": version_id, "tarea_id": f"tar-{self._proximo}", "items": len(items)}


class IdentidadDoble:
    """Doble de Identidad: devuelve un id fijo y guarda con que se le llamo."""

    def __init__(self, usuario_id: str | None = "usr-1") -> None:
        self.usuario_id = usuario_id
        self.llamadas: list[dict] = []
        # DANE -> datos DUEB que devolveria `/v1/directorio/{dane}`.
        self.directorio: dict[str, dict] = {}
        self.usuario_por_token: dict[str, str] = {}
        # Los colegios que Identidad ya tiene (`GET /v1/colegios`).
        self.conocidos: list[dict] = []

    async def colegios_conocidos(self) -> list[dict]:
        return list(self.conocidos)

    async def registrar_contacto(self, correo: str, celular: str | None = None) -> str | None:
        self.llamadas.append({"correo": correo, "celular": celular})
        return self.usuario_id

    async def usuario_del_token(self, token: str) -> str | None:
        return self.usuario_por_token.get(token)

    async def datos_directorio(self, dane: str) -> dict | None:
        # Un DANE fuera del directorio (o Identidad caida) devuelve None: la
        # subida degrada a nombre+dane.
        return self.directorio.get(dane)


@pytest.fixture()
def catalogo():
    return CatalogoImportador()


@pytest.fixture()
def identidad():
    return IdentidadDoble()


@pytest.fixture()
async def cliente(motor, catalogo, identidad):
    app.state.motor = motor
    app.state.catalogo = catalogo
    app.state.identidad = identidad

    # Percepcion por omision: una pagina, grado "Cuarto", dos items (uno sin
    # cantidad). Cada prueba que necesite otra cosa cambia `app.state.leer`.
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

    app.state.renderizar = _renderizar
    app.state.leer = _leer

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

    async def test_cada_lista_viaja_con_la_referencia_de_su_hijo(self, cliente, catalogo):
        # El catalogo la reenvia en `lista_verificada`: el kit del padre la usa
        # como clave de `personaje_por_hijo` en vez de un `hijo-1` fijo.
        cuerpo = _subida(
            [
                {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"},
                {"referencia": "hijo-2", "colegio_id": OTRO_COLEGIO, "grado": "Cuarto"},
            ],
            contacto={"correo": "mama@ejemplo.com"},
        )
        assert (await cliente.post("/v1/listas/subir", **cuerpo)).status_code == 202
        por_colegio = {ll["colegio_id"]: ll["referencias"] for ll in catalogo.llamadas}
        assert por_colegio == {COLEGIO: ["hijo-1"], OTRO_COLEGIO: ["hijo-2"]}

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
        assert all(ll["preferencias"] == preferencias for ll in catalogo.llamadas)

    async def test_un_personaje_demasiado_largo_se_rechaza(self, cliente, catalogo):
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}],
            contacto={"correo": "mama@ejemplo.com"},
            preferencias={"personaje_por_hijo": {"hijo-1": ["x" * 61]}},
        )
        assert (await cliente.post("/v1/listas/subir", **cuerpo)).status_code == 422
        assert catalogo.llamadas == []

    async def test_sin_preferencias_no_se_manda_nada(self, cliente, catalogo):
        cuerpo = _subida([{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        assert catalogo.llamadas[0]["preferencias"] is None

    async def test_dos_grados_distintos_son_dos_versiones(self, cliente, catalogo):
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

        app.state.renderizar = _renderizar
        app.state.leer = _leer_por_pagina

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


class TestElApodoDeLaSubida:
    """El apodo del hijo que sube su lista rotula su kit, pero NO viaja por el
    Catalogo (Ley 1581): se queda cifrado en Inteligencia hasta que el poller
    arma el kit."""

    async def test_el_apodo_no_viaja_al_catalogo_y_queda_guardado_aqui(self, cliente, catalogo, motor):
        from tukit_inteligencia import apodos_subida

        cuerpo = _subida(
            [{"referencia": "hijo-2", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "  Luca "}],
            contacto={"correo": "mama@ejemplo.com"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)
        assert respuesta.status_code == 202
        version_id = respuesta.json()["subidas"][0]["version_id"]
        assert "Luca" not in str(catalogo.llamadas)
        assert await apodos_subida.apodos_de(motor, version_id) == {"hijo-2": "Luca"}

    async def test_un_apodo_de_mas_de_40_se_rechaza(self, cliente):
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "apodo": "x" * 41}],
            contacto={"correo": "mama@ejemplo.com"},
        )
        assert (await cliente.post("/v1/listas/subir", **cuerpo)).status_code in (400, 422)


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

    async def test_el_directorio_tapa_los_huecos_del_perfil_sin_pisar_la_subida(
        self, cliente, catalogo, identidad
    ):
        # El DUEB pre-llena direccion y contacto del colegio nuevo; el nombre que
        # trajo la subida manda sobre el del directorio.
        identidad.directorio["311001105731"] = {
            "dane": "311001105731",
            "nombre": "ACADEMIA CENTRAL DE SISTEMAS (DUEB)",
            "direccion": "CL 1 # 2-3",
        }
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
        datos = catalogo.llamadas[0]["colegio_datos"]
        assert datos["direccion"] == "CL 1 # 2-3"
        assert datos["nombre"] == "ACADEMIA CENTRAL DE SISTEMAS"

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

    async def test_escrito_a_mano_reusa_el_colegio_que_identidad_ya_tiene(self, cliente, catalogo, identidad):
        # H-UG-01: Alamei existia en Identidad sin grado verificado, el papa lo
        # escribio "tal cual" y la aprobacion dio de alta un segundo Alamei.
        identidad.conocidos = [
            {"colegio_id": "6375ea98-a4ff-5878-ad9d-8cb7e24574e3", "nombre": "Colegio Alamei", "dane": None}
        ]
        cuerpo = _subida(
            [{"referencia": "hijo-1", "colegio_nombre": "  colegio   ALAMEÍ ", "grado": "Cuarto"}],
            contacto={"correo": "mama@ejemplo.com"},
        )
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == "6375ea98-a4ff-5878-ad9d-8cb7e24574e3"
        # Ya existe: no viajan datos, asi la aprobacion no da de alta otro.
        assert llamada["colegio_datos"] is None

    async def test_del_directorio_reusa_el_colegio_con_ese_dane(self, cliente, catalogo, identidad):
        identidad.conocidos = [
            {"colegio_id": "c-existente", "nombre": "Academia Central", "dane": "311001105731"}
        ]
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
        await cliente.post("/v1/listas/subir", **cuerpo)

        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == "c-existente"
        assert llamada["colegio_datos"] is None

    async def test_un_homonimo_con_otro_dane_no_se_reusa(self, cliente, catalogo, identidad):
        # Dos colegios con el mismo nombre y DANE distinto son dos colegios.
        identidad.conocidos = [{"colegio_id": "c-otro", "nombre": "Colegio Santa Ana", "dane": "111"}]
        cuerpo = _subida(
            [
                {
                    "referencia": "hijo-1",
                    "colegio_dane": "222",
                    "colegio_nombre": "Colegio Santa Ana",
                    "grado": "Cuarto",
                }
            ],
            contacto={"correo": "mama@ejemplo.com"},
        )
        await cliente.post("/v1/listas/subir", **cuerpo)

        from tukit_comun import derivar

        assert catalogo.llamadas[0]["colegio_id"] == str(derivar("colegio", "222"))

    async def test_sin_colegio_alguno_es_422(self, cliente, catalogo):
        # Ni id, ni dane, ni nombre: no hay a que (colegio, grado) importar.
        cuerpo = _subida([{"referencia": "hijo-1", "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 422
        assert catalogo.llamadas == []

    async def test_colegio_id_de_aliado_conocido_importa_sin_datos_de_colegio(self, cliente, catalogo):
        # La ruta "lista_oficial" (colegio ya aliado) manda `colegio_id` directo
        # y no lleva datos de colegio: no hay identidad que crear.
        cuerpo = _subida([{"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto"}])
        respuesta = await cliente.post("/v1/listas/subir", **cuerpo)

        assert respuesta.status_code == 202
        llamada = catalogo.llamadas[0]
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["colegio_datos"] is None


class TestSubirRechazado:
    async def test_un_archivo_de_varios_grados_es_422_sin_devolver_el_archivo(self, cliente, catalogo):
        def _leer_multi(_png: bytes, numero: int) -> PaginaLeida:
            grado = "Cuarto" if numero == 1 else "Quinto"
            return PaginaLeida(grados=[grado], items=[ItemExtraido(descripcion="lapiz")])

        app.state.renderizar = lambda _c: [b"p1", b"p2"]
        app.state.leer = _leer_multi

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


# --- Con el catalogo caido: la subida se importa despues (H-B-01, ADR 0040) -----------------------


# La subida de listas con el catalogo caido (H-B-01, ADR 0040).
#
# Antes, `POST /v1/listas/subir` percibia cada PDF y lo importaba al catalogo en
# la misma peticion. Con el catalogo caido el `RemotoCaido` salia sin manejar: el
# acudiente recibia un 500 y la lista, ya percibida, se perdia.
#
# Lo que se fija aqui:
#
# - con el catalogo caido la subida responde 202, cada hijo queda `pendiente` y
#   lo percibido (renglones, percepcion cruda y PDF) queda guardado en
#   `importacion_lista`;
# - cuando el catalogo vuelve, el trabajador la importa una sola vez, con lo ya
#   percibido y sin volver a percibir;
# - dos reintentos, o una respuesta que se perdio, dan una sola version: cada
#   destino viaja con la misma `clave_idempotencia`;
# - con el catalogo arriba la respuesta es la de siempre y aqui no queda copia
#   de la lista ni del PDF; si se cae a mitad de la subida, solo queda guardado
#   lo que no alcanzo a entrar.


IMPORTACION = Base.metadata.tables["importacion_lista"]
PADRE = uuid.UUID("33333333-3333-5333-8333-333333333333")
PDF = b"%PDF-falso"


def _despues() -> datetime:
    """Un momento en que cualquier espera de reintento ya vencio."""
    return datetime.now(UTC) + timedelta(hours=1)


def _con_zona(momento: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona; se guardaron en UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


class CatalogoIntermitente(CatalogoImportador):
    """El catalogo que se cae y vuelve, con la idempotencia del de verdad.

    Con `caido`, cada importacion lanza el `RemotoCaido` que lanza el cliente
    cuando el catalogo no responde; con `caer_tras`, se cae despues de crear
    esas versiones. Con una clave ya vista devuelve la version que ya tenia,
    como `POST /v1/admin/listas/importar`. `llamadas` solo cuenta las
    importaciones que de verdad crearon una version; `intentos`, todas.
    """

    def __init__(self) -> None:
        super().__init__()
        self.caido = False
        self.caer_tras: int | None = None
        self.rechazo: int | None = None
        self.perder_respuesta = False
        self.intentos: list[str | None] = []
        self._por_clave: dict[str, dict] = {}

    async def importar_lista(self, *, clave_idempotencia: str | None = None, **kw) -> dict:
        self.intentos.append(clave_idempotencia)
        if self.caido or (self.caer_tras is not None and len(self.llamadas) >= self.caer_tras):
            raise RemotoCaido(
                "catalogo", "/v1/admin/listas/importar no respondio (All connection attempts failed)"
            )
        if self.rechazo is not None:
            raise RemotoCaido(
                "catalogo", f"/v1/admin/listas/importar respondio {self.rechazo}", estado=self.rechazo
            )
        if clave_idempotencia is not None and clave_idempotencia in self._por_clave:
            return self._por_clave[clave_idempotencia]
        respuesta = await super().importar_lista(clave_idempotencia=clave_idempotencia, **kw)
        if clave_idempotencia is not None:
            self._por_clave[clave_idempotencia] = respuesta
        if self.perder_respuesta:
            # La importacion entro, pero la respuesta no llego (un timeout).
            self.perder_respuesta = False
            raise RemotoCaido("catalogo", "/v1/admin/listas/importar no respondio (ReadTimeout)")
        return respuesta

    async def listas_por_contacto(self, _contacto: str) -> list[dict]:
        if self.caido:
            raise RemotoCaido("catalogo", "/v1/admin/listas no respondio")
        return []


@pytest.fixture()
def intermitente():
    return CatalogoIntermitente()


@pytest.fixture()
def identidad_padre():
    return IdentidadDoble(usuario_id=str(PADRE))


@pytest.fixture()
def lecturas():
    """Cuantas paginas se le pidieron al modelo: la percepcion es la etapa cara."""
    return {"n": 0}


@pytest.fixture()
async def cliente_diferido(motor, intermitente, identidad_padre, lecturas):
    app.state.motor = motor
    app.state.catalogo = intermitente
    app.state.identidad = identidad_padre

    def _leer(_png: bytes, _numero: int) -> PaginaLeida:
        lecturas["n"] += 1
        return PaginaLeida(
            grados=["Cuarto"],
            completa=True,
            items=[
                ItemExtraido(descripcion="2 cuadernos cuadriculados", cantidad=2, confianza=0.91),
                ItemExtraido(descripcion="1 caja de colores", cantidad=None, confianza=0.8),
            ],
        )

    app.state.renderizar = lambda _contenido: [b"p1"]
    app.state.leer = _leer

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://prueba") as http:
        yield http


async def _filas(motor) -> list:
    async with motor.engine.begin() as conexion:
        return list(await conexion.execute(select(IMPORTACION).order_by(IMPORTACION.c.creado_en)))


def _un_hijo(**extra) -> dict:
    hijo = {"referencia": "hijo-1", "colegio_id": COLEGIO, "grado": "Cuarto", "anio_lectivo": 2026}
    hijo.update(extra)
    return hijo


class TestSubirConElCatalogoCaido:
    async def test_responde_202_y_el_hijo_queda_pendiente(self, cliente_diferido, intermitente):
        intermitente.caido = True
        respuesta = await cliente_diferido.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )

        assert respuesta.status_code == 202
        env = respuesta.json()
        assert env["subidas"] == [
            {"referencia": "hijo-1", "version_id": None, "grado": "Cuarto", "estado": "pendiente"}
        ]
        assert env["contacto_referencia"] == str(PADRE)
        assert intermitente.llamadas == []

    async def test_lo_percibido_queda_guardado(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        preferencias = {"pesos": {"precio": 0.7, "calidad": 0.3}}
        await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"}, preferencias=preferencias),
        )

        [fila] = await _filas(motor)
        assert fila.estado == "pendiente"
        assert fila.referencias == ["hijo-1"]
        assert fila.colegio_id == COLEGIO
        assert fila.grado == "Cuarto"
        assert fila.anio_lectivo == 2026
        assert fila.contacto_referencia == str(PADRE)
        assert fila.documento == PDF
        assert [i["texto_original"] for i in fila.carga["items"]] == [
            "2 cuadernos cuadriculados",
            "1 caja de colores",
        ]
        assert fila.carga["percepcion_cruda"]
        assert fila.carga["preferencias"] == preferencias
        assert fila.carga["origen"] == "sugerencia_padre"
        assert fila.intentos == 1
        assert "no respondio" in fila.error
        assert fila.version_id is None

    async def test_la_respuesta_no_repite_el_archivo(self, cliente_diferido, intermitente):
        intermitente.caido = True
        marcador = b"%PDF-marcador-secreto-del-cliente"
        respuesta = await cliente_diferido.post(
            "/v1/listas/subir", **_subida([_un_hijo()], archivos=[("hijo-1", marcador)])
        )

        assert respuesta.status_code == 202
        assert "marcador-secreto" not in respuesta.text
        assert base64.b64encode(marcador).decode() not in respuesta.text

    async def test_dos_hijos_del_mismo_destino_comparten_una_fila(
        self, cliente_diferido, intermitente, motor
    ):
        intermitente.caido = True
        respuesta = await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2")], contacto={"correo": "mama@ejemplo.com"}),
        )

        assert respuesta.status_code == 202
        assert [s["estado"] for s in respuesta.json()["subidas"]] == ["pendiente", "pendiente"]
        [fila] = await _filas(motor)
        assert fila.referencias == ["hijo-1", "hijo-2"]

        intermitente.caido = False
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1
        assert len(intermitente.llamadas) == 1

    async def test_al_primer_destino_caido_no_insiste_con_el_resto(
        self, cliente_diferido, intermitente, motor
    ):
        # Con el catalogo caido cada intento puede costar el tiempo de espera
        # entero del cliente: la peticion no los encadena. El resto queda
        # pendiente, listo para el trabajador.
        intermitente.caido = True
        respuesta = await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida(
                [_un_hijo(), _un_hijo(referencia="hijo-2", grado="Quinto", colegio_id=str(uuid.uuid4()))]
            ),
        )

        assert respuesta.status_code == 202
        assert len(intermitente.intentos) == 1
        filas = await _filas(motor)
        assert {f.estado for f in filas} == {"pendiente"}
        # Las dos quedan para dentro de segundos: el trabajador las toma pronto.
        pronto = datetime.now(UTC) + timedelta(seconds=30)
        assert all(_con_zona(f.proximo_intento_en) < pronto for f in filas)


class TestSubirCuandoElCatalogoVuelve:
    async def test_el_trabajador_la_importa_una_vez_con_lo_ya_percibido(
        self, cliente_diferido, intermitente, motor, lecturas
    ):
        intermitente.caido = True
        await cliente_diferido.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )
        assert lecturas["n"] == 1
        [pendiente] = await _filas(motor)

        intermitente.caido = False
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1

        # Una importacion, con lo que se percibio en la subida: sin volver a leer.
        assert lecturas["n"] == 1
        [llamada] = intermitente.llamadas
        assert llamada["colegio_id"] == COLEGIO
        assert llamada["grado"] == "Cuarto"
        assert llamada["anio_lectivo"] == 2026
        assert llamada["items"] == pendiente.carga["items"]
        assert llamada["percepcion_cruda"] == pendiente.carga["percepcion_cruda"]
        assert base64.b64decode(llamada["documento_base64"]) == PDF
        assert llamada["contacto_referencia"] == str(PADRE)
        assert llamada["origen"] == "sugerencia_padre"
        assert llamada["clave_idempotencia"] == str(pendiente.clave_idempotencia)
        assert llamada["referencias"] == ["hijo-1"]

        [fila] = await _filas(motor)
        assert fila.estado == "importada"
        assert fila.version_id == "ver-1"
        # Ya esta en el catalogo: aca no queda copia del PDF ni de lo percibido.
        assert fila.documento is None
        assert fila.carga is None

    async def test_el_apodo_espera_cifrado_y_llega_al_importar(self, cliente_diferido, intermitente, motor):
        from tukit_inteligencia import apodos_subida

        intermitente.caido = True
        hijo = {**_un_hijo(), "apodo": "Luca"}
        await cliente_diferido.post(
            "/v1/listas/subir", **_subida([hijo], contacto={"correo": "mama@ejemplo.com"})
        )
        [pendiente] = await _filas(motor)
        # Mientras espera, el apodo no queda en claro en la fila.
        assert "Luca" not in str(pendiente.carga)

        intermitente.caido = False
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1
        assert "Luca" not in str(intermitente.llamadas)
        assert await apodos_subida.apodos_de(motor, "ver-1") == {"hijo-1": "Luca"}

    async def test_dos_reintentos_dan_una_sola_version(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        intermitente.caido = False

        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 0
        assert len(intermitente.llamadas) == 1
        assert len(intermitente.intentos) == 2  # el de la subida y el del reintento

    async def test_una_respuesta_perdida_no_duplica_la_version(self, cliente_diferido, intermitente, motor):
        # La importacion entra al catalogo pero la respuesta se pierde: la
        # subida la deja pendiente y el reintento manda la MISMA clave, asi que
        # el catalogo devuelve la version que ya tenia en vez de crear otra.
        intermitente.perder_respuesta = True
        respuesta = await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        assert respuesta.json()["subidas"][0]["estado"] == "pendiente"

        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1
        assert len(intermitente.llamadas) == 1
        assert intermitente.intentos[0] == intermitente.intentos[1]
        [fila] = await _filas(motor)
        assert (fila.estado, fila.version_id) == ("importada", "ver-1")

    async def test_si_sigue_caido_la_espera_se_duplica_con_tope(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        [fila] = await _filas(motor)
        assert fila.intentos == 1

        momento = _despues()
        for espera in (10, 20, 40, 80, 160, 300, 300):
            assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=momento) == 0
            [fila] = await _filas(motor)
            assert fila.estado == "pendiente"
            assert _con_zona(fila.proximo_intento_en) == momento + timedelta(seconds=espera)
            momento += timedelta(seconds=espera)

    async def test_con_el_catalogo_caido_una_pasada_hace_un_solo_intento(
        self, cliente_diferido, intermitente, motor
    ):
        intermitente.caido = True
        await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2", colegio_id=str(uuid.uuid4()))]),
        )
        assert len(intermitente.intentos) == 1

        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 0
        assert len(intermitente.intentos) == 2

    async def test_no_toma_una_fila_cuya_espera_no_vencio(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        intermitente.caido = False
        async with motor.engine.begin() as conexion:
            await conexion.execute(
                update(IMPORTACION).values(proximo_intento_en=datetime.now(UTC) + timedelta(minutes=5))
            )

        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente) == 0
        assert intermitente.llamadas == []

    async def test_la_vuelta_del_trabajador_reintenta_las_pendientes(
        self, cliente_diferido, intermitente, motor
    ):
        intermitente.caido = True
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        intermitente.caido = False
        async with motor.engine.begin() as conexion:
            await conexion.execute(update(IMPORTACION).values(proximo_intento_en=datetime.now(UTC)))

        await trabajador.correr_una_vez(motor=motor, catalogo=intermitente)

        assert len(intermitente.llamadas) == 1


class TestSubirSinCopiaConElCatalogoArriba:
    async def test_responde_las_versiones_creadas_y_aqui_no_queda_copia(
        self, cliente_diferido, intermitente, motor
    ):
        respuesta = await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))

        assert respuesta.status_code == 202
        assert respuesta.json()["subidas"] == [
            {"referencia": "hijo-1", "version_id": "ver-1", "grado": "Cuarto"}
        ]
        assert uuid.UUID(intermitente.llamadas[0]["clave_idempotencia"])
        # La lista y el PDF quedan en el catalogo y en ningun otro lado.
        assert await _filas(motor) == []

    async def test_si_se_cae_a_mitad_solo_se_guarda_lo_que_no_entro(
        self, cliente_diferido, intermitente, motor
    ):
        intermitente.caer_tras = 1
        quinto = str(uuid.uuid4())
        respuesta = await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2", colegio_id=quinto)]),
        )

        assert respuesta.status_code == 202
        assert respuesta.json()["subidas"] == [
            {"referencia": "hijo-1", "version_id": "ver-1", "grado": "Cuarto"},
            {"referencia": "hijo-2", "version_id": None, "grado": "Cuarto", "estado": "pendiente"},
        ]
        [fila] = await _filas(motor)
        assert (fila.colegio_id, fila.referencias) == (quinto, ["hijo-2"])
        # La segunda se intento con la misma clave que guarda la fila.
        assert intermitente.intentos[1] == str(fila.clave_idempotencia)

        intermitente.caer_tras = None
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 1
        assert [ll["colegio_id"] for ll in intermitente.llamadas] == [COLEGIO, quinto]

    async def test_cada_destino_lleva_su_propia_clave(self, cliente_diferido, intermitente):
        await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida([_un_hijo(), _un_hijo(referencia="hijo-2", colegio_id=str(uuid.uuid4()))]),
        )
        claves = [ll["clave_idempotencia"] for ll in intermitente.llamadas]
        assert len(claves) == 2
        assert len(set(claves)) == 2

    async def test_dos_subidas_iguales_son_dos_claves(self, cliente_diferido, intermitente):
        # La clave es por subida y destino: un acudiente que vuelve a subir la
        # misma lista hace una version nueva, igual que antes.
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        assert len({ll["clave_idempotencia"] for ll in intermitente.llamadas}) == 2


class TestSubirConUnRechazoDelCatalogo:
    async def test_en_la_subida_un_4xx_sube_sin_guardar_nada_para_reintentar(
        self, cliente_diferido, intermitente, motor
    ):
        # Un 4xx no es una caida: reintentarlo daria lo mismo. El error sube
        # y no queda nada para el trabajador.
        intermitente.rechazo = 422
        with pytest.raises(RemotoCaido):
            await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))

        assert await _filas(motor) == []

    async def test_en_un_reintento_queda_fallida_y_no_se_vuelve_a_intentar(
        self, cliente_diferido, intermitente, motor
    ):
        intermitente.caido = True
        await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))
        intermitente.caido = False
        intermitente.rechazo = 422

        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 0
        [fila] = await _filas(motor)
        assert fila.estado == "fallida"
        assert "422" in fila.error

        intermitente.rechazo = None
        assert await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues()) == 0
        assert len(intermitente.intentos) == 2
        assert intermitente.llamadas == []

    @pytest.mark.parametrize("estado", [408, 429, 502, 503])
    async def test_un_408_429_o_5xx_si_es_caida(self, cliente_diferido, intermitente, motor, estado):
        intermitente.rechazo = estado
        respuesta = await cliente_diferido.post("/v1/listas/subir", **_subida([_un_hijo()]))

        assert respuesta.status_code == 202
        [fila] = await _filas(motor)
        assert fila.estado == "pendiente"


class TestLaSubidaPendienteEnMisSolicitudes:
    async def test_la_pendiente_sale_como_recibida_sin_tarea(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        await cliente_diferido.post(
            "/v1/listas/subir",
            **_subida(
                [{"referencia": "hijo-1", "colegio_nombre": "Gimnasio Ficticio", "grado": "Cuarto"}],
                contacto={"correo": "mama@ejemplo.com"},
            ),
        )

        # Con el catalogo todavia caido: las listas del catalogo no estan, pero
        # la que espera aca si.
        env = await trabajos.mis_solicitudes(motor, PADRE, catalogo=intermitente)
        assert env["listas_disponibles"] is False
        [solicitud] = env["solicitudes"]
        assert solicitud["tipo"] == "recibida"
        assert solicitud["tarea_id"] is None
        assert solicitud["colegio_nombre"] == "Gimnasio Ficticio"
        assert solicitud["grado"] == "Cuarto"

        # Ya importada, la muestra el catalogo y no sale dos veces de aca.
        intermitente.caido = False
        await importaciones.reintentar_pendientes(motor, catalogo=intermitente, ahora=_despues())
        env = await trabajos.mis_solicitudes(motor, PADRE, catalogo=intermitente)
        assert env["solicitudes"] == []

    async def test_no_muestra_las_de_otro_acudiente(self, cliente_diferido, intermitente, motor):
        intermitente.caido = True
        await cliente_diferido.post(
            "/v1/listas/subir", **_subida([_un_hijo()], contacto={"correo": "mama@ejemplo.com"})
        )

        env = await trabajos.mis_solicitudes(motor, uuid.uuid4(), catalogo=intermitente)
        assert env["solicitudes"] == []
