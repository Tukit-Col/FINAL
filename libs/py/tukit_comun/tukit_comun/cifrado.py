"""Puerto de cifrado con un adaptador que no miente.

Decisiones:
- El fallo a evitar es creer que hay cifrado. El adaptador por omision es `CifradorEnClaro`: avisa
  en cada arranque que no cifra y marca el dato con el prefijo `claro:`.
- El adaptador real (Fernet) entra solo si estan la libreria `cryptography` y
  `TUKIT_LLAVE_CIFRADO`; ninguna de las dos se asume.
- Con `TUKIT_ENTORNO=produccion` caer en claro hace fallar el arranque.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .entorno import exigir_en_produccion

PREFIJO_EN_CLARO = b"claro:"
VARIABLE_LLAVE = "TUKIT_LLAVE_CIFRADO"


class Cifrador(Protocol):
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
    nombre = "en_claro"
    cifra_de_verdad = False

    def cifrar(self, datos: bytes) -> bytes:
        return PREFIJO_EN_CLARO + datos

    def descifrar(self, datos: bytes) -> bytes:
        return datos[len(PREFIJO_EN_CLARO) :] if datos.startswith(PREFIJO_EN_CLARO) else datos


class CifradorFernet(_Base):
    nombre = "fernet"
    cifra_de_verdad = True

    def __init__(self, llave: str) -> None:
        from cryptography.fernet import Fernet

        self._fernet = Fernet(llave)

    def cifrar(self, datos: bytes) -> bytes:
        cifrado: bytes = self._fernet.encrypt(datos)
        return cifrado

    def descifrar(self, datos: bytes) -> bytes:
        if datos.startswith(PREFIJO_EN_CLARO):
            return datos[len(PREFIJO_EN_CLARO) :]
        claro: bytes = self._fernet.decrypt(datos)
        return claro


def cifrador_desde_entorno() -> Cifrador:
    llave = os.environ.get(VARIABLE_LLAVE, "").strip()
    exigir_en_produccion(bool(llave), f"falta {VARIABLE_LLAVE}; los datos se guardarian en claro.")
    if llave:
        try:
            return CifradorFernet(llave)
        except ImportError:
            exigir_en_produccion(False, "`cryptography` no esta instalada; los datos se guardarian en claro.")
            print(
                f"[cifrado] {VARIABLE_LLAVE} esta puesta pero `cryptography` no esta instalada: "
                "los datos derivados se guardan EN CLARO."
            )
        except Exception as error:
            exigir_en_produccion(False, f"la llave de {VARIABLE_LLAVE} no sirve ({error}).")
            print(f"[cifrado] la llave de {VARIABLE_LLAVE} no sirve ({error}): se guarda EN CLARO.")
    elif VARIABLE_LLAVE not in os.environ:
        # Sin llave el sistema funciona pero no cifra: hay que decirlo, no dejar creer que cifra (H-A-03).
        print(f"[cifrado] {VARIABLE_LLAVE} no esta puesta: los datos derivados se guardan EN CLARO.")
    return CifradorEnClaro()
