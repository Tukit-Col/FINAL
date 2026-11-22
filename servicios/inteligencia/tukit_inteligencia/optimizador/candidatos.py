from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from tukit_comun.texto import normalizar_personaje

from ..modelos import EstadoResolucion, PerfilKit
from .tipos import Candidato, Renglon, _costo_para_ordenar

MAX_MARCAS_EXCLUIDAS = 10


MAX_LARGO_MARCA = 40


def _plano_marca(texto: str | None) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").casefold()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes).strip()


def _contiene_palabras(frase: str, texto: str) -> bool:
    return bool(frase) and f" {frase} " in f" {texto} "


@dataclass(frozen=True)
class FiltrosDuros:
    marcas_excluidas: tuple[tuple[str, str], ...] = ()
    solo_disponibles: bool = False

    @property
    def activos(self) -> bool:
        return bool(self.marcas_excluidas) or self.solo_disponibles


def filtros_de(preferencias: dict[str, Any] | None) -> FiltrosDuros:
    preferencias = preferencias or {}
    crudas = preferencias.get("marcas_excluidas")
    marcas: list[tuple[str, str]] = []
    if isinstance(crudas, (list, tuple)):
        for cruda in crudas[:MAX_MARCAS_EXCLUIDAS]:
            if not isinstance(cruda, str):
                continue
            original = cruda.strip()[:MAX_LARGO_MARCA]
            plana = _plano_marca(original)
            if plana and all(plana != previa for previa, _ in marcas):
                marcas.append((plana, original))
    return FiltrosDuros(
        marcas_excluidas=tuple(marcas),
        solo_disponibles=preferencias.get("solo_disponibles") is True,
    )


def _marcas_que_coinciden(candidato: Candidato, filtros: FiltrosDuros) -> list[str]:
    base = _plano_marca(candidato.marca if candidato.marca else candidato.nombre)
    return [original for plana, original in filtros.marcas_excluidas if _contiene_palabras(plana, base)]


def _marcas_nombradas_por_la_lista(texto: str, filtros: FiltrosDuros) -> set[str]:
    plano = _plano_marca(texto)
    return {original for plana, original in filtros.marcas_excluidas if _contiene_palabras(plana, plano)}


def _tiene_oferta_vigente(candidato: Candidato) -> bool:
    return candidato.precio_cop is not None


def candidato_permitido(candidato: Candidato, texto_renglon: str, filtros: FiltrosDuros) -> bool:
    if filtros.solo_disponibles and not _tiene_oferta_vigente(candidato):
        return False
    exentas = _marcas_nombradas_por_la_lista(texto_renglon, filtros)
    return all(marca in exentas for marca in _marcas_que_coinciden(candidato, filtros))


def _nombres(marcas: list[str]) -> str:
    return ", ".join(dict.fromkeys(marcas))


def aplicar_filtros_duros(renglones: list[Renglon], preferencias: dict[str, Any] | None) -> list[Renglon]:
    filtros = filtros_de(preferencias)
    if not filtros.activos:
        return renglones

    salida: list[Renglon] = []
    for renglon in renglones:
        if renglon.informativa or not renglon.candidatos:
            salida.append(renglon)
            continue

        exentas = _marcas_nombradas_por_la_lista(renglon.texto, filtros)
        quedan: list[Candidato] = []
        quitadas: list[str] = []
        sin_oferta = 0
        exigida_presente: list[str] = []
        for candidato in renglon.candidatos:
            coinciden = _marcas_que_coinciden(candidato, filtros)
            if filtros.solo_disponibles and not _tiene_oferta_vigente(candidato):
                sin_oferta += 1
                continue
            prohibidas = [m for m in coinciden if m not in exentas]
            if prohibidas:
                quitadas += prohibidas
                continue
            exigida_presente += [m for m in coinciden if m in exentas]
            quedan.append(candidato)

        nota_exigida = (
            f"El colegio pide {_nombres(exigida_presente)} en esta linea y no la quitamos."
            if exigida_presente
            else None
        )
        if len(quedan) == len(renglon.candidatos) and nota_exigida is None:
            salida.append(renglon)
            continue
        if not quedan:
            motivos = []
            if quitadas:
                motivos.append(f"quitamos {_nombres(quitadas)} como pediste y no queda otro producto")
            if sin_oferta:
                motivos.append("ningun producto tiene precio vigente hoy y pediste solo los disponibles")
            mensaje = "Para esta linea " + "; ".join(motivos) + "."
            if nota_exigida:
                mensaje += " " + nota_exigida
            salida.append(
                replace(
                    renglon,
                    candidatos=(),
                    estado_resolucion=EstadoResolucion.HUECO_CATALOGO.value,
                    mensaje=mensaje,
                )
            )
            continue
        mensaje = renglon.mensaje
        if nota_exigida:
            mensaje = f"{mensaje} {nota_exigida}" if mensaje else nota_exigida
        salida.append(replace(renglon, candidatos=tuple(quedan), mensaje=mensaje))
    return salida


def elegir_por_perfil(
    candidatos: tuple[Candidato, ...],
    perfil: str,
    *,
    personajes: tuple[str, ...] = (),
    cantidad: int = 1,
) -> Candidato | None:
    admisibles = [c for c in candidatos if c.cumple] or list(candidatos)
    if not admisibles:
        return None

    def orden(c: Candidato) -> tuple[tuple[int, int, int], str]:
        return (_costo_para_ordenar(c, cantidad), c.sku)

    if perfil == PerfilKit.PREMIUM.value:
        mejor_nivel = max(c.rango_nivel for c in admisibles)
        del_nivel = [c for c in admisibles if c.rango_nivel == mejor_nivel]
        return min(del_nivel, key=orden)

    if perfil == PerfilKit.FAN.value:
        pedidos = {normalizar_personaje(p) for p in personajes}
        con_personaje = [
            c
            for c in admisibles
            if c.personaje and (not pedidos or normalizar_personaje(c.personaje) in pedidos)
        ]
        if con_personaje:
            return min(con_personaje, key=orden)

    return min(admisibles, key=orden)
