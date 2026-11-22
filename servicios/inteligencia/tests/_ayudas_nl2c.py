from __future__ import annotations

import copy
import uuid
from typing import Any

from sqlalchemy import insert
from tukit_inteligencia import nl2c
from tukit_inteligencia.modelos import Base, EstadoTrabajo

TRABAJO = Base.metadata.tables["trabajo_pipeline"]


PADRE = uuid.UUID("aaaaaaaa-aaaa-5aaa-8aaa-aaaaaaaaaaaa")


OTRO = uuid.UUID("bbbbbbbb-bbbb-5bbb-8bbb-bbbbbbbbbbbb")


PERSONAJES = ["Spiderman", "Bluey", "Frozen"]


class IdentidadFalsa:
    async def sesion(self, token: str):
        usuarios = {"tok-padre": PADRE, "tok-otro": OTRO}
        if token not in usuarios:
            return None
        return {
            "usuario_id": str(usuarios[token]),
            "roles": [{"rol": "acudiente", "ambito": None}],
            "version_permisos": 1,
        }


class CatalogoDePersonajes:
    async def _pedir(self, metodo: str, ruta: str, **kw: Any):
        return {
            "personajes": [
                {"nombre": n, "productos": 10 - i, "conceptos": ["C001", "C009", "C011", "C086"]}
                for i, n in enumerate(PERSONAJES)
            ]
            + [{"nombre": "Incompleto", "productos": 99, "conceptos": ["C001"]}]
        }


def kit_de_tres() -> dict[str, Any]:
    def linea(n: int, desc: str, sku: str, precio: int, alts: list[tuple[str, int]]) -> dict[str, Any]:
        return {
            "item_id": f"00000000-0000-4000-8000-00000000000{n}",
            "descripcion": desc,
            "informativa": False,
            "unidades_a_comprar": 2,
            "subtotal_linea": precio * 2,
            "producto_elegido": {
                "sku": sku,
                "nombre": f"{desc} {sku}",
                "marca": "Norma",
                "nivel": "premium",
                "precio": precio,
                "imagen_url": None,
            },
            "alternativas": [
                {"sku": s, "nombre": f"{desc} {s}", "nivel": "economico", "precio_cop": p, "imagen_url": None}
                for s, p in alts
            ],
        }

    return {
        "perfil": "Ahorrador",
        "total": {"monto": 100000},
        "consolidaciones": [{"sku": "SKU-JUNTO"}],
        "lineas": [
            linea(1, "Cuaderno cuadriculado", "CU-1", 9000, [("CU-2", 5000), ("CU-3", 7000)]),
            linea(2, "Tijeras punta roma", "TI-1", 6000, [("TI-2", 4000)]),
            linea(3, "Colores x12", "SKU-JUNTO", 8000, [("CO-2", 3000)]),
        ],
    }


def modelo(llamadas: list[dict[str, Any]], *, error: Exception | None = None):
    def doble(_sistema, _usuario, _decl, permitidas):
        doble.visto = {"sistema": _sistema, "usuario": _usuario, "permitidas": permitidas}
        if error:
            raise error
        return nl2c.RespuestaModelo(llamadas, 100, 20)

    return doble


async def sembrar(
    motor, usuario: uuid.UUID | None = PADRE, estado: str = EstadoTrabajo.PUBLICADO.value
) -> uuid.UUID:
    trabajo_id = uuid.uuid4()
    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(
            insert(TRABAJO).values(
                id=trabajo_id, usuario_id=usuario, estado=estado, origen="colegio_grado", hijos=[]
            )
        )
    return trabajo_id


H = {"Authorization": "Bearer tok-padre"}


def linea_de_kit(
    n: int,
    desc: str,
    sku: str,
    precio: int,
    alts: list[tuple[str, int, str]],
    *,
    nivel: str = "confiable",
    personaje: str | None = None,
) -> dict[str, Any]:
    return {
        "item_id": f"00000000-0000-4000-8000-{n:012d}",
        "descripcion": desc,
        "informativa": False,
        "unidades_a_comprar": 2,
        "subtotal_linea": precio * 2,
        "producto_elegido": {
            "sku": sku,
            "nombre": f"{desc} {sku}",
            "marca": "Norma",
            "nivel": nivel,
            "personaje": personaje,
            "precio": precio,
            "imagen_url": None,
        },
        "alternativas": [
            {"sku": s, "nombre": f"{desc} {s}", "nivel": nv, "precio_cop": p, "imagen_url": None}
            for s, p, nv in alts
        ],
    }


def kit_grande() -> dict[str, Any]:
    return {
        "perfil": "Fan",
        "total": {"monto": 200000},
        "consolidaciones": [{"sku": "SKU-JUNTO"}],
        "lineas": [
            linea_de_kit(
                1,
                "Cuaderno cuadriculado 100h",
                "CU-1",
                9000,
                [("CU-2", 5000, "economico"), ("CU-9", 12000, "premium")],
                personaje="spiderman",
            ),
            linea_de_kit(
                2, "Cuaderno rayado 100h", "CU-3", 9500, [("CU-4", 6000, "economico")], personaje="spiderman"
            ),
            linea_de_kit(
                3,
                "Cuaderno argollado 80h",
                "CU-5",
                11000,
                [("CU-6", 7000, "economico")],
                personaje="spiderman",
            ),
            linea_de_kit(4, "Cuaderno cosido 50h", "CU-7", 4000, [("CU-8", 4000, "confiable")]),
            linea_de_kit(
                5,
                "Colores x12",
                "CO-1",
                8000,
                [("CO-2", 3000, "economico"), ("CO-3", 14000, "premium")],
                nivel="economico",
            ),
            linea_de_kit(6, "Colores x24", "SKU-JUNTO", 15000, [("CO-4", 9000, "economico")]),
            linea_de_kit(7, "Tijeras punta roma", "TI-1", 6000, [("TI-2", 4000, "economico")]),
        ],
    }


def modelo_que_devuelve(llamadas: list[dict[str, Any]]):
    def doble(_sistema, usuario, _decl, _permitidas):
        doble.usuario = usuario
        return nl2c.RespuestaModelo(llamadas, 100, 20)

    return doble


def pedir(accion: str, categoria: str | None = None) -> list[dict[str, Any]]:
    args: dict[str, Any] = {"accion": accion}
    if categoria is not None:
        args["categoria"] = categoria
    return [{"name": "pedir_por_categoria", "args": args}]


def cambios(resp: dict[str, Any]) -> list[dict[str, Any]]:
    return [c["props"] for c in resp["ui"]["componentes"] if c["tipo"] == "PropuestaCambio"]


H_OTRO = {"Authorization": "Bearer tok-otro"}


CAMBIO = {"name": "proponer_cambio", "args": {"linea": "L1", "alternativa": "A1"}}


SIN_ACCION = {"name": "sin_accion", "args": {"motivo": "fuera_de_alcance"}}


def kit_repetido(n: int, descripcion: str = "Cuaderno cuadriculado") -> dict[str, Any]:
    base = kit_de_tres()["lineas"][0]
    lineas = []
    for i in range(n):
        ln = copy.deepcopy(base)
        ln["item_id"] = f"00000000-0000-4000-8000-{i:012d}"
        ln["descripcion"] = descripcion
        ln["producto_elegido"]["sku"] = f"CU-{i}"
        ln["alternativas"][0]["sku"] = f"ALT-{i}"
        lineas.append(ln)
    return {"perfil": "Ahorrador", "total": {"monto": 1}, "consolidaciones": [], "lineas": lineas}
