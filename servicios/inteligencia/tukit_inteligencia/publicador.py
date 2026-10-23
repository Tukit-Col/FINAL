"""El publicador de la bandeja de Inteligencia en RabbitMQ (ADR 0046).

Con `RABBITMQ_URL`, los eventos de la bandeja de Inteligencia (`kits_publicados`,
`trabajo_encolado` y `pedido_solicitado`, que nadie consume todavia) salen de
aqui hacia el exchange `tukit.eventos`, con confirmacion del publicador. Sin
broker no arranca: el repartidor de Operacion sigue leyendo esta bandeja y el
trabajador sigue sondeando `trabajo_pipeline`.

    python -m tukit_inteligencia.publicador            # hasta vaciar la bandeja
    python -m tukit_inteligencia.publicador --seguir   # bucle

La logica vive en `tukit_comun.publicador`; aqui solo se dice de que base sale.
"""

from __future__ import annotations

from tukit_comun.publicador import main_publicador


def main(argv: list[str] | None = None) -> int:
    return main_publicador("inteligencia", argv)


if __name__ == "__main__":
    raise SystemExit(main())
