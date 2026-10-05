"""Utilidades de prueba del servicio de Inteligencia.

Dos piezas, y las dos existen para que la suite no necesite ni Postgres ni
los otros dos servicios levantados.

`motor` es un SQLite en memoria con el API de `MotorServicio`, o sea el mismo
que usa el runtime. Va con `StaticPool` porque sin el cada conexion abriria
una base nueva y las tablas creadas al arrancar no existirian en la
siguiente: el sintoma es un `no such table` que parece un fallo del modelo.

`CatalogoFalso` implementa los tres metodos de `ClienteCatalogo` sobre datos
en memoria. No es un simulacro con expectativas sino una implementacion
alternativa del puerto, que es lo que permite probar la orquestacion completa
(las cuatro etapas, la persistencia, la maquina de estados) sin red.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from tukit_comun.bd import MotorServicio
from tukit_inteligencia.modelos import Base

COLEGIO = "11111111-1111-5111-8111-111111111111"


@pytest.fixture()
async def motor():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite ignora las FK (y por tanto ON DELETE CASCADE) salvo que se pida por
    # conexion. Postgres las respeta en produccion; sin este pragma las pruebas
    # no verian la cascada de borrado de un trabajo. Es la receta estandar.
    @event.listens_for(engine.sync_engine, "connect")
    def _activar_fk(conexion, _registro):  # noqa: ANN001
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)
    motor = MotorServicio(servicio="prueba", engine=engine, _fabrica=fabrica)
    yield motor
    await motor.cerrar()


def opcion(sku: str, nivel: str, precio: int | None, **kw: Any) -> dict[str, Any]:
    return {
        "sku": sku,
        "nombre": kw.pop("nombre", f"Producto {sku}"),
        "nivel": nivel,
        "precio_cop": precio,
        "personaje": kw.pop("personaje", None),
        "marca": kw.pop("marca", "Generica"),
        "imagen_url": kw.pop("imagen_url", None),
        "unidad_base": kw.pop("unidad_base", "unidad"),
        "unidades_por_empaque": kw.pop("unidades_por_empaque", 1),
        "atributos": kw.pop("atributos", {}),
        "cumple": kw.pop("cumple", True),
        "producto_id": kw.pop("producto_id", None),
    }


@dataclass
class CatalogoFalso:
    """Implementacion en memoria del puerto hacia el catalogo."""

    renglones: list[dict[str, Any]] = field(default_factory=list)
    respuestas: dict[str, dict[str, Any]] = field(default_factory=dict)
    grado: str = "Cuarto"
    llamadas: list[str] = field(default_factory=list)

    async def listas(self, *, colegio_id: str, grado: str, anio_lectivo: int | None = None) -> list[dict]:
        self.llamadas.append("listas")
        if grado != self.grado:
            return []
        return [{"lista_id": "lista-1", "grado": grado, "anio_lectivo": anio_lectivo or 2026}]

    async def lista(self, lista_id: str) -> dict[str, Any]:
        self.llamadas.append("lista")
        return {
            "lista_id": lista_id,
            "grado": self.grado,
            "total_items": len(self.renglones),
            "items": self.renglones,
        }

    async def producto(self, sku: str) -> dict[str, Any]:
        """El producto por sku, en forma publica (`precio_desde`), buscado en las opciones."""
        self.llamadas.append("producto")
        for respuesta in self.respuestas.values():
            for op in respuesta.get("opciones", []):
                if op["sku"] == sku:
                    return {
                        "sku": op["sku"],
                        "nombre": op["nombre"],
                        "marca": op.get("marca"),
                        "nivel": op["nivel"],
                        "personaje": op.get("personaje"),
                        "imagen_url": op.get("imagen_url"),
                        "unidad_base": op.get("unidad_base", "unidad"),
                        "unidades_por_empaque": op.get("unidades_por_empaque", 1),
                        "precio_desde": op.get("precio_cop"),
                    }
        raise KeyError(sku)

    async def producto_de_personaje(self, concepto: str, personaje: str) -> dict[str, Any] | None:
        """Primera opcion de un concepto ancla cuyo personaje coincide, o None."""
        self.llamadas.append("producto_de_personaje")
        respuesta = next((r for r in self.respuestas.values() if r.get("concepto_codigo") == concepto), None)
        for op in (respuesta or {}).get("opciones", []):
            if str(op.get("personaje") or "").lower() == personaje.lower():
                return {
                    "sku": op["sku"],
                    "nombre": op["nombre"],
                    "marca": op.get("marca"),
                    "nivel": op["nivel"],
                    "personaje": op.get("personaje"),
                    "imagen_url": op.get("imagen_url"),
                    "unidad_base": op.get("unidad_base", "unidad"),
                    "unidades_por_empaque": op.get("unidades_por_empaque", 1),
                    "precio_desde": op.get("precio_cop"),
                }
        return None

    async def emparejar(
        self, renglones: list[str], conceptos: list[str | None] | None = None
    ) -> list[dict[str, Any]]:
        self.llamadas.append("emparejar")
        self.conceptos_asignados = conceptos
        return [
            self.respuestas.get(
                texto,
                {
                    "texto": texto,
                    "estado": "sin_match",
                    "concepto_codigo": None,
                    "concepto_nombre": None,
                    "parecido": 0.0,
                    "atributos_impuestos": {},
                    "motivo": "No reconocemos que pide este renglon.",
                    "opciones": [],
                },
            )
            for texto in renglones
        ]


def renglon(orden: int, texto: str, **kw: Any) -> dict[str, Any]:
    return {
        "orden": orden,
        "texto_original": texto,
        "cantidad": kw.pop("cantidad", 1),
        "tipo_item": kw.pop("tipo_item", "util"),
        "modo_adquisicion": kw.pop("modo_adquisicion", "mercado_abierto"),
        "instruccion_colegio": kw.pop("instruccion_colegio", None),
        "url_externa": kw.pop("url_externa", None),
    }


def reconocido(texto: str, codigo: str, opciones: list[dict[str, Any]], parecido: float = 0.95) -> dict:
    return {
        "texto": texto,
        "estado": "reconocido",
        "concepto_codigo": codigo,
        "concepto_nombre": codigo.lower(),
        "parecido": parecido,
        "atributos_impuestos": {},
        "motivo": "",
        "opciones": opciones,
    }
