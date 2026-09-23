"""Fase 1, de punta a punta: leer la lista y responderla con el catalogo.

Inteligencia no importa Catalogo y Catalogo no importa Inteligencia. Este
archivo es el unico sitio donde los dos se encuentran, y solo para un
ensayo: parsea el renglon alla y lo empareja aca.

    python ensayos/fase1.py --texto "block oficio" "2 lapices negros"
    python ensayos/fase1.py lista.pdf

El PDF llama a Gemini (hace falta GEMINI_API_KEY). El texto no.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

# El ensayo vive fuera de los dos servicios. Se agregan sus raices al path
# porque `python ensayos/fase1.py` no pasa por el pythonpath de pytest.
_RAIZ = Path(__file__).resolve().parents[1]
for _ruta in (
    _RAIZ / "libs" / "py" / "tukit_comun",
    _RAIZ / "servicios" / "catalogo",
    _RAIZ / "servicios" / "inteligencia",
):
    sys.path.insert(0, str(_ruta))

from tukit_catalogo.consulta import emparejar_en_catalogo  # noqa: E402
from tukit_inteligencia.parseo import mensaje_para_papa, parsear_renglon  # noqa: E402


def _linea(demanda, emparejamiento) -> dict:
    cuerpo = asdict(demanda)
    cuerpo["busca_en_catalogo"] = demanda.busca_en_catalogo
    # El papa ve el estado del item aunque no se busque producto.
    cuerpo["mensaje"] = mensaje_para_papa(demanda)
    if emparejamiento is None:
        cuerpo["emparejamiento"] = None
    else:
        cuerpo["emparejamiento"] = emparejamiento.a_dict()
    return cuerpo


async def responder(renglones: list[tuple[str, int | None]]) -> list[dict]:
    """Parsea cada renglon y solo empareja los que se compran."""
    demandas = [parsear_renglon(texto, cantidad=cantidad) for texto, cantidad in renglones]
    a_buscar = [d.texto for d in demandas if d.busca_en_catalogo]
    encontrados = await emparejar_en_catalogo(a_buscar) if a_buscar else []
    por_texto = {e.texto: e for e in encontrados}
    return [_linea(d, por_texto.get(d.texto) if d.busca_en_catalogo else None) for d in demandas]


def _imprimir(filas: list[dict]) -> None:
    for fila in filas:
        tipo = fila["tipo_item"]
        print(f"{tipo:18} x{fila['cantidad']:<4} {fila['texto'][:70]}")
        if fila["mensaje"]:
            print(f"  {fila['mensaje']}")
        elif fila["nota"]:
            print(f"  {fila['nota']}")
        if fila["url_externa"]:
            print(f"  {fila['url_externa']}")
        emparejamiento = fila["emparejamiento"]
        if emparejamiento is None:
            print()
            continue
        corregido = emparejamiento.get("texto_corregido") or ""
        if corregido and corregido != fila["texto"]:
            print(f"  leido como {corregido}")
        print(f"  {emparejamiento['estado']}  {emparejamiento['concepto_nombre'] or '-'}")
        if emparejamiento["motivo"]:
            print(f"  {emparejamiento['motivo']}")
        for opcion in emparejamiento["opciones"]:
            precio = f"${opcion['precio_cop']:,}" if opcion["precio_cop"] is not None else "sin precio"
            print(f"    {opcion['nivel']:12} {precio:>12}  {opcion['nombre'][:56]}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fase 1 contra el catalogo curado.")
    parser.add_argument("archivo", nargs="?", help="PDF o imagen de una lista de un solo grado.")
    parser.add_argument("--texto", nargs="+", help="Renglones ya leidos, sin llamar a Gemini.")
    parser.add_argument("--json", action="store_true", help="Imprime el JSON en vez del resumen.")
    argumentos = parser.parse_args(argv)

    if argumentos.texto:
        filas = asyncio.run(responder([(t, None) for t in argumentos.texto]))
        if argumentos.json:
            print(json.dumps(filas, ensure_ascii=False, indent=2))
        else:
            _imprimir(filas)
        return 0

    if not argumentos.archivo:
        parser.error("pasa un PDF o usa --texto")

    from tukit_inteligencia.gemini import pedir_pagina
    from tukit_inteligencia.paginas import renderizar
    from tukit_inteligencia.percepcion import percibir

    contenido = Path(argumentos.archivo).read_bytes()
    percepcion = percibir(contenido, renderizar=renderizar, leer=pedir_pagina)
    if not percepcion.aceptada:
        print(percepcion.mensaje)
        if percepcion.grados:
            print("grados:", ", ".join(percepcion.grados))
        return 2

    filas = asyncio.run(responder([(item.descripcion, item.cantidad) for item in percepcion.items]))
    if argumentos.json:
        print(
            json.dumps(
                {"grados": list(percepcion.grados), "paginas": percepcion.paginas, "items": filas},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if percepcion.grados:
            print(f"grado: {', '.join(percepcion.grados)}   paginas: {percepcion.paginas}\n")
        _imprimir(filas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
