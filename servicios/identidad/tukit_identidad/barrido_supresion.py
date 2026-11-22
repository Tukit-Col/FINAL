"""Barrido de solicitudes de supresion atascadas en `propagando`.

Decisiones:
- Reenvia `titular_suprimido` si pasaron `--reenviar-tras` horas desde el ultimo envio y falta algun
  servicio. Es seguro repetirlo: cada servicio enmascara lo ya enmascarado y no se registra una
  segunda confirmacion. El evento va por el exchange de topico a las tres colas, asi que los que ya
  confirmaron lo reciben y lo ignoran.
- Deja una alerta cuando se vence el plazo legal de 15 dias habiles desde el recibo.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from tukit_comun import metricas
from tukit_comun.bd import MotorServicio, crear_motor
from tukit_comun.http import iso
from tukit_comun.registro import configurar_registro
from tukit_comun.resiliencia import bucle_resiliente
from tukit_comun.supresion import SUSCRIPTORES_SUPRESION, TITULAR_SUPRIMIDO

from .modelos import BandejaSalida, SolicitudSupresion

log = logging.getLogger(__name__)

PLAZO_DIAS_HABILES = 15
REENVIAR_TRAS_POR_OMISION = timedelta(hours=1)
MAX_REENVIOS = 24
_BOGOTA = ZoneInfo("America/Bogota")


def vence_el(recibida: datetime) -> date:
    dia = _con_zona(recibida).astimezone(_BOGOTA).date()
    contados = 0
    while contados < PLAZO_DIAS_HABILES:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            contados += 1
    return dia


def _con_zona(momento: datetime) -> datetime:
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)


@dataclass
class Reporte:
    revisadas: int = 0
    reenviadas: list[str] = field(default_factory=list)
    vencidas: list[str] = field(default_factory=list)
    sin_publicar: list[str] = field(default_factory=list)
    sin_reenvios: list[str] = field(default_factory=list)


async def barrer(
    motor: MotorServicio,
    *,
    ahora: datetime | None = None,
    reenviar_tras: timedelta = REENVIAR_TRAS_POR_OMISION,
    max_reenvios: int = MAX_REENVIOS,
    ya_avisadas: set[str] | None = None,
) -> Reporte:
    ahora = ahora or datetime.now(UTC)
    reporte = Reporte()
    nuevas_vencidas = 0
    async with motor.sesion() as db:
        solicitudes = (
            (
                await db.execute(
                    select(SolicitudSupresion)
                    .where(SolicitudSupresion.estado == "propagando")
                    .order_by(SolicitudSupresion.creado_en)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for solicitud in solicitudes:
            reporte.revisadas += 1
            id_ = str(solicitud.id)
            faltan = sorted(SUSCRIPTORES_SUPRESION - set(solicitud.suscriptores_confirmados))
            if not faltan:
                log.warning("supresion solicitud=%s tiene las tres confirmaciones y sigue en propagando", id_)
                continue

            if ahora.astimezone(_BOGOTA).date() > vence_el(solicitud.creado_en):
                reporte.vencidas.append(id_)
                if ya_avisadas is None or id_ not in ya_avisadas:
                    nuevas_vencidas += 1
                    if ya_avisadas is not None:
                        ya_avisadas.add(id_)
                    log.error(
                        "supresion vencida solicitud=%s recibida=%s plazo_dias_habiles=%d faltan=%s",
                        id_,
                        iso(_con_zona(solicitud.creado_en)),
                        PLAZO_DIAS_HABILES,
                        ",".join(faltan),
                    )

            envios = (
                await db.execute(
                    select(BandejaSalida.creado_en, BandejaSalida.publicado_en)
                    .where(BandejaSalida.tipo == TITULAR_SUPRIMIDO, BandejaSalida.agregado_id == solicitud.id)
                    .order_by(BandejaSalida.id.desc())
                )
            ).all()
            if envios and envios[0].publicado_en is None:
                reporte.sin_publicar.append(id_)
                log.warning("supresion solicitud=%s tiene un envio sin publicar; no se reenvia", id_)
                continue
            ultimo = _con_zona(envios[0].creado_en) if envios else _con_zona(solicitud.creado_en)
            if ahora - ultimo < reenviar_tras:
                continue
            if len(envios) > max_reenvios:
                reporte.sin_reenvios.append(id_)
                log.error("supresion solicitud=%s agoto %d reenvios sin cerrarse", id_, max_reenvios)
                continue

            db.add(
                BandejaSalida(
                    tipo=TITULAR_SUPRIMIDO,
                    agregado_tipo="solicitud_supresion",
                    agregado_id=solicitud.id,
                    carga={
                        "usuario_id": str(solicitud.usuario_id),
                        "solicitud_id": id_,
                        "suprimido_en": iso(_con_zona(solicitud.creado_en)),
                        "reenvio": len(envios),
                        "pendientes": faltan,
                    },
                    creado_en=ahora,
                )
            )
            reporte.reenviadas.append(id_)
            log.warning(
                "supresion atascada solicitud=%s reenvio=%d faltan=%s", id_, len(envios), ",".join(faltan)
            )

    metricas.contar_supresion_atascada("reenviada", len(reporte.reenviadas))
    metricas.contar_supresion_atascada("vencida", nuevas_vencidas)
    if reporte.revisadas:
        log.info(
            "supresion barrido revisadas=%d reenviadas=%d vencidas=%d",
            reporte.revisadas,
            len(reporte.reenviadas),
            len(reporte.vencidas),
        )
    return reporte


async def correr_una_vez(reenviar_tras: timedelta, ya_avisadas: set[str] | None = None) -> Reporte:
    motor = crear_motor("identidad")
    try:
        return await barrer(motor, reenviar_tras=reenviar_tras, ya_avisadas=ya_avisadas)
    finally:
        await motor.cerrar()


async def _bucle(intervalo: float, reenviar_tras: timedelta) -> None:
    ya_avisadas: set[str] = set()

    async def _vuelta() -> None:
        await correr_una_vez(reenviar_tras, ya_avisadas)

    await bucle_resiliente(_vuelta, intervalo=intervalo, proceso="identidad-barrido-supresion")


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description="Reenvia y avisa de las solicitudes de supresion atascadas en propagando."
    )
    analizador.add_argument("--seguir", action="store_true", help="Corre en bucle en vez de una pasada.")
    analizador.add_argument("--intervalo", type=float, default=900.0, help="Segundos entre pasadas.")
    analizador.add_argument(
        "--reenviar-tras",
        type=float,
        default=REENVIAR_TRAS_POR_OMISION.total_seconds() / 3600,
        help="Horas sin cerrarse antes de reenviar el evento.",
    )
    argumentos = analizador.parse_args(argv)
    configurar_registro("identidad-barrido-supresion")
    reenviar_tras = timedelta(hours=argumentos.reenviar_tras)
    if argumentos.seguir:
        asyncio.run(_bucle(argumentos.intervalo, reenviar_tras))
        return 0
    reporte = asyncio.run(correr_una_vez(reenviar_tras))
    print(
        f"[barrido-supresion] revisadas={reporte.revisadas} reenviadas={len(reporte.reenviadas)} "
        f"vencidas={len(reporte.vencidas)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["PLAZO_DIAS_HABILES", "Reporte", "barrer", "main", "vence_el"]
