"""El publicador de la bandeja de Identidad en RabbitMQ (ADR 0046, ADR 0048).

Con `RABBITMQ_URL`, `titular_suprimido` sale de aqui hacia el exchange
`tukit.eventos`, con confirmacion del publicador, y llega a las colas de
supresion de Comercio, Operacion e Inteligencia. Sin broker no arranca.

    python -m tukit_identidad.publicador            # hasta vaciar la bandeja
    python -m tukit_identidad.publicador --seguir   # bucle

La logica vive en `tukit_comun.publicador`; aqui solo se dice de que base sale.
"""

from __future__ import annotations

from tukit_comun.publicador import main_publicador


def main(argv: list[str] | None = None) -> int:
    return main_publicador("identidad", argv)


if __name__ == "__main__":
    raise SystemExit(main())
