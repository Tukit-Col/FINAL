from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from tukit_comun import derivar

_ETIQUETAS = {
    "NOMBRE": "nombre",
    "DANE 12": "dane",
    "SECTOR": "sector",
    "LOCALIDAD": "localidad",
    "DIRECCION": "direccion",
    "TELEFONO": "telefono",
    "EMAIL": "email",
    "WEB": "sitio_web",
    "RECTOR": "rector",
}

_SEPARADOR_MULTIVALOR = "--"


@dataclass(frozen=True)
class ColegioDirectorio:
    dane: str
    nombre: str
    localidad: str | None = None
    sector: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    sitio_web: str | None = None
    rector: str | None = None
    telefonos: tuple[str, ...] = ()
    correos: tuple[str, ...] = ()

    @property
    def id(self) -> uuid.UUID:
        return derivar("colegio", self.dane)

    def a_dict_busqueda(self) -> dict[str, str | None]:
        return {"dane": self.dane, "nombre": self.nombre, "localidad": self.localidad}

    def a_datos_colegio_nuevo(self) -> dict[str, str | None]:
        return {
            "dane": self.dane,
            "nombre": self.nombre,
            "direccion": self.direccion,
            "sitio_web": self.sitio_web,
            "contacto_email": self.email,
            "contacto_telefono": self.telefono,
            "contacto_nombre": self.rector,
        }

    def a_ficha_directorio(self) -> dict[str, Any]:
        return {
            **self.a_datos_colegio_nuevo(),
            "sector": self.sector,
            "localidad": self.localidad,
            "rector": self.rector,
            "telefonos": list(self.telefonos),
            "correos": list(self.correos),
        }


def _limpio(crudo: str | None) -> str | None:
    if crudo is None:
        return None
    return crudo.strip() or None


def _primer_valor(crudo: str) -> str | None:
    return _limpio(crudo.split(_SEPARADOR_MULTIVALOR, 1)[0])


def _todos_valores(crudo: str) -> tuple[str, ...]:
    return tuple(v for parte in crudo.split(_SEPARADOR_MULTIVALOR) if (v := _limpio(parte)))


def _bloque_a_colegio(campos: dict[str, str]) -> ColegioDirectorio | None:
    dane = campos.get("dane")
    nombre = campos.get("nombre")
    if not dane or not nombre:
        return None
    return ColegioDirectorio(
        dane=dane,
        nombre=nombre,
        localidad=_limpio(campos.get("localidad")),
        sector=_limpio(campos.get("sector")),
        direccion=_limpio(campos.get("direccion")),
        telefono=_primer_valor(campos.get("telefono", "")),
        email=_primer_valor(campos.get("email", "")),
        sitio_web=_limpio(campos.get("sitio_web")),
        rector=_limpio(campos.get("rector")),
        telefonos=_todos_valores(campos.get("telefono", "")),
        correos=_todos_valores(campos.get("email", "")),
    )


def parsear_directorio(texto: str) -> list[ColegioDirectorio]:
    colegios: list[ColegioDirectorio] = []
    campos: dict[str, str] = {}

    def cerrar() -> None:
        if campos:
            colegio = _bloque_a_colegio(campos)
            if colegio is not None:
                colegios.append(colegio)
            campos.clear()

    for linea in texto.splitlines():
        if ":" not in linea:
            cerrar()
            continue
        etiqueta_cruda, _, valor = linea.partition(":")
        clave = _ETIQUETAS.get(etiqueta_cruda.strip())
        if clave is None:
            continue
        campos[clave] = valor.strip()

    cerrar()
    return colegios


def generar_json_busqueda(
    texto: str, imagenes: dict[str, str | None] | None = None
) -> list[dict[str, str | None]]:
    colegios = parsear_directorio(texto)
    colegios.sort(key=lambda c: c.nombre)
    imagenes = imagenes or {}
    return [{**c.a_dict_busqueda(), "imageURL": imagenes.get(c.dane)} for c in colegios]


_POR_DANE: dict[str, ColegioDirectorio] | None = None
_FUENTE = "datos/colegios_bogota.txt"


def _indice_por_dane() -> dict[str, ColegioDirectorio]:
    global _POR_DANE
    if _POR_DANE is None:
        from pathlib import Path

        ruta = Path(__file__).parent.parent / _FUENTE
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        _POR_DANE = {c.dane: c for c in parsear_directorio(texto)}
    return _POR_DANE


def datos_colegio_nuevo_por_dane(dane: str) -> dict[str, str | None] | None:
    colegio = _indice_por_dane().get(dane)
    return colegio.a_datos_colegio_nuevo() if colegio is not None else None


def ficha_directorio_por_dane(dane: str) -> dict[str, Any] | None:
    colegio = _indice_por_dane().get(dane)
    return colegio.a_ficha_directorio() if colegio is not None else None


def _main() -> None:
    """Uso: python -m tukit_identidad.dominio.directorio <fuente.txt> <destino.json>

    Parsea el volcado DUEB y escribe el JSON de busqueda que sirven las apps
    (`libs/ts/tukit-contrato/datos/directorio-colegios.json`). Si el destino ya
    existe, conserva el `imageURL` curado de cada DANE. Es una herramienta de
    datos, no parte del servicio: se corre cuando el directorio fuente cambia,
    no en cada arranque.
    """
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) != 3:
        print(_main.__doc__)
        raise SystemExit(2)
    fuente, destino = Path(sys.argv[1]), Path(sys.argv[2])
    imagenes: dict[str, str | None] = {}
    if destino.exists():
        imagenes = {r["dane"]: r.get("imageURL") for r in json.loads(destino.read_text(encoding="utf-8"))}
    registros = generar_json_busqueda(fuente.read_text(encoding="utf-8", errors="replace"), imagenes)
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(registros)} colegios -> {destino}")


if __name__ == "__main__":
    _main()


__all__ = ["ColegioDirectorio", "generar_json_busqueda", "parsear_directorio"]
