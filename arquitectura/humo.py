"""Prueba de humo del backend vivo: golpea la API y exige que traiga datos.

Es la funcion de aptitud que le faltaba a la capa HTTP. `test_fronteras.py`
mira el codigo y `verificar_deriva.py` mira el motor; esto mira lo unico que
el frontend va a ver, que es la respuesta.

Lo que comprueba no es que responda 200. Un endpoint que devuelve
`{"total": 0, "conceptos": []}` responde 200 perfectamente y es exactamente
el modo de fallar que hay que atrapar: la base migrada y sin sembrar se ve
igual de sana que la sembrada hasta que alguien abre la pantalla. Por eso
cada comprobacion exige un minimo de contenido.

No va con pytest a proposito. La suite corre sin Postgres y sin procesos
levantados; esto necesita las dos cosas, y meterlo ahi obligaria a saltarlo
casi siempre, que es la forma de que una prueba deje de significar algo.

    make humo
    python arquitectura/humo.py --base http://127.0.0.1:8010
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

BASE_POR_OMISION = "http://127.0.0.1:8010"

# Cuanto se espera a que el pipeline termine. Son segundos y no minutos
# porque el camino de hoy no llama a ningun modelo: lee la lista oficial ya
# cargada y empareja contra el catalogo local.
ESPERA_TRABAJO = 90


class Fallo(Exception):
    pass


def _pedir(base: str, ruta: str, cuerpo: dict[str, Any] | None = None) -> Any:
    url = f"{base}{ruta}"
    datos = None if cuerpo is None else json.dumps(cuerpo).encode("utf-8")
    peticion = urllib.request.Request(
        url, data=datos, headers={"Content-Type": "application/json"} if datos else {}
    )
    try:
        with urllib.request.urlopen(peticion, timeout=120) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise Fallo(f"{ruta} respondio {error.code}: {error.read()[:200]!r}") from error
    except OSError as error:
        raise Fallo(f"{ruta} no respondio: {error}") from error


def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise Fallo(mensaje)


def comprobar(base: str) -> list[tuple[str, str]]:
    """Devuelve una linea por comprobacion, con lo que trajo de verdad."""
    hechas: list[tuple[str, str]] = []

    salud = _pedir(base, "/v1/servicios")
    _exigir(salud["todos_arriba"], f"no todos los servicios estan arriba: {salud['servicios']}")
    hechas.append(("/v1/servicios", "los cuatro procesos responden"))

    conceptos = _pedir(base, "/v1/catalogo/conceptos?por_pagina=5")
    _exigir(conceptos["total"] > 0, "el catalogo no tiene conceptos: falta `make bd-cargar`")
    hechas.append(("/v1/catalogo/conceptos", f"{conceptos['total']} conceptos"))

    productos = _pedir(base, "/v1/catalogo/productos?con_precio=true&por_pagina=5")
    _exigir(productos["total"] > 0, "no hay productos con precio vigente")
    primero = productos["productos"][0]
    _exigir(primero["precio_desde"] is not None, "el producto vino sin precio")
    hechas.append(("/v1/catalogo/productos", f"{productos['total']} con precio, el primero {primero['sku']}"))

    ficha = _pedir(base, f"/v1/catalogo/productos/{primero['sku']}")
    _exigir(bool(ficha["ofertas"]), f"{primero['sku']} no trae ofertas")
    hechas.append((f"/v1/catalogo/productos/{primero['sku']}", f"{len(ficha['ofertas'])} ofertas"))

    tiendas = _pedir(base, "/v1/catalogo/tiendas")
    _exigir(tiendas["total"] > 0, "no hay tiendas")
    hechas.append(("/v1/catalogo/tiendas", f"{tiendas['total']} tiendas"))

    colegios = _pedir(base, "/v1/colegios")
    _exigir(colegios["total"] > 0, "no hay colegios: falta `make bd-colegios`")
    colegio = colegios["colegios"][0]
    hechas.append(("/v1/colegios", f"{colegios['total']} colegios, el primero {colegio['nombre']}"))

    listas = _pedir(base, "/v1/listas?por_pagina=5")
    _exigir(listas["total"] > 0, "no hay listas oficiales: falta `make bd-listas`")
    lista = listas["listas"][0]
    _exigir(lista["items"] > 0, "la primera lista no tiene renglones")
    hechas.append(("/v1/listas", f"{listas['total']} listas, la primera con {lista['items']} renglones"))

    detalle = _pedir(base, f"/v1/listas/{lista['lista_id']}")
    _exigir(detalle["total_items"] > 0, "el detalle de la lista vino vacio")
    hechas.append((f"/v1/listas/{lista['lista_id']}", f"{detalle['total_items']} renglones"))

    emparejados = _pedir(
        base,
        "/v1/catalogo/emparejar",
        {"renglones": ["2 cuadernos cuadriculados grandes", "caja de colores x12"]},
    )
    reconocidos = sum(1 for e in emparejados["emparejamientos"] if e["estado"] == "reconocido")
    _exigir(reconocidos > 0, "el emparejamiento no reconocio ni un renglon")
    hechas.append(("/v1/catalogo/emparejar", f"{reconocidos} de 2 renglones reconocidos"))

    # --- el ciclo completo ---------------------------------------------------
    trabajo = _pedir(
        base,
        "/v1/trabajos",
        {
            "contacto": {"correo": "humo@ejemplo.com"},
            "hijos": [
                {
                    "referencia": "hijo-1",
                    "colegio_id": lista["colegio_id"],
                    "grado": lista["grado"],
                    "anio_lectivo": lista["anio_lectivo"],
                }
            ],
            "preferencias": {"presupuesto_por_hijo": 700000},
        },
    )
    trabajo_id = trabajo["trabajo_id"]
    hechas.append(("POST /v1/trabajos", f"202, trabajo {trabajo_id}"))

    limite = time.monotonic() + ESPERA_TRABAJO
    estado = trabajo["estado"]
    while time.monotonic() < limite:
        actual = _pedir(base, f"/v1/trabajos/{trabajo_id}")
        estado = actual["estado"]
        if estado in {"espera_revision", "publicado", "fallido"}:
            break
        time.sleep(1)

    _exigir(estado != "fallido", f"el trabajo fallo: {actual.get('error')} {actual.get('mensaje')}")
    _exigir(estado in {"espera_revision", "publicado"}, f"el trabajo se quedo en {estado}")
    etapas = {e["nombre"]: e["estado"] for e in actual["etapas"]}
    hechas.append((f"GET /v1/trabajos/{trabajo_id}", f"estado {estado}, etapas {etapas}"))

    if estado == "espera_revision":
        cola = _pedir(base, "/v1/admin/cola")
        _exigir(cola["total"] > 0, "el trabajo no aparece en la cola de revision")
        hechas.append(("/v1/admin/cola", f"{cola['total']} trabajo(s) esperando"))

        admin = _pedir(base, f"/v1/admin/trabajos/{trabajo_id}")
        _exigir(len(admin["kits"]) == 3, f"Admin ve {len(admin['kits'])} kits y deberian ser 3")
        hechas.append((f"/v1/admin/trabajos/{trabajo_id}", "los 3 kits visibles antes de publicar"))

        _pedir(base, f"/v1/admin/trabajos/{trabajo_id}/revision", {"decision": "aprobar"})
        hechas.append((f"POST /v1/admin/trabajos/{trabajo_id}/revision", "aprobado"))

    publicado = _pedir(base, f"/v1/trabajos/{trabajo_id}")
    _exigir(publicado["estado"] == "publicado", f"tras aprobar quedo en {publicado['estado']}")
    _exigir(len(publicado["kits"]) == 3, f"salieron {len(publicado['kits'])} kits y deberian ser 3")
    _exigir(publicado["recomendado"] is not None, "ningun kit quedo marcado como recomendado")
    lineas = sum(len(k["lineas"]) for k in publicado["kits"])
    _exigir(lineas > 0, "los kits salieron sin lineas")
    totales = ", ".join(f"{k['perfil']}=${k['total']:,}" for k in publicado["kits"])
    hechas.append(
        (
            f"GET /v1/trabajos/{trabajo_id} (publicado)",
            f"3 kits ({totales}), recomendado {publicado['recomendado']['perfil']}",
        )
    )
    return hechas


def main(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--base", default=BASE_POR_OMISION)
    argumentos = analizador.parse_args(argv)

    try:
        hechas = comprobar(argumentos.base.rstrip("/"))
    except Fallo as error:
        print(f"HUMO FALLO: {error}", file=sys.stderr)
        return 1

    ancho = max(len(r) for r, _ in hechas)
    for ruta, resultado in hechas:
        print(f"  ok  {ruta:{ancho}}  {resultado}")
    print(f"\n{len(hechas)} comprobaciones, todas con datos reales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
