"""Metricas de un colegio, calculadas EN VIVO sobre los trabajos publicados.

El panel del colegio no tenia superficie: nadie contaba cuantos kits se armaron
para sus estudiantes, que cobertura logro el catalogo ni cuanto ahorro la
consolidacion entre hermanos. Aqui nace, y nace calculada sobre las tablas
reales (`trabajo_pipeline`, `kit`, `linea_kit`), no sobre un contador aparte que
se pudiera desincronizar.

El colegio no es una columna: vive dentro del JSON `hijos` de cada trabajo (asi
lo mando el acudiente, `{referencia, colegio_id, grado}`). Por eso el filtro por
colegio se hace en Python sobre los trabajos publicados y no con un `WHERE`
sobre una columna que no existe. Es barato porque solo mira lo publicado, que es
la fraccion util, y el conteo de trabajos de un colegio es de decenas, no de
millones.

Las tres cifras que el panel promete:

- **kits_armados**: cuantos kits recomendados se publicaron para el colegio (uno
  por trabajo suyo que llego a `publicado`).
- **cobertura**: de las lineas que Tukit puede comprar (no informativas), que
  fraccion quedo resuelta con un producto real. Es la promesa de FU-06 medida.
- **ahorro_total_cop**: la suma del `ahorro` que la consolidacion imputo en los
  kits recomendados. Es la razon de que el trabajo sea por hogar.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from .modelos import Base, EstadoResolucion, EstadoTrabajo

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]

# Una linea "resuelta" es la que quedo con un producto real que se puede
# comprar. Las abstenciones del catalogo (ambiguo, sin match, hueco) no cuentan
# como cobertura: son justo lo que la metrica tiene que dejar ver. Es la misma
# definicion de fidelidad que usa `optimizador.medir_objetivos`.
_ESTADOS_RESUELTOS = frozenset({EstadoResolucion.RESUELTO_AUTO.value})


def _colegios_del_trabajo(hijos: list[dict[str, Any]] | None) -> set[str]:
    """Los colegios que aparecen en los hijos de un trabajo. Un hogar puede
    tener hijos en colegios distintos, asi que es un conjunto."""
    colegios: set[str] = set()
    for hijo in hijos or ():
        cid = hijo.get("colegio_id") if isinstance(hijo, dict) else None
        if cid:
            colegios.add(str(cid))
    return colegios


async def metricas_de_colegio(motor: Any, colegio_id: str) -> dict[str, Any]:
    """Las metricas en vivo de un colegio. Cero en todo si no tiene trabajos
    publicados todavia: es una respuesta valida, no un 404."""
    async with motor.sesion() as db:
        conexion = await db.connection()

        publicados = list(
            await conexion.execute(
                select(TRABAJO.c.id, TRABAJO.c.hijos).where(TRABAJO.c.estado == EstadoTrabajo.PUBLICADO.value)
            )
        )
        trabajos_del_colegio = [t.id for t in publicados if colegio_id in _colegios_del_trabajo(t.hijos)]

        if not trabajos_del_colegio:
            return _vacio(colegio_id)

        # El kit recomendado de cada trabajo (uno por trabajo). Si ninguno quedo
        # marcado recomendado, se toma el mas barato como en el resto del
        # servicio; aqui basta con contar por trabajo.
        kits = list(
            await conexion.execute(
                select(KIT.c.id, KIT.c.trabajo_id, KIT.c.recomendado, KIT.c.consolidaciones)
                .where(KIT.c.trabajo_id.in_(trabajos_del_colegio))
                .order_by(KIT.c.trabajo_id, KIT.c.total_cop)
            )
        )
        recomendados = _un_kit_por_trabajo(kits)
        ids_recomendados = [k.id for k in recomendados]

        ahorro = 0
        for k in recomendados:
            for nota in k.consolidaciones or ():
                ahorro += int(nota.get("ahorro", 0) or 0)

        # Cobertura sobre las lineas comprables (no informativas) de los kits
        # recomendados: fraccion resuelta con producto real.
        comprables = 0
        resueltas = 0
        if ids_recomendados:
            lineas = await conexion.execute(
                select(LINEA.c.estado_resolucion, LINEA.c.informativa).where(
                    LINEA.c.kit_id.in_(ids_recomendados)
                )
            )
            for linea in lineas:
                if linea.informativa:
                    continue
                comprables += 1
                if linea.estado_resolucion in _ESTADOS_RESUELTOS:
                    resueltas += 1

    cobertura = round(resueltas / comprables, 4) if comprables else 0.0
    return {
        "colegio_id": colegio_id,
        "kits_armados": len(recomendados),
        "lineas_comprables": comprables,
        "lineas_resueltas": resueltas,
        "cobertura": cobertura,
        "ahorro_total_cop": ahorro,
    }


def _un_kit_por_trabajo(kits: list[Any]) -> list[Any]:
    """Un kit por trabajo: el recomendado si lo hay, si no el primero (mas
    barato, porque la consulta viene ordenada por `total_cop`)."""
    por_trabajo: dict[Any, Any] = {}
    for k in kits:
        actual = por_trabajo.get(k.trabajo_id)
        if actual is None or (k.recomendado and not actual.recomendado):
            por_trabajo[k.trabajo_id] = k
    return list(por_trabajo.values())


def _vacio(colegio_id: str) -> dict[str, Any]:
    return {
        "colegio_id": colegio_id,
        "kits_armados": 0,
        "lineas_comprables": 0,
        "lineas_resueltas": 0,
        "cobertura": 0.0,
        "ahorro_total_cop": 0,
    }
