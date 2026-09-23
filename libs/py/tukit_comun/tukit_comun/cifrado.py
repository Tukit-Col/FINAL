"""Puerto de cifrado en la aplicacion, con un adaptador que no miente.

Existe por una nota concreta del manifiesto sobre `inteligencia`:

    `kit.perfil` y `kit.pesos_usados` son derivados de la encuesta
    socioeconomica, que en Identidad esta cifrada. Aqui vivian EN CLARO.
    Cifrar el origen y dejar el derivado en claro no protege nada.

El modo de fallar que hay que evitar no es "no hay cifrado": es **creer que
lo hay**. Por eso el adaptador por omision se llama `CifradorEnClaro`, dice
en cada arranque que no cifra, y marca el dato con un prefijo legible
(`claro:`) para que nadie confunda un volcado de la base con un secreto bien
guardado. Un adaptador que se llamara `CifradorPorOmision` y devolviera los
bytes tal cual seria peor que ninguno.

El adaptador real es Fernet (`cryptography`), y entra solo si se cumplen las
dos condiciones: la libreria instalada y `TUKIT_LLAVE_CIFRADO` en el entorno.
Ninguna de las dos se asume, porque la integracion continua no instala
`cryptography` y las pruebas de dominio no deben depender de una llave.

    cifrador = cifrador_desde_entorno()
    guardado = cifrador.cifrar_json({"precio": 0.35})
    ...
    pesos = cifrador.descifrar_json(guardado)
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

PREFIJO_EN_CLARO = b"claro:"
VARIABLE_LLAVE = "TUKIT_LLAVE_CIFRADO"


class Cifrador(Protocol):
    """Lo que el dominio necesita: bytes que entran, bytes que salen."""

    nombre: str

    def cifrar(self, datos: bytes) -> bytes: ...

    def descifrar(self, datos: bytes) -> bytes: ...


class _Base:
    nombre = "base"

    def cifrar_json(self, valor: Any) -> bytes:
        return self.cifrar(json.dumps(valor, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    def descifrar_json(self, datos: bytes | None) -> Any:
        if not datos:
            return None
        return json.loads(self.descifrar(datos).decode("utf-8"))

    def cifrar(self, datos: bytes) -> bytes:  # pragma: no cover - lo implementa cada adaptador
        raise NotImplementedError

    def descifrar(self, datos: bytes) -> bytes:  # pragma: no cover
        raise NotImplementedError


class CifradorEnClaro(_Base):
    """NO cifra. Existe para que el desarrollo corra y para que se note.

    El prefijo es la parte importante: hace que el dato guardado sea
    identificable a simple vista en un volcado, asi que migrar a Fernet puede
    saber cuales filas hay que reescribir en vez de adivinarlo.
    """

    nombre = "en_claro"
    cifra_de_verdad = False

    def cifrar(self, datos: bytes) -> bytes:
        return PREFIJO_EN_CLARO + datos

    def descifrar(self, datos: bytes) -> bytes:
        return datos[len(PREFIJO_EN_CLARO) :] if datos.startswith(PREFIJO_EN_CLARO) else datos


class CifradorFernet(_Base):
    """Cifrado simetrico autenticado. El adaptador de verdad."""

    nombre = "fernet"
    cifra_de_verdad = True

    def __init__(self, llave: str) -> None:
        from cryptography.fernet import Fernet

        self._fernet = Fernet(llave)

    def cifrar(self, datos: bytes) -> bytes:
        return self._fernet.encrypt(datos)

    def descifrar(self, datos: bytes) -> bytes:
        # Un dato escrito por `CifradorEnClaro` antes de que hubiera llave no
        # se puede descifrar, pero tampoco se debe perder: se lee tal cual y
        # el prefijo delata de donde viene.
        if datos.startswith(PREFIJO_EN_CLARO):
            return datos[len(PREFIJO_EN_CLARO) :]
        return self._fernet.decrypt(datos)


def cifrador_desde_entorno() -> Cifrador:
    """Fernet si se puede, en claro si no, y en ese caso se avisa."""
    llave = os.environ.get(VARIABLE_LLAVE, "").strip()
    if llave:
        try:
            return CifradorFernet(llave)
        except ImportError:
            print(
                f"[cifrado] {VARIABLE_LLAVE} esta puesta pero `cryptography` no esta instalada: "
                "los datos derivados se guardan EN CLARO."
            )
        except Exception as error:  # llave mal formada
            print(f"[cifrado] la llave de {VARIABLE_LLAVE} no sirve ({error}): se guarda EN CLARO.")
    return CifradorEnClaro()
