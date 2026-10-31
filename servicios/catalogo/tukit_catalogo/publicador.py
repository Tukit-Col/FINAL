"""El publicador de la bandeja de Catalogo en RabbitMQ (ADR 0046).

Con `RABBITMQ_URL`, los eventos de la bandeja de Catalogo (`colegio_verificado`,
`lista_verificada` y `lista_aprobada`) salen de aqui hacia el exchange
`tukit.eventos`, con confirmacion del publicador. Sin broker no arranca: los
sondeadores de Identidad y de Inteligencia siguen leyendo esta bandeja.

    python -m tukit_catalogo.publicador            # hasta vaciar la bandeja
    python -m tukit_catalogo.publicador --seguir   # bucle

La logica vive en `tukit_comun.publicador`; aqui solo se dice de que base sale.
"""

from __future__ import annotations

from tukit_comun.publicador import main_publicador


def main(argv: list[str] | None = None) -> int:
    return main_publicador("catalogo", argv)


if __name__ == "__main__":
    raise SystemExit(main())
