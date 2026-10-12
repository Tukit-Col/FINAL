"""Los kits canonicos de un colegio, armados desde `datos/` sin base de datos.

No es producto: es la vara para medir la curaduria. Corre la misma ruta
rapida que el catalogo (`armar_items`, el filtro por atributos de cada
renglon) sobre lo que `cargador` cargaria, y elige el producto de cada perfil
como lo proyecta el optimizador cuando cada linea tiene un solo renglon:

- Ahorrador: el de menor costo de linea (empaque incluido).
- Premium: el de mejor nivel y, dentro de el, el de menor costo de linea.

Los empates se rompen como los rompe el optimizador (ver `_clave_ahorrador`).

Despues junta las herramientas que un mismo hijo pide en varias materias, como
`juntar_herramientas`. No reproduce lo que no cambia la eleccion (personaje
pedido por el acudiente, hermanos, disponibilidad por tienda).

Uso:

    python ensayos/kits_offline.py                      # resumen del Agustiniano
    python ensayos/kits_offline.py --csv salida.csv     # ademas, renglon por renglon
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_RAIZ = Path(__file__).resolve().parents[1]
for _ruta in (
    _RAIZ / "libs" / "py" / "tukit_comun",
    _RAIZ / "servicios" / "catalogo",
    _RAIZ / "servicios" / "inteligencia",
):
    if str(_ruta) not in sys.path:
        sys.path.insert(0, str(_ruta))

from tukit_catalogo.cargador import Cargador  # noqa: E402
from tukit_catalogo.routers.admin import armar_items  # noqa: E402
from tukit_inteligencia.parseo import BUSCA_EN_CATALOGO  # noqa: E402

AGUSTINIANO = "bccf0294-f6b2-5203-84dd-e7fc643ae17f"
ORDEN_NIVEL = ("economico", "confiable", "premium")
GRADOS = (
    "Jardin",
    "Transicion",
    "Primero",
    "Segundo",
    "Tercero",
    "Cuarto",
    "Quinto",
    "Sexto",
    "Septimo",
    "Octavo",
    "Noveno",
    "Decimo",
    "Once",
)
# La notacion de la auditoria: `J#3`, `7#45`.
SIGLA = {g: s for g, s in zip(GRADOS, ("J", "T", *map(str, range(1, 12))), strict=True)}


@dataclass
class Eleccion:
    sku: str
    nombre: str
    nivel: str
    precio: int | None
    empaque: int
    unidades: int
    personaje: str | None = None

    @property
    def subtotal(self) -> int:
        return (self.precio or 0) * self.unidades


@dataclass
class Linea:
    grado: str
    orden: int
    texto: str
    cantidad: int
    concepto: str | None
    tipo: str
    estado: str
    impuestos: dict[str, Any]
    por_revisar: list[str]
    candidatos: list[dict[str, Any]]
    uno_por_estudiante: bool
    ahorrador: Eleccion | None = None
    premium: Eleccion | None = None
    notas: list[str] = field(default_factory=list)

    @property
    def clave(self) -> str:
        return f"{SIGLA.get(self.grado, self.grado)}#{self.orden}"

    @property
    def informativa(self) -> bool:
        return self.estado != "HUECO_CATALOGO" and not self.candidatos


@dataclass
class Catalogo:
    productos: dict[str, list[dict[str, Any]]]
    reglas: dict[str, tuple[tuple[str, ...], bool, str]]
    nombres: dict[str, str]


def cargar_catalogo(directorio: Path = _RAIZ / "datos" / "catalogo") -> Catalogo:
    """Lo que `cargador` meteria en la base, en la forma en que la ruta rapida lo lee."""
    armado = Cargador(directorio).armar()
    conceptos = {c["id"]: c for c in armado["concepto"]}
    precio_oferta: dict[Any, int] = {}
    for p in armado["precio_oferta"]:
        actual = precio_oferta.get(p["oferta_id"])
        if actual is None or p["valor_centavos"] < actual:
            precio_oferta[p["oferta_id"]] = p["valor_centavos"]
    precio_producto: dict[Any, int] = {}
    for o in armado["oferta_tienda"]:
        if not o["activo"] or o["id"] not in precio_oferta:
            continue
        valor = precio_oferta[o["id"]]
        pid = o["producto_canonico_id"]
        if pid not in precio_producto or valor < precio_producto[pid]:
            precio_producto[pid] = valor

    productos: dict[str, list[dict[str, Any]]] = {}
    for p in armado["producto_canonico"]:
        concepto = conceptos.get(p["concepto_id"])
        if not p["activo"] or concepto is None or not concepto["activo"]:
            continue
        centavos = precio_producto.get(p["id"])
        productos.setdefault(concepto["codigo"], []).append(
            {
                "id": p["id"],
                "sku": p["sku_interno"],
                "nombre": p["nombre"],
                "nivel": p["nivel"],
                "personaje": p["personaje"],
                "marca": p["marca"],
                "imagen_url": p["imagen_url"],
                "unidad_base": p["unidad_base"],
                "unidades_por_empaque": int(p["unidades_por_empaque"] or 1),
                "atributos": dict(p["atributos"] or {}),
                "precio_cop": None if centavos is None else centavos // 100,
            }
        )
    reglas = {
        c["codigo"]: (
            tuple(c["atributos_discriminantes"] or ()),
            bool(c["uno_por_estudiante"]),
            c["tipo_item"],
        )
        for c in conceptos.values()
    }
    nombres = {c["codigo"]: c["nombre_canonico"] for c in conceptos.values()}
    return Catalogo(productos, reglas, nombres)


def renglones_de(colegio_id: str, ruta: Path = _RAIZ / "datos" / "curaduria" / "listas_revisadas.csv"):
    """Los renglones curados de cada grado del colegio, como los lee la ruta rapida."""
    por_grado: dict[str, list[SimpleNamespace]] = {}
    with ruta.open(encoding="utf-8", newline="") as fh:
        for i, f in enumerate(csv.DictReader(fh)):
            if f["colegio_id"] != colegio_id:
                continue
            por_grado.setdefault(f["grado"], []).append(
                SimpleNamespace(
                    id=f"{f['grado']}-{f['orden']}-{i}",
                    orden=int(f["orden"]),
                    texto_original=f["texto_original"],
                    cantidad=int(f["cantidad"] or 1),
                    tipo_item=f["tipo_item"] or None,
                    modo_adquisicion=f["modo_adquisicion"] or "mercado_abierto",
                    concepto_codigo=f["concepto"] or None,
                    concepto_nombre=None,
                    instruccion_colegio=f["instruccion_colegio"] or None,
                    url_externa=f["url_externa"] or None,
                    atributos=json.loads(f["atributos"]) if f["atributos"] else {},
                    avisos_descartados=[],
                )
            )
    for filas in por_grado.values():
        filas.sort(key=lambda f: f.orden)
    return por_grado


def _costo_linea(candidato: dict[str, Any], cantidad: int) -> int:
    precio = candidato.get("precio_cop")
    unidades = math.ceil(max(cantidad, 1) / max(1, int(candidato.get("unidades_por_empaque") or 1)))
    return (precio or 0) * unidades


# Como desempata el optimizador, linea por linea. Sus cuatro objetivos se suman
# por linea, asi que la proyeccion de `_proyectar` se descompone:
#
# 1. `_surtibles`: primero la mayor disponibilidad, o sea un candidato con
#    precio si la linea tiene alguno.
# 2. El eje del perfil: el Ahorrador minimiza el costo y luego maximiza la
#    fidelidad (`-s.fidelidad`); el Premium maximiza la fidelidad y luego
#    minimiza el costo.
# 3. Lo que queda empatado lo decide la dominancia de `_no_dominadas`: a igual
#    costo y nivel, el que trae personaje domina (sin personaje pedido cuenta
#    cualquiera). En los canonicos casi nunca pesa, porque la ruta rapida solo
#    deja productos con personaje cuando son los unicos que cumplen.
# 4. Con el vector de objetivos identico, `_no_dominadas` se queda con la
#    primera solucion enumerada, que lleva el primer candidato en el orden de la
#    ruta rapida (nivel, precio, sku): de ahi el indice.
#
# Con NSGA-II (espacio de busqueda > `LIMITE_ENUMERACION`) el frente puede no
# traer el punto exacto; esto replica el frente exacto.
def _clave_ahorrador(
    candidato: dict[str, Any], indice: int, cantidad: int
) -> tuple[bool, int, int, bool, int]:
    return (
        candidato.get("precio_cop") is None,
        _costo_linea(candidato, cantidad),
        -_rango(candidato["nivel"]),
        not candidato.get("personaje"),
        indice,
    )


def _clave_premium(candidato: dict[str, Any], indice: int, cantidad: int) -> tuple[bool, int, int, bool, int]:
    return (
        candidato.get("precio_cop") is None,
        -_rango(candidato["nivel"]),
        _costo_linea(candidato, cantidad),
        not candidato.get("personaje"),
        indice,
    )


def _mejor(candidatos: list[dict[str, Any]], clave, cantidad: int) -> dict[str, Any]:
    return min(enumerate(candidatos), key=lambda par: clave(par[1], par[0], cantidad))[1]


def _eleccion(candidato: dict[str, Any], cantidad: int) -> Eleccion:
    empaque = max(1, int(candidato.get("unidades_por_empaque") or 1))
    return Eleccion(
        sku=candidato["sku"],
        nombre=candidato["nombre"],
        nivel=candidato["nivel"],
        precio=candidato.get("precio_cop"),
        empaque=empaque,
        unidades=math.ceil(max(cantidad, 1) / empaque),
        personaje=candidato.get("personaje"),
    )


def _rango(nivel: str) -> int:
    return ORDEN_NIVEL.index(nivel) if nivel in ORDEN_NIVEL else -1


def armar_grado(grado: str, filas: list[SimpleNamespace], catalogo: Catalogo) -> list[Linea]:
    for f in filas:
        f.concepto_nombre = catalogo.nombres.get(f.concepto_codigo or "")
    items = armar_items(filas, catalogo.productos, catalogo.reglas)
    lineas = []
    for item in items:
        tipo = item.get("tipo_item") or "util"
        modo = item.get("modo_adquisicion") or "mercado_abierto"
        candidatos = item["candidatos"]
        # La misma puerta que la ruta rapida de `trabajos.py`.
        surtible = (
            item.get("concepto_codigo") is not None
            and tipo in BUSCA_EN_CATALOGO
            and modo in {"mercado_abierto", "libro_libre"}
        )
        estado = "RESUELTO_AUTO"
        if surtible and not candidatos:
            estado = "HUECO_CATALOGO"
        elif not surtible and tipo == "texto" and modo in {"mercado_abierto", "libro_libre"}:
            estado = "SIN_MATCH"
        if not surtible:
            candidatos = []
        linea = Linea(
            grado=grado,
            orden=item["orden"],
            texto=item["texto_original"],
            cantidad=item["cantidad"],
            concepto=item.get("concepto_codigo"),
            tipo=tipo,
            estado=estado,
            impuestos=item["atributos_impuestos"],
            por_revisar=item["atributos_por_revisar"],
            candidatos=candidatos,
            uno_por_estudiante=bool(item.get("uno_por_estudiante")),
        )
        if candidatos:
            barato = _mejor(candidatos, _clave_ahorrador, linea.cantidad)
            premium = _mejor(candidatos, _clave_premium, linea.cantidad)
            linea.ahorrador = _eleccion(barato, linea.cantidad)
            linea.premium = _eleccion(premium, linea.cantidad)
        lineas.append(linea)
    _juntar(lineas, "ahorrador")
    _juntar(lineas, "premium")
    return lineas


def _juntar(lineas: list[Linea], perfil: str) -> None:
    """`juntar_herramientas`: el mismo producto de un concepto uno-por-estudiante se compra una vez."""
    grupos: dict[str, list[Linea]] = {}
    for linea in lineas:
        eleccion = getattr(linea, perfil)
        if eleccion is not None and linea.uno_por_estudiante:
            grupos.setdefault(eleccion.sku, []).append(linea)
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        primera = getattr(grupo[0], perfil)
        cantidad = max(lin.cantidad for lin in grupo)
        primera.unidades = math.ceil(cantidad / primera.empaque)
        for otra in grupo[1:]:
            getattr(otra, perfil).unidades = 0
            otra.notas.append(f"{perfil}: va en la linea {grupo[0].orden}")


def armar_colegio(colegio_id: str = AGUSTINIANO, catalogo: Catalogo | None = None) -> dict[str, list[Linea]]:
    catalogo = catalogo or cargar_catalogo()
    return {
        grado: armar_grado(grado, filas, catalogo)
        for grado, filas in sorted(
            renglones_de(colegio_id).items(),
            key=lambda par: GRADOS.index(par[0]) if par[0] in GRADOS else 99,
        )
    }


def por_clave(kits: dict[str, list[Linea]]) -> dict[str, Linea]:
    return {linea.clave: linea for lineas in kits.values() for linea in lineas}


def resumen(kits: dict[str, list[Linea]]) -> dict[str, int]:
    todas = [linea for lineas in kits.values() for linea in lineas]
    return {
        "renglones": len(todas),
        "resuelto_con_producto": sum(1 for lin in todas if lin.candidatos),
        "hueco_catalogo": sum(1 for lin in todas if lin.estado == "HUECO_CATALOGO"),
        "informativas": sum(1 for lin in todas if lin.informativa),
        "personaje_en_ahorrador": sum(1 for lin in todas if lin.ahorrador and lin.ahorrador.personaje),
        "total_ahorrador": sum(lin.ahorrador.subtotal for lin in todas if lin.ahorrador),
        "total_premium": sum(lin.premium.subtotal for lin in todas if lin.premium),
    }


def _escribir_csv(kits: dict[str, list[Linea]], ruta: Path) -> None:
    columnas = [
        "clave",
        "texto",
        "cantidad",
        "concepto",
        "tipo",
        "estado",
        "impuestos",
        "por_revisar",
        "n_candidatos",
        "ahorrador",
        "a_unidades",
        "a_subtotal",
        "premium",
        "p_unidades",
        "p_subtotal",
        "notas",
    ]
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        for lineas in kits.values():
            for lin in lineas:
                a, p = lin.ahorrador, lin.premium
                escritor.writerow(
                    {
                        "clave": lin.clave,
                        "texto": lin.texto,
                        "cantidad": lin.cantidad,
                        "concepto": lin.concepto or "",
                        "tipo": lin.tipo,
                        "estado": lin.estado,
                        "impuestos": json.dumps(lin.impuestos, ensure_ascii=False, sort_keys=True),
                        "por_revisar": ",".join(lin.por_revisar),
                        "n_candidatos": len(lin.candidatos),
                        "ahorrador": f"{a.sku} {a.nombre} ${a.precio}" if a else "",
                        "a_unidades": a.unidades if a else "",
                        "a_subtotal": a.subtotal if a else "",
                        "premium": f"{p.sku} {p.nombre} ${p.precio}" if p else "",
                        "p_unidades": p.unidades if p else "",
                        "p_subtotal": p.subtotal if p else "",
                        "notas": "; ".join(lin.notas),
                    }
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--colegio", default=AGUSTINIANO)
    parser.add_argument("--csv", type=Path, help="escribe el detalle renglon por renglon")
    args = parser.parse_args(argv)
    kits = armar_colegio(args.colegio)
    for clave, valor in resumen(kits).items():
        print(f"{clave:26} {valor:>12,}")
    if args.csv:
        _escribir_csv(kits, args.csv)
        print(f"detalle en {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
