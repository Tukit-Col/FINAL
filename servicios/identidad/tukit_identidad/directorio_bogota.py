"""El directorio DUEB de Bogota: 3169 colegios como referencia buscable.

No es data sembrada. Es el catalogo de colegios que EXISTEN en Bogota, para
que un acudiente los busque en `/empezar` al subir su lista aunque Tukit
todavia no conozca el suyo. El colegio nace de verdad —en Identidad— cuando un
administrador aprueba en la cola la lista que el acudiente subio; hasta
entonces el directorio solo sirve para elegir y para pre-llenar los datos que
el revisor completa.

La pieza que hace que todo cruce es el identificador. La lista se guarda en
Catalogo apuntando a `derivar("colegio", dane)` ANTES de que el colegio exista;
al aprobar, Identidad crea el colegio con ese MISMO UUID. Por eso el id se
deriva aqui con el contrato compartido `tukit_comun.derivar` y de nada mas: el
codigo DANE es la llave natural del colegio en las dos puntas.

El formato fuente es un volcado de texto por bloques (una etiqueta por linea,
`ETIQUETA : valor`), separados por lineas en blanco. Se parsea a `ColegioDirectorio`
y de ahi a un JSON compacto que el web app sirve y busca en el cliente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from tukit_comun import derivar

# Las etiquetas del volcado DUEB. Se listan para no adivinar: una linea que no
# empiece por una de estas es ruido de cabecera (titulo, fuente, separadores).
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

# Telefono y email traen varios valores separados asi; el primero es el principal.
_SEPARADOR_MULTIVALOR = "--"


@dataclass(frozen=True)
class ColegioDirectorio:
    """Un colegio del directorio, con lo que el directorio provee.

    El `logo_url` no vive aqui a proposito: el directorio DUEB no trae logo, y
    es justo el dato que el revisor completa a mano antes de aprobar para que
    la identidad del colegio nazca completa.
    """

    dane: str
    nombre: str
    localidad: str | None = None
    sector: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    sitio_web: str | None = None
    rector: str | None = None

    @property
    def id(self) -> uuid.UUID:
        """El UUID del colegio, derivado del DANE con el contrato compartido.

        El mismo que Catalogo usa para la lista y que Identidad usara al crear
        el colegio. No es un detalle de implementacion: es LA referencia entre
        las dos bases.
        """
        return derivar("colegio", self.dane)

    def a_dict_busqueda(self) -> dict[str, str | None]:
        """Lo minimo que el buscador de `/empezar` necesita: filtra por nombre
        y localidad, y manda el dane al subir. El UUID lo deriva el backend; el
        resto de campos los pre-llena el revisor desde el directorio completo."""
        return {"dane": self.dane, "nombre": self.nombre, "localidad": self.localidad}

    def a_datos_colegio_nuevo(self) -> dict[str, str | None]:
        """El bloque con que la cola pre-llena el perfil del colegio nuevo
        (`DatosColegioNuevo`). Mapea los campos del DUEB a los del formulario:
        el `rector` va a `contacto_nombre` (la secretaria/contacto institucional
        que el revisor puede corregir), y no hay `logo_url` porque el DUEB no lo
        trae —ese lo completa el revisor a mano, como dice `CompletarColegio`."""
        return {
            "dane": self.dane,
            "nombre": self.nombre,
            "direccion": self.direccion,
            "sitio_web": self.sitio_web,
            "contacto_email": self.email,
            "contacto_telefono": self.telefono,
            "contacto_nombre": self.rector,
        }


def _limpio(crudo: str | None) -> str | None:
    """El valor recortado, o None si quedo vacio: en el volcado un campo
    ausente aparece como `WEB       :` sin nada, no como linea faltante."""
    if crudo is None:
        return None
    return crudo.strip() or None


def _primer_valor(crudo: str) -> str | None:
    """El valor principal de un campo que puede traer varios (`a -- b -- c`)."""
    return _limpio(crudo.split(_SEPARADOR_MULTIVALOR, 1)[0])


def _bloque_a_colegio(campos: dict[str, str]) -> ColegioDirectorio | None:
    """Un bloque parseado a colegio. Sin DANE no hay identificador estable, asi
    que ese bloque se descarta: no se podria crear el colegio de forma
    idempotente ni cruzar su lista."""
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
    )


def parsear_directorio(texto: str) -> list[ColegioDirectorio]:
    """Parsea el volcado DUEB a registros de colegio.

    Un bloque es una racha de lineas `ETIQUETA : valor`; una linea en blanco lo
    cierra. Las lineas que no empiezan por una etiqueta conocida (titulo,
    fuente, separadores) se ignoran, asi que la cabecera del archivo no ensucia.
    """
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


def generar_json_busqueda(texto: str) -> list[dict[str, str | None]]:
    """El arreglo que el web app sirve: un dict de busqueda por colegio,
    ordenado por nombre para que el buscador de `/empezar` no tenga que hacerlo."""
    colegios = parsear_directorio(texto)
    colegios.sort(key=lambda c: c.nombre)
    return [c.a_dict_busqueda() for c in colegios]


# --------------------------------------------------------------- lookup por DANE

# El volcado DUEB vive junto al modulo (no en `datos/`, que es data sembrable):
# es una referencia externa fija, no algo que el pipeline genere. Se parsea una
# vez y se indexa por DANE. `None` hasta el primer uso: un servicio que nunca
# resuelve un colegio nuevo no paga el parseo de 3169 bloques.
_POR_DANE: dict[str, ColegioDirectorio] | None = None
_FUENTE = "datos/colegios_bogota.txt"


def _indice_por_dane() -> dict[str, ColegioDirectorio]:
    global _POR_DANE
    if _POR_DANE is None:
        from pathlib import Path

        ruta = Path(__file__).parent / _FUENTE
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        _POR_DANE = {c.dane: c for c in parsear_directorio(texto)}
    return _POR_DANE


def datos_colegio_nuevo_por_dane(dane: str) -> dict[str, str | None] | None:
    """Los datos del DUEB para pre-llenar el perfil del colegio nuevo, o `None`
    si el DANE no esta en el directorio (colegio escrito a mano, otra ciudad).
    Es lo que Identidad expone para que la subida enriquezca `colegio_datos`."""
    colegio = _indice_por_dane().get(dane)
    return colegio.a_datos_colegio_nuevo() if colegio is not None else None


def _main() -> None:
    """Uso: python -m tukit_identidad.directorio_bogota <fuente.txt> <destino.json>

    Parsea el volcado DUEB y escribe el JSON de busqueda que el web app sirve.
    Es una herramienta de datos, no parte del servicio: se corre cuando el
    directorio fuente cambia, no en cada arranque.
    """
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) != 3:
        print(_main.__doc__)
        raise SystemExit(2)
    fuente, destino = Path(sys.argv[1]), Path(sys.argv[2])
    registros = generar_json_busqueda(fuente.read_text(encoding="utf-8", errors="replace"))
    destino.write_text(json.dumps(registros, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(registros)} colegios -> {destino}")


if __name__ == "__main__":
    _main()


__all__ = ["ColegioDirectorio", "generar_json_busqueda", "parsear_directorio"]
