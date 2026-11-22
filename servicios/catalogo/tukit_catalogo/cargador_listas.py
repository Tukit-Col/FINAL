"""Siembra las listas oficiales de los colegios del corpus.

Decisiones:
- La version nace sin revisar (`revisada_en` nulo): una version sin revisar es la que habilita el
  descubrimiento y una vez cerrada no se reabre, asi que sembrarla revisada la dejaria muerta.
- Un renglon sin concepto no se fuerza al mas parecido: por debajo de 0,5 de parecido queda
  `concepto_id` nulo y `requiere_revision` en verdadero. El informe cuenta cuantos quedaron asi,
  porque ese numero mide cuanto del corpus no cubre el vocabulario todavia.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tukit_comun import derivar

from .clasificacion import clasificar
from .modelos.base import MODOS_SURTIBLES, ModoAdquisicion, TipoItem

ANIO_POR_OMISION = 2026

UMBRAL_CONCEPTO = 0.5

MODOS_VALIDOS = frozenset(m.value for m in ModoAdquisicion)
TIPOS_VALIDOS = frozenset(t.value for t in TipoItem)
VALORES_SURTIBLES = frozenset(m.value for m in MODOS_SURTIBLES)

INSTRUCCION_POR_MODO: dict[str, str] = {
    "plataforma": (
        "El colegio indica que se adquiere por plataforma externa. "
        "Sigue el enlace o las instrucciones que el colegio publico en su lista."
    ),
    "venta_directa_editorial": (
        "El colegio indica que la editorial lo vende directamente a las familias, "
        "por lo general en una jornada de venta en el plantel."
    ),
    "edicion_exclusiva": (
        "El colegio indica que es una edicion exclusiva para la institucion: "
        "solo se consigue por el canal que el colegio senale."
    ),
    "diferido": (
        "El colegio indica que se pide mas adelante en el ano lectivo. Todavia no hay que comprarlo."
    ),
}

FILAS_POR_BLOQUE = 400


@dataclass(frozen=True)
class Problema:

    bloqueante: bool
    clase: str
    detalle: str

    def __str__(self) -> str:
        marca = "BLOQUEA" if self.bloqueante else "carencia"
        return f"[{marca}] {self.clase}: {self.detalle}"


@dataclass
class Informe:

    escritos: dict[str, int] = field(default_factory=dict)
    problemas: list[Problema] = field(default_factory=list)
    carencias: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def bloqueado(self) -> bool:
        return any(p.bloqueante for p in self.problemas)

    def imprimir(self) -> None:
        print("\n=== sembrado ===")
        for tabla, n in self.escritos.items():
            print(f"  {tabla:24} {n:5}")

        bloqueantes = [p for p in self.problemas if p.bloqueante]
        if bloqueantes:
            print(f"\n=== {len(bloqueantes)} problema(s) que BLOQUEAN ===")
            for p in bloqueantes[:20]:
                print(f"  {p}")
            if len(bloqueantes) > 20:
                print(f"  ... y {len(bloqueantes) - 20} mas")

        if self.carencias:
            print("\n=== lo que falta para poder mostrarlo a un papa ===")
            for que, (faltan, total) in sorted(self.carencias.items()):
                pct = 100 * faltan / total if total else 0
                print(f"  {que:38} {faltan:5}/{total:<5} ({pct:.0f}%)")

        otros = [p for p in self.problemas if not p.bloqueante]
        if otros:
            print(f"\n=== {len(otros)} carencia(s) con nombre propio ===")
            for p in otros[:15]:
                print(f"  {p}")
            if len(otros) > 15:
                print(f"  ... y {len(otros) - 15} mas")


def id_colegio(codigo: str) -> uuid.UUID:
    return derivar("colegio", codigo)


def id_sede(codigo: str, sede_nombre: str) -> uuid.UUID:
    return derivar("sede", codigo, sede_nombre)


def id_lista(codigo: str, grado: str, anio: int) -> uuid.UUID:
    return derivar("lista", codigo, grado, str(anio))


def id_version(codigo: str, grado: str, anio: int, numero: int = 1) -> uuid.UUID:
    return derivar("version_lista", codigo, grado, str(anio), str(numero))


def id_item(codigo: str, grado: str, orden: int) -> uuid.UUID:
    return derivar("item_lista", codigo, grado, str(orden))


def normalizar_modo(crudo: str | None) -> str:
    limpio = (crudo or "").strip()
    if not limpio or limpio not in MODOS_VALIDOS:
        return ModoAdquisicion.MERCADO_ABIERTO.value
    return limpio


def normalizar_tipo(crudo: str | None) -> str | None:
    limpio = (crudo or "").strip()
    return limpio if limpio in TIPOS_VALIDOS else None


def cantidad_valida(crudo: str | None) -> int:
    try:
        cantidad = int(float((crudo or "").strip()))
    except ValueError:
        return 1
    return cantidad if cantidad > 0 else 1


def instruccion_para(modo: str, declarada: str | None) -> str | None:
    texto = (declarada or "").strip()
    if texto:
        return texto
    if modo in VALORES_SURTIBLES:
        return None
    return INSTRUCCION_POR_MODO.get(
        modo, "El colegio indica que este renglon no se compra en el mercado abierto."
    )


def _texto(crudo: str | None) -> str | None:
    limpio = (crudo or "").strip()
    return limpio or None


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Cargador:
    def __init__(self, directorio: Path, anio: int = ANIO_POR_OMISION) -> None:
        self.dir = directorio
        self.anio = anio
        self.problemas: list[Problema] = []
        self.carencias: dict[str, tuple[int, int]] = {}
        self.sin_concepto = 0
        self.total_items = 0

    def armar(self, conceptos: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        sedes = self._sedes()
        filas = leer_csv(self.dir / "items_lista.csv")
        if not filas:
            self.problemas.append(
                Problema(True, "datos", f"no hay items_lista.csv en {self.dir} o esta vacio")
            )
            return {"lista_oficial": [], "version_lista_oficial": [], "item_lista_oficial": []}

        listas: dict[tuple[str, str], dict[str, Any]] = {}
        versiones: dict[tuple[str, str], dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        ordenes: set[tuple[str, str, int]] = set()
        resueltos: dict[str, tuple[uuid.UUID | None, float]] = {}

        for numero, fila in enumerate(filas, start=2):
            codigo = (fila.get("colegio_codigo") or "").strip()
            grado = (fila.get("grado") or "").strip()
            texto = (fila.get("texto_original") or "").strip()
            if not codigo or not grado or not texto:
                self.problemas.append(Problema(True, "fila", f"fila {numero}: falta colegio, grado o texto"))
                continue
            if codigo not in sedes:
                self.problemas.append(
                    Problema(True, "colegio", f"fila {numero}: `{codigo}` no esta en colegios.csv")
                )
                continue

            try:
                orden = int((fila.get("orden") or "").strip())
            except ValueError:
                self.problemas.append(Problema(True, "orden", f"fila {numero}: orden no numerico"))
                continue
            if (codigo, grado, orden) in ordenes:
                self.problemas.append(
                    Problema(True, "orden", f"fila {numero}: {codigo} {grado} repite el orden {orden}")
                )
                continue
            ordenes.add((codigo, grado, orden))

            clave = (codigo, grado)
            if clave not in listas:
                listas[clave] = {
                    "id": id_lista(codigo, grado, self.anio),
                    "colegio_id": id_colegio(codigo),
                    "sede_id": id_sede(codigo, sedes[codigo]),
                    "grado": grado,
                    "anio_lectivo": self.anio,
                    "activa": True,
                }
                versiones[clave] = {
                    "id": id_version(codigo, grado, self.anio),
                    "lista_id": listas[clave]["id"],
                    "numero": 1,
                    "contenido_redactado": None,
                    "hash_origen": None,
                    "vigente": True,
                    "revisada_en": None,
                }

            if texto not in resueltos:
                concepto_id, _nombre, parecido = clasificar(texto, conceptos)
                resueltos[texto] = (
                    (concepto_id, parecido) if parecido >= UMBRAL_CONCEPTO else (None, parecido)
                )
            concepto_id, parecido = resueltos[texto]

            modo = normalizar_modo(fila.get("modo_adquisicion"))
            instruccion = instruccion_para(modo, fila.get("instruccion_colegio"))
            categoria = _texto(fila.get("categoria"))

            items.append(
                {
                    "id": id_item(codigo, grado, orden),
                    "version_id": versiones[clave]["id"],
                    "orden": orden,
                    "texto_original": texto,
                    "concepto_id": concepto_id,
                    "cantidad": cantidad_valida(fila.get("cantidad")),
                    "unidad": None,
                    "tipo_item": normalizar_tipo(fila.get("tipo_item")),
                    "modo_adquisicion": modo,
                    "instruccion_colegio": instruccion,
                    "url_externa": _texto(fila.get("url_externa")),
                    "atributos": {"categoria": categoria} if categoria else {},
                    "confianza_normalizacion": round(parecido, 3),
                    "requiere_revision": concepto_id is None,
                }
            )

        self.total_items = len(items)
        self.sin_concepto = sum(1 for i in items if i["concepto_id"] is None)
        self._medir_carencias(items, conceptos)

        return {
            "lista_oficial": list(listas.values()),
            "version_lista_oficial": list(versiones.values()),
            "item_lista_oficial": items,
        }

    def _sedes(self) -> dict[str, str]:
        filas = leer_csv(self.dir / "colegios.csv")
        if not filas:
            self.problemas.append(
                Problema(True, "datos", f"no hay colegios.csv en {self.dir}: sin el no hay sede_id")
            )
        return {
            (f.get("codigo") or "").strip(): (f.get("sede_nombre") or "Sede unica").strip()
            for f in filas
            if (f.get("codigo") or "").strip()
        }

    def _medir_carencias(self, items: list[dict[str, Any]], conceptos: list[dict[str, Any]]) -> None:
        total = len(items)
        if not total:
            return
        self.carencias["renglones sin concepto resuelto"] = (
            sum(1 for i in items if i["concepto_id"] is None),
            total,
        )
        self.carencias["renglones que Tukit no puede surtir"] = (
            sum(1 for i in items if i["modo_adquisicion"] not in VALORES_SURTIBLES),
            total,
        )
        self.carencias["renglones sin unidad declarada"] = (
            sum(1 for i in items if i["unidad"] is None),
            total,
        )
        if conceptos:
            pedidos = {str(i["concepto_id"]) for i in items if i["concepto_id"]}
            self.carencias["conceptos del catalogo que nadie pide"] = (
                sum(1 for c in conceptos if str(c["id"]) not in pedidos),
                len(conceptos),
            )

    async def escribir(self, datos: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
        from sqlalchemy.dialects.postgresql import insert
        from tukit_comun.bd import crear_motor

        from .modelos import Base

        motor = crear_motor("catalogo")
        escritos: dict[str, int] = {}
        try:
            async with motor.engine.begin() as conexion:
                for tabla in ("lista_oficial", "version_lista_oficial", "item_lista_oficial"):
                    filas = datos.get(tabla, [])
                    if not filas:
                        escritos[tabla] = 0
                        continue
                    objeto = Base.metadata.tables[tabla]
                    claves = [c.name for c in objeto.primary_key.columns]
                    for bloque in _en_bloques(filas, FILAS_POR_BLOQUE):
                        sentencia = insert(objeto).values(bloque)
                        actualizables = {
                            c.name: sentencia.excluded[c.name]
                            for c in objeto.columns
                            if c.name not in claves and c.name in bloque[0]
                        }
                        if actualizables:
                            sentencia = sentencia.on_conflict_do_update(
                                index_elements=claves, set_=actualizables
                            )
                        else:
                            sentencia = sentencia.on_conflict_do_nothing()
                        await conexion.execute(sentencia)
                    escritos[tabla] = len(filas)
        finally:
            await motor.cerrar()
        return escritos


def _en_bloques(filas: list[dict[str, Any]], tamano: int):
    for inicio in range(0, len(filas), tamano):
        yield filas[inicio : inicio + tamano]


async def leer_conceptos() -> list[dict[str, Any]]:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            return [
                {"id": f.id, "nombre": f.nombre_canonico, "sinonimos": list(f.sinonimos or ())}
                for f in await conexion.execute(
                    select(concepto.c.id, concepto.c.nombre_canonico, concepto.c.sinonimos).where(
                        concepto.c.activo
                    )
                )
            ]
    finally:
        await motor.cerrar()


async def _principal(directorio: Path, anio: int, solo_validar: bool) -> int:
    conceptos = await leer_conceptos()
    print(f"Vocabulario activo del catalogo: {len(conceptos)} conceptos")

    cargador = Cargador(directorio, anio)
    datos = cargador.armar(conceptos)

    informe = Informe(
        escritos={t: len(f) for t, f in datos.items()},
        problemas=cargador.problemas,
        carencias=cargador.carencias,
    )

    if informe.bloqueado:
        print("No se escribio nada: hay filas que romperian las restricciones de la base.")
        informe.imprimir()
        return 1

    if not solo_validar:
        informe.escritos = await cargador.escribir(datos)

    informe.imprimir()

    total = cargador.total_items
    sin = cargador.sin_concepto
    pct = 100 * sin / total if total else 0
    print(f"\nRenglones sin concepto resuelto: {sin}/{total} ({pct:.1f}%)")
    print("No es un fallo: es lo que nuestro vocabulario todavia no cubre, y va a revision.")
    if solo_validar:
        print("\n(--solo-validar: no se escribio nada en la base)")
    else:
        print("Las versiones quedan SIN revisar: mira cuales con  --listas  de `descubrir`.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--datos", type=Path, default=Path("datos/listas"))
    analizador.add_argument("--anio", type=int, default=ANIO_POR_OMISION)
    analizador.add_argument("--solo-validar", action="store_true")
    args = analizador.parse_args()

    directorio = args.datos
    if not directorio.exists():
        print(f"No existe el directorio de datos: {directorio}")
        return 2

    return asyncio.run(_principal(directorio, args.anio, args.solo_validar))


if __name__ == "__main__":
    sys.exit(main())
