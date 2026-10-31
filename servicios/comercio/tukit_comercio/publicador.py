"""El publicador de la bandeja de Comercio en RabbitMQ (ADR 0046).

Con `RABBITMQ_URL`, los eventos de la bandeja de Comercio (`pedido_pagado`,
`incidencia` y los cambios de estado del despacho) salen de aqui hacia el
exchange `tukit.eventos`, con confirmacion del publicador. Sin broker no
arranca: el repartidor de Operacion sigue leyendo esta bandeja.

    python -m tukit_comercio.publicador            # hasta vaciar la bandeja
    python -m tukit_comercio.publicador --seguir   # bucle

La logica vive en `tukit_comun.publicador`; aqui solo se dice de que base sale.
"""

from __future__ import annotations

from tukit_comun.publicador import main_publicador


def main(argv: list[str] | None = None) -> int:
    return main_publicador("comercio", argv)


if __name__ == "__main__":
    raise SystemExit(main())
