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


async def resumen_pedidos_de_colegio(motor: Any, colegio_id: str, cliente_comercio: Any) -> dict[str, Any]:
    """El cruce `pedido pagado -> trabajo -> hijos -> padre` de un colegio.

    Comercio es el dueno de "pagado": devuelve por HTTP los pedidos en estado
    confirmado con su `{trabajo_id, usuario_id}` (sin PII). Aqui se cruzan con
    los `hijos` del propio `trabajo_pipeline` (que si tienen colegio y grado) y
    se agrega. Se devuelve solo `usuario_id`, nunca correo: el correo lo resuelve
    el servidor del admin con el endpoint protegido de acudientes.

    Un trabajo cuenta una sola vez aunque tenga varios pedidos pagados (dedupe
    por `trabajo_id`), para no inflar el conteo de ninos con re-pedidos.

    `estados_trabajos` (punto 4) cuenta TODAS las solicitudes de kit del colegio
    -pagadas o no- en los tres estados de negocio; por eso se calcula sobre el
    barrido completo de trabajos y no solo sobre los pagados."""
    pagados = await cliente_comercio.pedidos_pagados()
    dueno_por_trabajo: dict[str, str] = {}
    for pedido in pagados:
        tid = pedido.get("trabajo_id")
        uid = pedido.get("usuario_id")
        if tid and uid:
            dueno_por_trabajo.setdefault(str(tid), str(uid))

    async with motor.sesion() as db:
        conexion = await db.connection()
        trabajos = list(
            await conexion.execute(select(TRABAJO.c.id, TRABAJO.c.hijos, TRABAJO.c.estado))
        )

    # Punto 4: estados de las solicitudes de kit del colegio (todas, no solo pagadas).
    estados = {
        EstadoTrabajo.ESPERA_REVISION.value: 0,
        EstadoTrabajo.PUBLICADO.value: 0,
        EstadoTrabajo.FALLIDO.value: 0,
    }
    for t in trabajos:
        if colegio_id in _colegios_del_trabajo(t.hijos) and t.estado in estados:
            estados[t.estado] += 1

    # Puntos 1-3 y el desglose por grado: solo trabajos pagados, contando los
    # hijos de ESTE colegio, atribuidos al padre que pago.
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
    """La lista `[{usuario_id, ninos}]` ordenada por mas ninos primero y, a
    empate, por id (orden estable, sin depender del insertado)."""
    return [
        {"usuario_id": uid, "ninos": ninos}
        for uid, ninos in sorted(por_padre.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


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
