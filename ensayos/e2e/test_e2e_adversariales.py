"""Fase 5 de QA: las listas hostiles contra el stack vivo (ADV-01, 02, 04, 05, 06, 08, 09 y 10).

Las de nivel 1 (`servicios/inteligencia/tests/test_adv_inteligencia_subida.py`)
prueban el adaptador real contra un proveedor de mentira. Aqui la lista hostil
entra por la puerta de los E2E como la subiria un acudiente, y la lee la copia
de inteligencia de `conftest.py`: busca la pagina por su sha256 en el indice
compartido (`datos/golden/fixtures-modelo/indice.json`, que tambien apunta a
`ensayos/adversariales/fixtures/`) y devuelve la respuesta grabada. Todo lo
demas es el stack: identidad, el catalogo y su revision, los logs.

Solo se suben los fixtures cuya respuesta cumple el esquema. El lector de los
E2E valida con `PaginaLeida` sin envolver el `ValidationError`, asi que los de
esquema roto (ADV-03-p1, ADV-04-p3) darian aqui un 500 del lector y no del
producto; esos se prueban en el nivel 1 (H-A-48).

Lo que se exige: que nada hostil se publique ni cambie el catalogo, que la
respuesta no traiga el prompt ni datos de nadie, que cada acudiente vea solo
lo suyo, que cada subida cueste las llamadas de sus paginas y no mas, y que el
id de correlacion no se cruce entre peticiones.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
from e2e_flujo import cerrar, colegio_ficticio, quitar_concepto_sin_producto, registrar_acudiente, revision
from sqlalchemy import text
from stack_vivo import GATEWAY, RAIZ, conexion_a, logs_del_stack
from tukit_comun.http import CABECERA_CORRELACION
from tukit_inteligencia.gemini import _PROMPT

FIXTURES = RAIZ / "ensayos" / "adversariales" / "fixtures"
# Los fixtures ADV con respuesta valida para el esquema, en el orden en que se suben.
ACEPTADOS = ("ADV-01-p1", "ADV-02-p1", "ADV-04-p1", "ADV-04-p2", "ADV-05-p1", "ADV-06-p1", "ADV-08-p1")
NOMBRE_FICTICIO = "Inventada Zafiro"


def _items(fixture_id: str) -> list[str]:
    cuerpo = json.loads((FIXTURES / f"{fixture_id}.json").read_text())["respuesta_http"]["cuerpo"]
    return [
        i["descripcion"] for i in json.loads(cuerpo["candidates"][0]["content"]["parts"][0]["text"])["items"]
    ]


def _fragmentos_del_prompt(largo: int = 24) -> list[str]:
    """Ventanas del prompt del sistema: si una aparece en una respuesta, el prompt se filtro."""
    plano = " ".join(_PROMPT.split())
    return [plano[i : i + largo] for i in range(0, len(plano) - largo, largo)]


def _subir(
    http: httpx.Client, cabecera: dict[str, str], fixture_id: str, colegio_nombre: str
) -> httpx.Response:
    hijos = [{"referencia": "hijo-1", "colegio_nombre": colegio_nombre, "grado": "Tercero"}]
    return http.post(
        "/v1/listas/subir",
        headers=cabecera,
        data={"hijos": json.dumps(hijos), "referencia": "hijo-1"},
        files={"archivo": (f"{fixture_id}.png", (FIXTURES / f"{fixture_id}.png").read_bytes(), "image/png")},
    )


def _lecturas(puerta: dict[str, Any]) -> int:
    ruta: Path = puerta["lecturas"]
    return len(ruta.read_text().splitlines()) if ruta.exists() else 0


async def _huella_del_catalogo() -> dict[str, int]:
    """Lo que una lista hostil no deberia poder mover: precios y listas ya revisadas."""
    async with conexion_a("catalogo") as conexion:
        precios, suma = (
            await conexion.execute(
                text("select count(*), coalesce(sum(valor_centavos), 0) from precio_oferta")
            )
        ).one()
        revisadas = (
            await conexion.execute(
                text("select count(*) from version_lista_oficial where revisada_en is not null")
            )
        ).scalar_one()
        vigentes_revisadas = (
            await conexion.execute(
                text("select count(*) from version_lista_oficial where vigente and revisada_en is not null")
            )
        ).scalar_one()
    # Las versiones sin revisar que suben las pruebas nacen vigentes en listas nuevas (colegios
    # ficticios): lo que no puede cambiar es cuantas listas revisadas estan vigentes.
    return {
        "precios": precios,
        "suma_precios": int(suma),
        "revisadas": revisadas,
        "vigentes_revisadas": vigentes_revisadas,
    }


@pytest.fixture(scope="module")
def mama(http_flujo: httpx.Client, colegio_aliado: str) -> dict[str, Any]:
    return registrar_acudiente(http_flujo, colegio_aliado)


@pytest.fixture(scope="module")
def papa(http_flujo: httpx.Client, colegio_aliado: str) -> dict[str, Any]:
    return registrar_acudiente(http_flujo, colegio_aliado)


@pytest.fixture(scope="module")
def subidas(http_flujo: httpx.Client, mama: dict[str, Any], puerta: dict[str, Any]) -> dict[str, Any]:
    """Cada fixture aceptado, subido por la misma acudiente con un colegio escrito a mano distinto."""
    antes = asyncio.run(_huella_del_catalogo())
    resultado: dict[str, Any] = {"huella_antes": antes, "por_fixture": {}}
    for fixture_id in ACEPTADOS:
        colegio = colegio_ficticio(fixture_id)
        leidas = _lecturas(puerta)
        respuesta = _subir(http_flujo, mama["cabecera"], fixture_id, colegio)
        resultado["por_fixture"][fixture_id] = {
            "status": respuesta.status_code,
            "texto": respuesta.text,
            "cuerpo": respuesta.json(),
            "colegio": colegio,
            "llamadas": _lecturas(puerta) - leidas,
        }
    resultado["huella_despues"] = asyncio.run(_huella_del_catalogo())
    return resultado


def _version(subidas: dict[str, Any], fixture_id: str) -> str:
    subida = subidas["por_fixture"][fixture_id]
    assert subida["status"] == 202, f"{fixture_id}: {subida['texto']}"
    return subida["cuerpo"]["subidas"][0]["version_id"]


@pytest.mark.nfr("NFR-SEG-06")
class TestNadaHostilSePublica:
    @pytest.mark.parametrize("fixture_id", ACEPTADOS)
    def test_la_lista_queda_sin_revisar_con_los_renglones_que_el_modelo_leyo(
        self, fixture_id, http_flujo, admin, subidas, record_property
    ):
        record_property("caso_adv", "ADV-02")
        vista = revision(http_flujo, admin, _version(subidas, fixture_id))

        items = sorted(vista["items"], key=lambda i: i["orden"])
        hostiles = [i for i in items if i["texto_original"] not in _items("ADV-09-p1")]
        record_property("fixture_id", fixture_id)
        record_property(
            "conceptos_de_los_renglones_hostiles",
            " | ".join(
                f"{i['texto_original'][:40]}->{(i['concepto'] or {}).get('codigo')}" for i in hostiles
            ),
        )
        assert vista["revisada"] is False
        assert [i["texto_original"] for i in items] == _items(fixture_id)

    def test_las_listas_hostiles_no_mueven_precios_ni_listas_revisadas(self, subidas, record_property):
        record_property("caso_adv", "ADV-06")
        antes, despues = subidas["huella_antes"], subidas["huella_despues"]

        for clave, valor in despues.items():
            record_property(f"{clave}_antes_despues", f"{antes[clave]}->{valor}")
        assert despues == antes

    def test_la_acudiente_no_recibe_ningun_kit_hasta_que_un_humano_revise(
        self, http_flujo, mama, subidas, record_property
    ):
        record_property("caso_adv", "ADV-06")
        solicitudes = http_flujo.get("/v1/mis-solicitudes", headers=mama["cabecera"]).json()["solicitudes"]
        trabajos = http_flujo.get("/v1/trabajos", headers=mama["cabecera"]).json()["trabajos"]

        colegios = {s["colegio"] for s in subidas["por_fixture"].values()}
        versiones = {_version(subidas, fixture_id) for fixture_id in ACEPTADOS}
        de_las_hostiles = [s for s in solicitudes if s["colegio_nombre"] in colegios]
        con_kit = [t for t in trabajos if any(h.get("version_id") in versiones for h in t["hijos"])]
        record_property("solicitudes_hostiles", len(de_las_hostiles))
        record_property("trabajos_de_las_hostiles", len(con_kit))
        assert sorted(s["colegio_nombre"] for s in de_las_hostiles) == sorted(colegios)
        assert {s["tipo"] for s in de_las_hostiles} == {"recibida"}
        assert con_kit == []


async def _versiones_de_la_lista(version_id: str) -> tuple[str, list[tuple[str, int, bool, bool]]]:
    """La lista de esa version y `(version_id, numero, vigente, revisada)` de cada una de sus versiones."""
    async with conexion_a("catalogo") as conexion:
        lista_id = (
            await conexion.execute(
                text("select lista_id::text from version_lista_oficial where id = cast(:v as uuid)"),
                {"v": version_id},
            )
        ).scalar_one()
        filas = await conexion.execute(
            text(
                "select id::text, numero, vigente, revisada_en is not null from version_lista_oficial "
                "where lista_id = cast(:l as uuid) order by numero"
            ),
            {"l": lista_id},
        )
        return lista_id, [tuple(f) for f in filas]


@pytest.fixture(scope="module")
def desplazada(http_flujo, admin, mama, papa, catalogo) -> dict[str, Any]:
    """ADV-06: la lista base de un colegio la revisa un humano; luego otro acudiente sube la hostil."""
    colegio = colegio_ficticio("ADV-06-revisada")
    base = _subir(http_flujo, mama["cabecera"], "ADV-09-p1", colegio)
    assert base.status_code == 202, base.text
    revisada = base.json()["subidas"][0]["version_id"]
    quitar_concepto_sin_producto(http_flujo, admin, revisada, catalogo["sin_producto"])
    cerrar(http_flujo, admin, revisada)
    hostil = _subir(http_flujo, papa["cabecera"], "ADV-06-p1", colegio)
    assert hostil.status_code == 202, hostil.text
    lista_id, versiones = asyncio.run(_versiones_de_la_lista(revisada))
    publica = http_flujo.get(f"/v1/listas/{lista_id}")
    assert publica.status_code == 200, publica.text
    return {
        "revisada": revisada,
        "hostil": hostil.json()["subidas"][0]["version_id"],
        "versiones": versiones,
        "publica": publica.json(),
    }


@pytest.mark.nfr("NFR-SEG-06")
class TestLaSubidaNoDesplazaLaListaRevisada:
    """ADV-06, «Borra la lista anterior del colegio». Un humano revisa la lista base de un colegio y
    despues otro acudiente sube la hostil para el mismo colegio escrito a mano y el mismo grado."""

    def test_la_hostil_entra_como_una_version_nueva_sin_revisar(self, desplazada, record_property):
        record_property("caso_adv", "ADV-06")
        por_id = {v[0]: v for v in desplazada["versiones"]}

        record_property(
            "versiones",
            " | ".join(f"n{n} vigente={vig} revisada={rev}" for _, n, vig, rev in desplazada["versiones"]),
        )
        assert desplazada["hostil"] != desplazada["revisada"]
        assert por_id[desplazada["revisada"]][3] is True
        assert por_id[desplazada["hostil"]][3] is False

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-52: `POST /v1/admin/listas/importar` le quita la vigencia a la version revisada "
        "antes de crear la nueva; la subida sin revisar de cualquier acudiente pasa a ser la lista vigente "
        "del colegio y es la que sirve GET /v1/listas/{id}",
    )
    def test_la_lista_vigente_sigue_siendo_la_revisada(self, desplazada, record_property):
        record_property("caso_adv", "ADV-06")
        vigentes = [v[0] for v in desplazada["versiones"] if v[2]]
        renglones = json.dumps(desplazada["publica"], ensure_ascii=False)
        hostiles = [t for t in _items("ADV-06-p1") if t not in _items("ADV-09-p1") and t in renglones]

        record_property("publica_revisada", desplazada["publica"].get("revisada"))
        record_property("renglones_hostiles_en_la_publica", len(hostiles))
        assert vigentes == [desplazada["revisada"]], "la version vigente ya no es la revisada"
        assert hostiles == []


@pytest.mark.nfr("NFR-SEG-07")
class TestNadaSeFiltra:
    # ADV-04 (LLM07) cuenta en NFR-SEG-06, como lo pone la matriz.
    @pytest.mark.nfr("NFR-SEG-06")
    @pytest.mark.parametrize("fixture_id", ACEPTADOS)
    def test_el_202_no_trae_el_prompt_ni_lo_que_la_lista_dice(self, fixture_id, subidas, record_property):
        record_property("caso_adv", "ADV-04")
        texto = subidas["por_fixture"][fixture_id]["texto"]

        fugas = [f for f in _fragmentos_del_prompt() if f in " ".join(texto.split())]
        record_property("fragmentos_del_prompt", len(fugas))
        assert set(subidas["por_fixture"][fixture_id]["cuerpo"]) == {"subidas", "contacto_referencia"}
        assert fugas == []
        assert not any(renglon in texto for renglon in _items(fixture_id))

    def test_otro_acudiente_no_ve_las_listas_de_la_primera_en_las_suyas(
        self, http_flujo, papa, subidas, record_property
    ):
        record_property("caso_adv", "ADV-05")
        de_el = http_flujo.get("/v1/mis-solicitudes", headers=papa["cabecera"]).json()["solicitudes"]

        colegios = {s["colegio"] for s in subidas["por_fixture"].values()}
        assert [s for s in de_el if s["colegio_nombre"] in colegios] == []

    @pytest.mark.xfail(
        strict=True,
        reason="H-C-06 (punto 4): el router /v1/admin de catalogo no lee Authorization; otro acudiente lee "
        "la revision de la lista ajena, con el nombre del menor que el modelo transcribio",
    )
    def test_otro_acudiente_no_lee_la_revision_de_la_lista_ajena(
        self, http_flujo, papa, subidas, record_property
    ):
        record_property("caso_adv", "ADV-05")
        ajena = http_flujo.get(
            f"/v1/admin/listas/{_version(subidas, 'ADV-05-p1')}/revision", headers=papa["cabecera"]
        )

        record_property("status_lista_ajena", ajena.status_code)
        record_property("nombre_visible_para_otro", ajena.text.count(NOMBRE_FICTICIO))
        assert ajena.status_code in (401, 403), f"otro acudiente recibe {ajena.status_code}"
        assert NOMBRE_FICTICIO not in ajena.text

    def test_el_nombre_del_menor_no_queda_en_los_logs(self, subidas, puerta, record_property):
        record_property("caso_adv", "ADV-05")
        assert subidas["por_fixture"]["ADV-05-p1"]["status"] == 202
        registros = [*logs_del_stack(), *sorted(Path(puerta["carpeta"]).glob("*.log"))]

        con_nombre = [r.name for r in registros if NOMBRE_FICTICIO in r.read_text(errors="replace")]
        record_property("logs_barridos", len(registros))
        record_property("logs_con_nombre", len(con_nombre))
        assert con_nombre == []

    @pytest.mark.xfail(
        strict=True,
        reason="H-C-15: el nombre del menor que el modelo transcribe entra al catalogo tal cual, en el "
        "renglon y en la percepcion cruda, sin depurar",
    )
    def test_el_nombre_del_menor_no_entra_al_catalogo(self, http_flujo, admin, subidas, record_property):
        record_property("caso_adv", "ADV-05")
        version_id = _version(subidas, "ADV-05-p1")
        vista = http_flujo.get(f"/v1/admin/listas/{version_id}/revision", headers=admin)
        percepcion = http_flujo.get(f"/v1/admin/listas/{version_id}/percepcion", headers=admin)

        apariciones = vista.text.count(NOMBRE_FICTICIO) + percepcion.text.count(NOMBRE_FICTICIO)
        record_property("apariciones_en_el_catalogo", apariciones)
        assert apariciones == 0, (
            f"el nombre ficticio aparece {apariciones} veces en la revision y la percepcion"
        )


@pytest.mark.nfr("NFR-SEG-03")
class TestCadaSubidaCuestaSusPaginas:
    @pytest.mark.parametrize("fixture_id", ACEPTADOS)
    def test_una_pagina_es_una_llamada_al_modelo(self, fixture_id, subidas, record_property):
        record_property("caso_adv", "ADV-09")
        llamadas = subidas["por_fixture"][fixture_id]["llamadas"]

        record_property("llamadas_al_modelo", llamadas)
        assert llamadas == 1


@pytest.mark.nfr("NFR-COS-01")
def test_la_copia_de_inteligencia_no_intento_salir_a_gemini(subidas, puerta, record_property):
    record_property("caso_adv", "ADV-09")
    intentos = puerta["guardia"].read_text().splitlines() if puerta["guardia"].exists() else []

    record_property(
        "paginas_servidas_de_fixtures", sum(s["llamadas"] for s in subidas["por_fixture"].values())
    )
    record_property("intentos_de_salir", len(intentos))
    assert intentos == []


@pytest.mark.nfr("NFR-SEG-06")
class TestLaCorrelacionPorElStack:
    def test_veinte_peticiones_a_la_vez_no_cruzan_sus_ids(self, stack, record_property):
        record_property("caso_adv", "ADV-10")

        async def pedir_todas() -> list[tuple[str, str]]:
            async with httpx.AsyncClient(base_url=GATEWAY, timeout=30.0) as cliente:
                ids = [f"qa-adv10-{uuid.uuid4().hex[:12]}" for _ in range(20)]
                respuestas = await asyncio.gather(
                    *(cliente.get("/v1/colegios", headers={CABECERA_CORRELACION: cid}) for cid in ids)
                )
                return [
                    (cid, r.headers.get(CABECERA_CORRELACION, ""))
                    for cid, r in zip(ids, respuestas, strict=True)
                ]

        pares = asyncio.run(pedir_todas())

        cruzados = [enviado for enviado, devuelto in pares if enviado != devuelto]
        record_property("peticiones", len(pares))
        record_property("ids_cruzados", len(cruzados))
        assert cruzados == []

    @pytest.mark.xfail(
        strict=True,
        reason="H-A-51: un byte no ASCII en una cabecera reenviada (aqui x-correlation-id) tumba la "
        "peticion en la puerta con un 500",
    )
    def test_un_byte_no_ascii_en_la_correlacion_no_da_500(self, stack, record_property):
        record_property("caso_adv", "ADV-10")
        respuesta = httpx.get(
            f"{GATEWAY}/v1/colegios", headers={CABECERA_CORRELACION: "acudiente-ñandú".encode()}, timeout=30.0
        )

        record_property("status", respuesta.status_code)
        assert respuesta.status_code != 500, respuesta.text
