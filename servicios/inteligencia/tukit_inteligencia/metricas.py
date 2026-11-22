"""Metricas de un colegio, calculadas en vivo sobre los trabajos publicados.

Decisiones:
- Se calculan sobre las tablas reales (`trabajo_pipeline`, `kit`, `linea_kit`) y no sobre un
  contador aparte que pudiera desincronizarse.
- El colegio vive dentro del JSON `hijos` de cada trabajo y no es una columna, asi que el filtro se
  hace en Python sobre lo publicado, que es la fraccion util.
- Cifras: `kits_armados` (uno por trabajo publicado), `cobertura` (fraccion de lineas comprables
  resueltas con un producto real) y `ahorro_total_cop` (la suma del ahorro de la consolidacion).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from .modelos import Base, EstadoResolucion, EstadoTrabajo

TRABAJO = Base.metadata.tables["trabajo_pipeline"]
KIT = Base.metadata.tables["kit"]
LINEA = Base.metadata.tables["linea_kit"]

_ESTADOS_RESUELTOS = frozenset({EstadoResolucion.RESUELTO_AUTO.value})


def _colegios_del_trabajo(hijos: list[dict[str, Any]] | None) -> set[str]:
    colegios: set[str] = set()
    for hijo in hijos or ():
        cid = hijo.get("colegio_id") if isinstance(hijo, dict) else None
        if cid:
            colegios.add(str(cid))
    return colegios


async def metricas_de_colegio(motor: Any, colegio_id: str) -> dict[str, Any]:
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


async def resumen_pedidos_de_colegio(motor: Any, colegio_id: str, cliente_comercio: Any) -> dict[str, Any]:
    pagados = await cliente_comercio.pedidos_pagados()
    dueno_por_trabajo: dict[str, str] = {}
    for pedido in pagados:
        tid = pedido.get("trabajo_id")
        uid = pedido.get("usuario_id")
        if tid and uid:
            dueno_por_trabajo.setdefault(str(tid), str(uid))

    async with motor.sesion() as db:
        conexion = await db.connection()
        trabajos = list(await conexion.execute(select(TRABAJO.c.id, TRABAJO.c.hijos, TRABAJO.c.estado)))

    estados = {
        EstadoTrabajo.ESPERA_REVISION.value: 0,
        EstadoTrabajo.PUBLICADO.value: 0,
        EstadoTrabajo.FALLIDO.value: 0,
    }
    for t in trabajos:
        if colegio_id in _colegios_del_trabajo(t.hijos) and t.estado in estados:
            estados[t.estado] += 1

    por_padre: dict[str, int] = {}
    por_grado: dict[str, dict[str, int]] = {}
    for t in trabajos:
        uid = dueno_por_trabajo.get(str(t.id))
        if uid is None:
            continue
        for hijo in t.hijos or ():
            if not isinstance(hijo, dict) or str(hijo.get("colegio_id")) != colegio_id:
                continue
            por_padre[uid] = por_padre.get(uid, 0) + 1
            grado = str(hijo.get("grado")) if hijo.get("grado") is not None else "—"
            grado_padres = por_grado.setdefault(grado, {})
            grado_padres[uid] = grado_padres.get(uid, 0) + 1

    return {
        "colegio_id": colegio_id,
        "total_padres": len(por_padre),
        "total_ninos": sum(por_padre.values()),
        "por_padre": _lista_padres(por_padre),
        "por_grado": [
            {
                "grado": grado,
                "padres": len(padres),
                "ninos": sum(padres.values()),
                "por_padre": _lista_padres(padres),
            }
            for grado, padres in sorted(por_grado.items())
        ],
        "estados_trabajos": {
            "espera_revision": estados[EstadoTrabajo.ESPERA_REVISION.value],
            "publicado": estados[EstadoTrabajo.PUBLICADO.value],
            "fallido": estados[EstadoTrabajo.FALLIDO.value],
        },
    }


def _lista_padres(por_padre: dict[str, int]) -> list[dict[str, Any]]:
    return [
        {"usuario_id": uid, "ninos": ninos}
        for uid, ninos in sorted(por_padre.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _un_kit_por_trabajo(kits: list[Any]) -> list[Any]:
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
