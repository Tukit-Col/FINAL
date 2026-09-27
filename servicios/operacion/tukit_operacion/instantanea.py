"""El snapshot diario de metricas punto-en-el-tiempo (`metrica_diaria`).

Hay dos clases de metrica en el panel del operador. Las de CONTEO (pedidos por
dia, colegios por dia, listas verificadas por dia) se reconstruyen en cualquier
momento desde las columnas de fecha que ya existen (`creado_en`, `revisada_en`,
`publicada_en`...). Las de CALIDAD —la cobertura y el match del catalogo, la
salud del corpus— NO: se recalculan contra el estado ACTUAL del catalogo, asi
que ayer ya no se puede volver a medir. Por eso este proceso las congela hacia
adelante, una fila por dia, y asi nace la traza de "como mejora el algoritmo
mientras crezco el catalogo y lo afino".

    python -m tukit_operacion.instantanea        # snapshot de hoy (idempotente)

Es idempotente: reescribe TODAS las filas del dia (borra las de hoy y las vuelve
a insertar), asi que correrlo dos veces el mismo dia deja lo mismo. Se pensó
para correrlo a mano por sesion de trabajo (`make instantanea-metricas`), no en
un bucle: un solo escritor, sin concurrencia, por eso el borrar-e-insertar es
correcto y no hace falta un upsert por dialecto.

Lee los agregados por HTTP (Catalogo, Identidad, Inteligencia), no tocando sus
bases: la frontera de bases se respeta, igual que en el resto de Operacion. Si
un servicio esta caido, se salta esa parte y anota lo que si logro: un snapshot
parcial es una respuesta valida.
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

# Las siete cifras del resumen de catalogo que valen la pena congelar: son el
# estado del corpus hoy, y crecen a medida que se cura. Se guardan como conteo
# directo (la columna `valor` es entera). El nombre de la metrica es la clave.
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
    """Una fraccion 0..1 a puntos base (0..10000), enteros porque `valor` lo es.

    La cobertura viaja como 0.9231; guardarla como 9231 conserva dos decimales
    de porcentaje sin cambiar el tipo de la columna ni perder precision util.
    """
    return round(max(0.0, min(1.0, fraccion)) * 10000)


def _filas_de_snapshot(
    hoy: date,
    resumen: dict[str, Any] | None,
    metricas_por_colegio: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Arma las filas de `metrica_diaria` para hoy a partir de lo leido.

    Funcion pura (sin IO) para poder probar el mapeo de agregados a filas sin
    base de datos ni servicios. El escritor solo la persiste.
    """
    filas: list[dict[str, Any]] = []

    # --- Salud global del catalogo (dimension="catalogo", sin id) ---
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

    # --- Calidad por colegio (dimension="colegio", id=colegio) ---
    # Solo los colegios con actividad real (kits armados): un colegio sin kits
    # tiene cobertura 0 y no aporta traza, y congelar 17 ceros por dia solo
    # engorda la tabla. Los kits solo crecen (cuentan trabajos publicados), asi
    # que un colegio que aparece un dia sigue apareciendo.
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

    # --- Top-line global (dimension="global", sin id) ---
    # La cobertura agregada sobre todo lo comprable de todos los colegios con
    # actividad: la aguja unica que resume "cuanto del kit sabemos comprar hoy".
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


async def escribir_instantanea(
    motor: Any, cliente: ClienteMetricas, hoy: date
) -> dict[str, Any]:
    """Congela el snapshot de `hoy` en `metrica_diaria`, idempotente.

    Devuelve un pequeño reporte (filas escritas, colegios cubiertos, que
    servicios respondieron) para que el CLI lo imprima y las pruebas lo asserten.
    """
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
        # Se reescribe TODO el dia: borrar-e-insertar hace idempotente el
        # recomputo sin depender de un upsert por dialecto (SQLite en pruebas,
        # Postgres en prod). Un solo escritor por sesion, sin concurrencia.
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
