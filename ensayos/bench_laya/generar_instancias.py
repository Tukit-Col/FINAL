"""Foto del catalogo -> instancias fijas del benchmark Laya vs NSGA-II.

Cada instancia es una lista oficial (colegio, grado) de `datos/listas/items_lista.csv`
pasada por la MISMA normalizacion y el MISMO emparejamiento que usa el pipeline
(`trabajos._normalizar`, `consulta.emparejar`, `trabajos._candidato`). El resultado se
congela en un JSON: todos los competidores deciden sobre exactamente los mismos
renglones y candidatos, aunque el catalogo cambie despues.

Uso (desde la raiz del worktree, con el .venv del proyecto):
    python ensayos/bench_laya/generar_instancias.py --salida ensayos/bench_laya/instancias.json.gz
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
for sub in ("servicios/catalogo", "servicios/inteligencia", "libs/py/tukit_comun", "ensayos"):
    sys.path.insert(0, str(RAIZ / sub))

from entorno import cargar_env  # noqa: E402


def _leer_listas() -> dict[tuple[str, str], list[dict]]:
    listas: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with open(RAIZ / "datos/listas/items_lista.csv", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            listas[(fila["colegio_codigo"], fila["grado"])].append(fila)
    for filas in listas.values():
        filas.sort(key=lambda r: int(r["orden"]))
    return dict(sorted(listas.items()))


async def _indice():
    from tukit_catalogo.consulta import cargar_indice
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            return await cargar_indice(conexion)
    finally:
        await motor.cerrar()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default=str(RAIZ / "ensayos/bench_laya/instancias.json.gz"))
    ap.add_argument("--env", default=str(RAIZ / ".env"))
    ap.add_argument("--sin-semantico", action="store_true", help="fuerza match lexico")
    args = ap.parse_args(argv)

    cargar_env(Path(args.env))
    if args.sin_semantico:
        os.environ.pop("GEMINI_API_KEY", None)

    from tukit_catalogo.consulta import _embeder_por_entorno, calcular_vectores, emparejar
    from tukit_inteligencia.trabajos import _candidato, _normalizar, estado_desde_emparejamiento, tau

    t0 = time.perf_counter()
    conceptos, productos = asyncio.run(_indice())
    huella = hashlib.sha256(
        json.dumps(sorted((p.get("sku"), p.get("precio_cop")) for p in productos), default=str).encode()
    ).hexdigest()[:16]
    print(f"indice: {len(conceptos)} conceptos, {len(productos)} productos, huella {huella}", flush=True)

    embeder = _embeder_por_entorno()
    umbral = tau()
    listas = _leer_listas()
    instancias = []
    canal = Counter()

    for (colegio, grado), filas in listas.items():
        crudos = [
            {
                "hijo": "hijo-1",
                "orden": int(f["orden"]),
                "texto": f["texto_original"],
                "cantidad": int(f["cantidad"]) if f["cantidad"] else None,
                "instruccion_colegio": f.get("instruccion_colegio") or None,
                "url_externa": f.get("url_externa") or None,
                "tipo_item_lista": f.get("tipo_item") or None,
                "modo_lista": f.get("modo_adquisicion") or None,
            }
            for f in filas
        ]
        normalizados = _normalizar(crudos)
        buscables = [r for r in normalizados if r["busca_en_catalogo"]]
        textos = [r["texto"] for r in buscables]
        vectores = asyncio.run(calcular_vectores(textos, embeder))
        canal["semantico" if any(v is not None for v in vectores) else "lexico"] += 1
        resp = {
            (r["hijo"], r["orden"]): emparejar(t, conceptos, productos, embedding_renglon=v).a_dict()
            for r, t, v in zip(buscables, textos, vectores, strict=True)
        }

        renglones = []
        for r in normalizados:
            respuesta = resp.get((r["hijo"], r["orden"]))
            if respuesta is None:
                estado = "resuelto_auto"
                candidatos = []
                if r["tipo_item"] == "texto" and r["modo_adquisicion"] in {"mercado_abierto", "libro_libre"}:
                    estado = "sin_match"
            else:
                estado = estado_desde_emparejamiento(respuesta, umbral)
                candidatos = [_candidato(o).__dict__ for o in (respuesta.get("opciones") or ())]
            renglones.append(
                {
                    "hijo": r["hijo"],
                    "orden": r["orden"],
                    "texto": r["texto"],
                    "tipo_item": r["tipo_item"],
                    "modo_adquisicion": r["modo_adquisicion"],
                    "cantidad": r["cantidad"],
                    "estado_resolucion": estado,
                    "unidad_base": r["unidad_base"],
                    "concepto_codigo": (respuesta or {}).get("concepto_codigo"),
                    "concepto_nombre": (respuesta or {}).get("concepto_nombre"),
                    "parecido": float((respuesta or {}).get("parecido") or 0.0),
                    "candidatos": candidatos,
                    "mensaje": (respuesta or {}).get("motivo") or r.get("mensaje") or None,
                    "instruccion_colegio": r.get("instruccion_colegio"),
                    "url_externa": r.get("url_externa"),
                    "nota": r.get("nota"),
                }
            )
        instancias.append(
            {"id": f"{colegio}|{grado}", "colegio": colegio, "grado": grado, "renglones": renglones}
        )
        print(f"  {colegio} {grado}: {len(renglones)} renglones, {len(buscables)} buscados", flush=True)

    salida = {
        "generado_en": datetime.now(UTC).isoformat(),
        "catalogo": {"conceptos": len(conceptos), "productos": len(productos), "huella": huella},
        "canal": dict(canal),
        "umbral_tau": umbral,
        "instancias": instancias,
    }
    texto = json.dumps(salida, ensure_ascii=False, default=str)
    if args.salida.endswith(".gz"):
        # mtime=0: la misma foto da el mismo archivo, byte a byte.
        with gzip.GzipFile(args.salida, "wb", mtime=0) as f:
            f.write(texto.encode("utf-8"))
    else:
        Path(args.salida).write_text(texto, encoding="utf-8")
    segundos = time.perf_counter() - t0
    print(f"{len(instancias)} instancias en {segundos:.0f}s -> {args.salida}; canal {dict(canal)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
