"""Eleccion de candidatos por renglon: filtros duros del acudiente y la heuristica por perfil."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from typing import Any

from tukit_comun.texto import normalizar_personaje

from ..modelos import EstadoResolucion, PerfilKit
from .tipos import Candidato, Renglon, _costo_para_ordenar

# `marcas_excluidas` y `solo_disponibles` (objeto R del asistente NL2C) son
# restricciones DURAS: se aplican a los candidatos ANTES de armar el frente, no
# como un castigo en la funcion objetivo. Si fueran un peso mas, NSGA-II podria
# devolver un kit con la marca que el acudiente pidio no ver, y eso es justo lo
# que una restriccion dura promete que no pasa. Esto contrasta con el
# presupuesto, que si se aplica despues del frente (ver docstring del paquete):
# el presupuesto recorta el kit entero y un frente recortado esconde opciones;
# una marca excluida no es una opcion que el acudiente quiera ver.
MAX_MARCAS_EXCLUIDAS = 10


MAX_LARGO_MARCA = 40


def _plano_marca(texto: str | None) -> str:
    """Minusculas, sin tildes y sin signos: `Faber-Castell` y `FABER CASTELL` coinciden.

    Las marcas llegan escritas por el acudiente y por el catalogo, que no
    comparten ortografia. Comparar el texto crudo dejaba pasar justo la marca
    que el acudiente pidio excluir.
    """
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").casefold()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes).strip()


def _contiene_palabras(frase: str, texto: str) -> bool:
    """`frase` aparece en `texto` como palabras completas (`norma` no esta en `normalizado`)."""
    return bool(frase) and f" {frase} " in f" {texto} "


@dataclass(frozen=True)
class FiltrosDuros:
    """Lo que el acudiente prohibe, ya normalizado. Vacio = no filtra nada."""

    # (forma plana para comparar, como lo escribio el acudiente para decirselo).
    marcas_excluidas: tuple[tuple[str, str], ...] = ()
    solo_disponibles: bool = False

    @property
    def activos(self) -> bool:
        return bool(self.marcas_excluidas) or self.solo_disponibles


def filtros_de(preferencias: dict[str, Any] | None) -> FiltrosDuros:
    """Lee los filtros de las preferencias, desconfiando de lo que traigan.

    Las preferencias de una subida de PDF viajan por el catalogo como JSON
    sin esquema, asi que aqui se acota todo: una lista enorme o un tipo raro
    no deben tumbar el armado del kit ni volverlo mas lento.
    """
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
        # Solo un `true` de verdad: "false" o 0 llegados de un JSON suelto no encienden el filtro.
        solo_disponibles=preferencias.get("solo_disponibles") is True,
    )


def _marcas_que_coinciden(candidato: Candidato, filtros: FiltrosDuros) -> list[str]:
    """Las marcas excluidas a las que pertenece el candidato (casi siempre 0 o 1).

    Si el catalogo no trae marca se mira el nombre del producto: hay productos
    cargados sin marca cuyo nombre la dice ("Cuaderno Norma"), y dejarlos pasar
    seria ofrecer la marca excluida por un hueco de datos. Con marca, solo
    cuenta la marca: el nombre de un producto de otra marca puede nombrar a
    la excluida de pasada (compatibilidad, "tipo Faber-Castell").
    """
    base = _plano_marca(candidato.marca if candidato.marca else candidato.nombre)
    return [original for plana, original in filtros.marcas_excluidas if _contiene_palabras(plana, base)]


def _marcas_nombradas_por_la_lista(texto: str, filtros: FiltrosDuros) -> set[str]:
    """Las marcas excluidas que el texto del renglon nombra: el colegio las exige.

    Catalogo no modela una "marca exigida" como dato aparte; lo que existe es el
    texto de la lista ("Cuaderno Norma 100 hojas"). Si el colegio escribio la
    marca, el acudiente no puede excluirla en esa linea sin que el kit deje de
    servirle para el colegio.
    """
    plano = _plano_marca(texto)
    return {original for plana, original in filtros.marcas_excluidas if _contiene_palabras(plana, plano)}


def _tiene_oferta_vigente(candidato: Candidato) -> bool:
    """Precio vigente = oferta activa hoy.

    Es el unico modelo de disponibilidad que llega a Inteligencia: el catalogo
    entrega `precio_cop` desde la oferta activa con precio vigente, y el objetivo
    `disponibilidad` del frente ya lo lee asi ("Tukit puede surtirlo hoy"). La
    bandera `disponible` por tienda no viaja en el candidato.
    """
    return candidato.precio_cop is not None


def candidato_permitido(candidato: Candidato, texto_renglon: str, filtros: FiltrosDuros) -> bool:
    """Si el candidato pasa los filtros duros en ESE renglon (con la excepcion de marca exigida)."""
    if filtros.solo_disponibles and not _tiene_oferta_vigente(candidato):
        return False
    exentas = _marcas_nombradas_por_la_lista(texto_renglon, filtros)
    return all(marca in exentas for marca in _marcas_que_coinciden(candidato, filtros))


def _nombres(marcas: list[str]) -> str:
    return ", ".join(dict.fromkeys(marcas))


def aplicar_filtros_duros(renglones: list[Renglon], preferencias: dict[str, Any] | None) -> list[Renglon]:
    """Quita los candidatos prohibidos de cada renglon, ANTES de optimizar.

    - Marca excluida: el candidato se saca, salvo que el texto del renglon
      nombre esa marca (la exige el colegio): ahi se deja y la linea lo explica.
    - `solo_disponibles`: se sacan los candidatos sin oferta vigente.
    - Si un renglon se queda sin candidatos NO se rellena con el excluido: queda
      como hueco del catalogo con un mensaje que dice por que, igual que las demas
      lineas que no se pueden comprar. Callar y usar la marca prohibida es la
      falla que este filtro existe para evitar.

    Sin filtros devuelve la misma lista. Los renglones informativos y los que ya
    venian sin candidatos no se tocan (no hay nada que filtrar).
    """
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
            # Solo cuenta la marca exigida de un candidato que SOBREVIVE: si salio
            # por no tener oferta, decir "no la quitamos" seria afirmar que el kit
            # lleva la marca del colegio cuando lleva otra.
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
    """La heuristica de seleccion, hoy acotada a dos usos legitimos.

    Sigue viva por dos razones, y NINGUNA es "pymoo no esta" (pymoo es
    dependencia dura): es la eleccion de la linea sin compromiso multiobjetivo
    —un unico candidato admisible, donde el frente devolveria ese mismo punto—,
    y es la referencia contra la que se mide el frente (la prueba de
    hipervolumen exige que NSGA-II no lo haga peor). Su semantica es la de
    siempre:

    `Ahorrador` es el mas barato; `Premium` el de mejor nivel de marca y, a
    igualdad de nivel, el mas barato; `Fan` el que trae el personaje que el
    acudiente pidio para ESE hijo, y si no hay ninguno se comporta como
    `Ahorrador` en vez de inventarse un personaje.

    Nota sobre `Ahorrador`: puede terminar eligiendo un producto de nivel
    `premium` si resulto mas barato por empaque, y eso NO es un defecto. El
    nivel describe un producto y el perfil describe una ponderacion sobre el
    kit completo.

    `cantidad` es lo que pide el renglon: "mas barato" se mide sobre lo que
    cuesta la linea entera, que depende del empaque (`_costo_para_ordenar`).
    """
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
