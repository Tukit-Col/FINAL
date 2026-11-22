from __future__ import annotations

from tukit_comun.publicador import main_publicador


def main(argv: list[str] | None = None) -> int:
    return main_publicador("comercio", argv)


if __name__ == "__main__":
    raise SystemExit(main())
