"""Snapshot diario de metricas de calidad (`metrica_diaria`).

Decisiones:
- Las metricas de conteo se reconstruyen desde las fechas existentes; las de calidad (cobertura y
  emparejamiento del catalogo, salud del corpus) se recalculan contra el estado actual, asi que se
  congelan hacia adelante, una fila por dia.
- Es idempotente: borra las filas de hoy y las vuelve a insertar. Se corre a mano
  (`make instantanea-metricas`), con un solo escritor, por eso no hace falta un upsert.
- Lee los agregados por HTTP (Catalogo, Identidad, Inteligencia) y no toca sus bases.

Uso:  python -m tukit_operacion.instantanea
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, insert
from tukit_comun.bd import crear_motor

from .modelos import Base
from .remoto import ClienteMetricas

METRICA = Base.metadata.tables["metrica_diaria"]

_CAMPOS_CATALOGO = (
    "conceptos",
    "productos",
    "conceptos_con_tres_niveles",
    "conceptos_sin_producto",
    "productos_con_foto",
    "tiendas",
    "productos_sin_revisar",
)


def _a_bps(fraccion: float) -> int:
    return round(max(0.0, min(1.0, fraccion)) * 10000)


def _filas_de_snapshot(
    hoy: date,
    resumen: dict[str, Any] | None,
    metricas_por_colegio: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    filas: list[dict[str, Any]] = []

    if resumen is not None:
        for campo in _CAMPOS_CATALOGO:
            filas.append(
                {
                    "fecha": hoy,
                    "dimension": "catalogo",
                    "dimension_id": None,
                    "metrica": campo,
                    "valor": int(resumen.get(campo, 0) or 0),
                }
            )

    total_comprables = 0
    total_resueltas = 0
    for m in metricas_por_colegio:
        cid = m.get("colegio_id")
        if not cid or int(m.get("kits_armados", 0) or 0) <= 0:
            continue
        comprables = int(m.get("lineas_comprables", 0) or 0)
        resueltas = int(m.get("lineas_resueltas", 0) or 0)
        total_comprables += comprables
        total_resueltas += resueltas
        por_colegio = {
            "kits_armados": int(m.get("kits_armados", 0) or 0),
            "lineas_comprables": comprables,
            "lineas_resueltas": resueltas,
            "cobertura_bps": _a_bps(float(m.get("cobertura", 0.0) or 0.0)),
            "ahorro_cop": int(m.get("ahorro_total_cop", 0) or 0),
        }
        for nombre, valor in por_colegio.items():
            filas.append(
                {
                    "fecha": hoy,
                    "dimension": "colegio",
                    "dimension_id": str(cid),
                    "metrica": nombre,
                    "valor": valor,
                }
            )

    colegios_activos = len({f["dimension_id"] for f in filas if f["dimension"] == "colegio"})
    if colegios_activos:
        cobertura_global = total_resueltas / total_comprables if total_comprables else 0.0
        filas.append(
            {
                "fecha": hoy,
                "dimension": "global",
                "dimension_id": None,
                "metrica": "cobertura_bps",
                "valor": _a_bps(cobertura_global),
            }
        )
        filas.append(
            {
                "fecha": hoy,
                "dimension": "global",
                "dimension_id": None,
                "metrica": "colegios_activos",
                "valor": colegios_activos,
            }
        )

    return filas


async def escribir_instantanea(motor: Any, cliente: ClienteMetricas, hoy: date) -> dict[str, Any]:
    resumen = await cliente.resumen_catalogo()
    colegios = await cliente.colegios()

    metricas_por_colegio: list[dict[str, Any]] = []
    for c in colegios:
        cid = c.get("colegio_id")
        if not cid:
            continue
        m = await cliente.metricas_colegio(str(cid))
        if m is not None:
            metricas_por_colegio.append(m)

    filas = _filas_de_snapshot(hoy, resumen, metricas_por_colegio)

    async with motor.sesion() as db:
        conexion = await db.connection()
        await conexion.execute(delete(METRICA).where(METRICA.c.fecha == hoy))
        if filas:
            await conexion.execute(insert(METRICA), filas)

    return {
        "fecha": hoy.isoformat(),
        "filas": len(filas),
        "colegios_con_metricas": len(metricas_por_colegio),
        "catalogo_ok": resumen is not None,
    }


async def _correr(hoy: date) -> dict[str, Any]:
    motor = crear_motor("operacion")
    try:
        return await escribir_instantanea(motor, ClienteMetricas(), hoy)
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        description="Congela el snapshot diario de metricas de calidad en metrica_diaria."
    ).parse_args(argv)

    hoy = datetime.now(UTC).date()
    reporte = asyncio.run(_correr(hoy))
    print(
        f"snapshot {reporte['fecha']}: {reporte['filas']} filas, "
        f"{reporte['colegios_con_metricas']} colegios, "
        f"catalogo={'ok' if reporte['catalogo_ok'] else 'caido'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
