"""El barrido de solicitudes de supresion atascadas en `propagando` (ADR 0048).

`suprimir_titular` deja la solicitud en `propagando` y escribe `titular_suprimido`
en la bandeja; la solicitud solo pasa a `completada` cuando confirman Comercio,
Operacion e Inteligencia. Si un servicio estuvo caido, perdio el mensaje o su
confirmacion nunca llego, la solicitud se queda ahi sin que nadie lo note: el
titular ya fue anonimizado en Identidad pero sus datos siguen en otra base. Este
barrido es el que lo hace visible y lo intenta arreglar.

Hace dos cosas, cada una con su propio umbral:

1. **Reenvia.** Si pasaron `--reenviar-tras` horas desde el ultimo envio y falta
   algun servicio, escribe otro `titular_suprimido` en la bandeja de Identidad
   (el publicador comun lo lleva al broker). Es seguro repetirlo: cada servicio
   enmascara lo ya enmascarado sin cambiar nada y `anotar_confirmacion` no deja
   una segunda confirmacion. El evento sale por el exchange de topico y llega a
   las tres colas; no se puede dirigir a un solo servicio, asi que "reenviar a
   los que faltan" significa que los que ya confirmaron lo reciben y lo ignoran.
   La carga lleva `pendientes` y `reenvio` solo para diagnostico.
2. **Alerta del plazo legal.** Pasados 15 dias habiles desde el recibo, deja un
   log de nivel ERROR y suma la metrica `tukit.supresion.atascadas{motivo=vencida}`.
   Ese plazo es el del reclamo del titular (Ley 1581 de 2012, art. 15), el mismo
   que la politica de privacidad publica en `/legal/privacidad`: "un reclamo en
   maximo 15 dias habiles". El repo solo dice los 15 dias habiles; que se cuenten
   desde el dia siguiente al recibo es el texto de la ley, no algo que el repo
   documente, y de ahi sale `vence_el`.

No cierra ni marca `fallida` ninguna solicitud: declarar fallida una supresion
es una decision de una persona, no de un cron. El ADR 0048 lo deja como pendiente
y este barrido solo lo avisa.

Los dias habiles aqui son lunes a viernes, sin festivos. Es a proposito: Comercio
tiene el calendario de festivos de Colombia (`ley1480.py`) pero Identidad no puede
importar a otro servicio, y ignorar un festivo adelanta la alerta uno o dos dias,
nunca la retrasa. Para una alerta es el lado correcto del error.

    python -m tukit_identidad.barrido_supresion           # una pasada
    python -m tukit_identidad.barrido_supresion --seguir  # bucle

No necesita broker: solo lee y escribe la base de Identidad.
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

# Ley 1581 de 2012, art. 15: el reclamo se atiende en maximo 15 dias habiles.
PLAZO_DIAS_HABILES = 15
# La propagacion normal tarda segundos. Una hora sin cerrarse ya no es lentitud
# del broker; es un servicio caido o un mensaje perdido. Es un valor operativo
# nuestro, no un plazo legal.
REENVIAR_TRAS_POR_OMISION = timedelta(hours=1)
# Tope de reenvios por solicitud: si 24 envios (un dia a razon de uno por hora)
# no la cerraron, seguir llenando la bandeja no la va a arreglar; queda la alerta.
MAX_REENVIOS = 24
_BOGOTA = ZoneInfo("America/Bogota")


def vence_el(recibida: datetime) -> date:
    """Ultimo dia del plazo: 15 dias habiles contados desde el dia siguiente al recibo."""
    dia = _con_zona(recibida).astimezone(_BOGOTA).date()
    contados = 0
    while contados < PLAZO_DIAS_HABILES:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            contados += 1
    return dia


def _con_zona(momento: datetime) -> datetime:
    # SQLite devuelve la fecha sin zona; en Postgres ya viene con ella.
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)


@dataclass
class Reporte:
    """Lo que una pasada encontro, para el log y para las pruebas."""

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
    """Una pasada sobre las solicitudes en `propagando`. Idempotente.

    `ya_avisadas` lo guarda quien corre en bucle: una solicitud vencida se avisa
    (log ERROR y metrica) la primera vez que se ve y no en cada pasada. Sin eso,
    una sola solicitud sin cerrar sumaria ~96 alertas al dia con el intervalo por
    omision y la metrica contaria pasadas, no solicitudes. `reporte.vencidas`
    sigue listando todas las vencidas de la pasada. Sin el conjunto (una pasada
    suelta) siempre se avisa.
    """
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
                # Confirmaron los tres pero el cierre no corrio: lo cierra el
                # proceso de confirmaciones, no este. Se avisa y no se toca.
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
                # El ultimo envio ni siquiera salio de la bandeja: el publicador
                # esta parado o sin broker. Otro envio solo acumularia copias.
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
                    # La misma carga que escribe `suprimir_titular`, mas dos
                    # campos de diagnostico que los consumidores ignoran.
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
    # Un motor por pasada: si Postgres se cayo, la siguiente reconecta sola.
    motor = crear_motor("identidad")
    try:
        return await barrer(motor, reenviar_tras=reenviar_tras, ya_avisadas=ya_avisadas)
    finally:
        await motor.cerrar()


async def _bucle(intervalo: float, reenviar_tras: timedelta) -> None:
    # Vive lo que viva el bucle: un reinicio vuelve a avisar una vez, que es
    # preferible a callar una vencida que nadie ha cerrado.
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
