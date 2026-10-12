"""Curaduría de huecos de catálogo sobre las listas escolares del corpus.

No es producto: lee página a página (varios grados permitidos), parsea,
empareja y consolida faltantes. Escribe reporte md+json en docs/informes/.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import traceback
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
for _ruta in (
    _RAIZ / "libs" / "py" / "tukit_comun",
    _RAIZ / "servicios" / "catalogo",
    _RAIZ / "servicios" / "inteligencia",
    _RAIZ / "ensayos",
):
    sys.path.insert(0, str(_ruta))

from entorno import carpeta_cache  # noqa: E402
from tukit_catalogo.consulta import cargar_indice, emparejar  # noqa: E402
from tukit_inteligencia.gemini import pedir_pagina  # noqa: E402
from tukit_inteligencia.paginas import renderizar  # noqa: E402
from tukit_inteligencia.parseo import parsear_renglon  # noqa: E402
from tukit_inteligencia.percepcion import (  # noqa: E402
    TOPE_PAGINAS,
    PercepcionFallida,
    grados_distintos,
    normalizar_grado,
)

# Lo que Gemini ya leyo, para no volver a pedirlo (`TUKIT_CACHE_ENSAYOS`).
DIR_PERCEPCION = carpeta_cache() / "percepcion"
OSITO_CACHE = carpeta_cache() / "ositodemiel-fase1.json"
OUT_MD = _RAIZ / "docs" / "informes" / "reporte-huecos-catalogo.md"
OUT_JSON = _RAIZ / "docs" / "informes" / "reporte-huecos-catalogo.json"
MAX_PDF_PARALELO = 2


def _sin_tildes(texto: str) -> str:
    plano = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", plano).strip()


def _slug(nombre: str) -> str:
    plano = _sin_tildes(nombre)
    plano = re.sub(r"[^a-z0-9]+", "-", plano).strip("-")
    return plano or "pdf"


def _carpeta_listas() -> Path:
    base = Path("/Users/mariapaula.rodriguez/Documents/university/TUKIT/Arquitectura")
    for p in base.iterdir():
        if p.is_dir() and "Listas" in p.name:
            return p
    raise FileNotFoundError("No hallé la carpeta Listas de Útiles")


def _colegio_de(nombre_pdf: str) -> str:
    n = Path(nombre_pdf).stem
    n = re.sub(r"\.pdf$", "", n, flags=re.I)
    mapa = {
        "ositodemiel": "Osito de Miel",
        "alamei": "Alamei",
        "bahiasolano": "Bahía Solano",
        "matilde": "Matilde",
        "modelia": "Modelia",
        "san pedro": "San Pedro",
        "jardin_merged": "Jardín (merged)",
        "listas-de-textos-escolares-colegio-san-jose-de-fontibon": "San José de Fontibón",
        "textos-y-utiles-escolares-2026-cacs.docx-1": "CACS",
        "listas 2026.pdf": "Listas 2026",
        "lista-de-textos-y-utiles-2021": "Lista textos y útiles 2021",
        "lista-de-utiles-2026": "Lista de útiles 2026",
        "listas-de-utiles-2025-act": "Listas de útiles 2025 ACT",
        "listas-textos-utiles-2026": "Listas textos útiles 2026",
    }
    clave = _sin_tildes(n)
    for k, v in mapa.items():
        if _sin_tildes(k) == clave or clave.startswith(_sin_tildes(k)):
            return v
    return n.replace("_", " ").replace("-", " ").strip()


def _accion_fuera_busqueda(demanda) -> str:
    t, m = demanda.tipo_item, demanda.modo_adquisicion
    if t == "util" and m == "venta_directa_editorial":
        return "directamente con el colegio"
    if t == "texto" and m == "venta_directa_editorial":
        return "directamente con la editorial"
    if t == "no_comprar":
        return "no comprar"
    if t == "diferido":
        return "aún no se compra"
    if t == "licencia_digital":
        return "licencia digital / plataforma"
    if t == "uniforme":
        return "aún no proveemos"
    if t == "texto" and m in {"mercado_abierto", "edicion_exclusiva", "libro_libre"}:
        return "libro por revisar a mano"
    if t == "libro_libre":
        return "libro por revisar a mano"
    return f"fuera de búsqueda ({t}/{m})"


def _accion_catalogo(estado: str) -> str:
    if estado == "abstencion":
        return "declarar atributo"
    if estado == "sin_match":
        return "agregar concepto"
    if estado == "hueco_catalogo":
        return "agregar producto"
    return estado


def leer_pdf_pagina_a_pagina(ruta: Path) -> dict:
    """Lee todas las páginas; no rechaza por varios grados. Continúa si una falla."""
    contenido = ruta.read_bytes()
    try:
        pngs = renderizar(contenido)
    except Exception as exc:
        return {
            "archivo": ruta.name,
            "error": "pdf_ilegible",
            "mensaje": str(exc),
            "paginas": 0,
            "paginas_fallidas": [],
            "grados": [],
            "items": [],
            "truncado_tope": False,
        }

    truncado = False
    if len(pngs) > TOPE_PAGINAS:
        truncado = True
        # No truncar en silencio: registrar y no leer más allá del tope de abuso.
        return {
            "archivo": ruta.name,
            "error": "archivo_demasiado_largo",
            "mensaje": f"Tiene {len(pngs)} páginas (tope {TOPE_PAGINAS}). No se leyó.",
            "paginas": len(pngs),
            "paginas_fallidas": [],
            "grados": [],
            "items": [],
            "truncado_tope": True,
        }

    items = []
    fallidas = []
    grados_crudos: list[str] = []

    for numero, png in enumerate(pngs, start=1):
        try:
            pagina = pedir_pagina(png, numero)
        except PercepcionFallida as exc:
            fallidas.append({"pagina": numero, "error": str(exc)})
            print(f"  [{ruta.name}] página {numero} falló: {exc}", flush=True)
            continue
        except Exception as exc:
            fallidas.append({"pagina": numero, "error": f"{type(exc).__name__}: {exc}"})
            print(f"  [{ruta.name}] página {numero} error: {exc}", flush=True)
            continue

        grados_pagina = [normalizar_grado(g) for g in pagina.grados if normalizar_grado(g)]
        grados_crudos.extend(pagina.grados)
        for item in pagina.items:
            desc = (item.descripcion or "").strip()
            if not desc:
                continue
            items.append(
                {
                    "descripcion": desc,
                    "cantidad": item.cantidad,
                    "confianza": item.confianza,
                    "pagina": numero,
                    "grados": grados_pagina or [],
                    "completa": pagina.completa,
                }
            )
        print(
            f"  [{ruta.name}] pág {numero}/{len(pngs)}: {len(pagina.items)} ítems, grados={grados_pagina}",
            flush=True,
        )

    grados = list(grados_distintos(grados_crudos))
    return {
        "archivo": ruta.name,
        "error": None,
        "mensaje": "",
        "paginas": len(pngs),
        "paginas_fallidas": fallidas,
        "grados": grados,
        "items": items,
        "truncado_tope": truncado,
        "papa_rechazaria_varios_grados": len(grados) > 1,
    }


def cargar_osito() -> dict:
    data = json.loads(OSITO_CACHE.read_text(encoding="utf-8"))
    grados = [normalizar_grado(g) for g in data.get("grados") or [] if normalizar_grado(g)]
    items = []
    for it in data.get("items") or []:
        texto = it.get("texto") or it.get("descripcion") or ""
        if not texto.strip():
            continue
        items.append(
            {
                "descripcion": texto.strip(),
                "cantidad": it.get("cantidad"),
                "confianza": it.get("confianza"),
                "pagina": None,
                "grados": grados,
                "completa": True,
                "reutilizado_cache": True,
            }
        )
    return {
        "archivo": "ositodemiel.pdf",
        "error": None,
        "mensaje": f"Reutilizado {OSITO_CACHE.name} de la cache (sin llamar a Gemini).",
        "paginas": data.get("paginas") or 3,
        "paginas_fallidas": [],
        "grados": grados,
        "items": items,
        "truncado_tope": False,
        "papa_rechazaria_varios_grados": len(grados) > 1,
        "fuente": "cache_ositodemiel",
    }


def procesar_un_pdf(ruta: Path) -> dict:
    slug = _slug(ruta.name)
    out = DIR_PERCEPCION / f"{slug}.json"
    if slug.startswith("ositodemiel") and OSITO_CACHE.exists():
        data = cargar_osito()
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"=== {ruta.name}: cache Osito ({len(data['items'])} ítems) ===", flush=True)
        return data

    if out.exists():
        try:
            prev = json.loads(out.read_text(encoding="utf-8"))
            if prev.get("items") is not None and prev.get("error") is None and not prev.get("forzar"):
                print(f"=== {ruta.name}: reusando {out} ===", flush=True)
                return prev
        except json.JSONDecodeError:
            pass

    print(f"=== {ruta.name}: leyendo con Gemini ===", flush=True)
    data = leer_pdf_pagina_a_pagina(ruta)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"=== {ruta.name}: listo {len(data.get('items') or [])} ítems, "
        f"fallidas={len(data.get('paginas_fallidas') or [])} ===",
        flush=True,
    )
    return data


def _clave_faltante(texto: str, estado: str, concepto: str | None, attrs: dict) -> str:
    attrs_ord = ",".join(f"{k}={v}" for k, v in sorted((attrs or {}).items()))
    return f"{_sin_tildes(texto)}|{estado}|{_sin_tildes(concepto or '')}|{attrs_ord}"


def clasificar_y_emparejar(percepciones: list[dict], conceptos, productos) -> tuple[list[dict], list[dict]]:
    resúmenes = []
    faltantes_raw = []

    for perc in percepciones:
        colegio = _colegio_de(perc["archivo"])
        cuentas = defaultdict(int)
        for it in perc.get("items") or []:
            demanda = parsear_renglon(it["descripcion"], cantidad=it.get("cantidad"))
            grados = it.get("grados") or perc.get("grados") or []
            base = {
                "colegio": colegio,
                "archivo": perc["archivo"],
                "texto": demanda.texto,
                "cantidad": demanda.cantidad,
                "grados": grados,
                "pagina": it.get("pagina"),
                "tipo_item": demanda.tipo_item,
                "modo_adquisicion": demanda.modo_adquisicion,
            }

            if not demanda.busca_en_catalogo:
                accion = _accion_fuera_busqueda(demanda)
                cuentas["fuera_busqueda"] += 1
                faltantes_raw.append(
                    {
                        **base,
                        "estado": "fuera_busqueda",
                        "concepto": None,
                        "atributos_impuestos": {},
                        "motivo": demanda.nota or "",
                        "accion": accion,
                        "texto_corregido": None,
                    }
                )
                continue

            emp = emparejar(demanda.texto, conceptos, productos)
            cuentas[emp.estado] += 1
            if emp.estado == "reconocido":
                continue

            accion = _accion_catalogo(emp.estado)
            # Heurística suave para descartar: higiene / cartilla Nacho etc. en reporte
            if emp.estado == "sin_match":
                plano = _sin_tildes(demanda.texto)
                if (
                    any(
                        x in plano
                        for x in (
                            "cepillo dental",
                            "crema dental",
                            "pasta dental",
                            "jabon",
                            "shampoo",
                            "toalla higienica",
                            "papel higienico",
                        )
                    )
                    or "cartilla" in plano
                    and "nacho" in plano
                ):
                    accion = "descartar"

            faltantes_raw.append(
                {
                    **base,
                    "estado": emp.estado,
                    "concepto": emp.concepto_nombre,
                    "concepto_codigo": emp.concepto_codigo,
                    "atributos_impuestos": dict(emp.atributos_impuestos or {}),
                    "motivo": emp.motivo or "",
                    "accion": accion,
                    "texto_corregido": emp.texto_corregido
                    if emp.texto_corregido and emp.texto_corregido != demanda.texto
                    else None,
                }
            )

        grados = perc.get("grados") or []
        resúmenes.append(
            {
                "archivo": perc["archivo"],
                "colegio": colegio,
                "paginas": perc.get("paginas") or 0,
                "grados": grados,
                "papa_rechazaria_varios_grados": bool(
                    perc.get("papa_rechazaria_varios_grados", len(grados) > 1)
                ),
                "reconocido": cuentas.get("reconocido", 0),
                "abstencion": cuentas.get("abstencion", 0),
                "sin_match": cuentas.get("sin_match", 0),
                "hueco_catalogo": cuentas.get("hueco_catalogo", 0),
                "fuera_busqueda": cuentas.get("fuera_busqueda", 0),
                "total_items": len(perc.get("items") or []),
                "paginas_fallidas": perc.get("paginas_fallidas") or [],
                "error": perc.get("error"),
                "mensaje": perc.get("mensaje") or "",
                "fuente": perc.get("fuente"),
            }
        )

    # Deduplicar
    agrupados: dict[str, dict] = {}
    for f in faltantes_raw:
        clave = _clave_faltante(
            f["texto"], f["estado"], f.get("concepto"), f.get("atributos_impuestos") or {}
        )
        if clave not in agrupados:
            agrupados[clave] = {
                "texto": f["texto"],
                "texto_corregido": f.get("texto_corregido"),
                "estado": f["estado"],
                "concepto": f.get("concepto"),
                "concepto_codigo": f.get("concepto_codigo"),
                "atributos_impuestos": f.get("atributos_impuestos") or {},
                "motivo": f.get("motivo") or "",
                "accion": f["accion"],
                "apariciones": [],
                "veces": 0,
                "colegios": set(),
                "grados": set(),
            }
        g = agrupados[clave]
        g["veces"] += 1
        g["colegios"].add(f["colegio"])
        for gr in f.get("grados") or []:
            g["grados"].add(gr)
        g["apariciones"].append(
            {
                "colegio": f["colegio"],
                "archivo": f["archivo"],
                "grados": f.get("grados") or [],
                "pagina": f.get("pagina"),
                "cantidad": f.get("cantidad"),
            }
        )
        if f.get("texto_corregido") and not g["texto_corregido"]:
            g["texto_corregido"] = f["texto_corregido"]

    unicos = []
    for g in agrupados.values():
        unicos.append(
            {
                "texto": g["texto"],
                "texto_corregido": g["texto_corregido"],
                "estado": g["estado"],
                "concepto": g["concepto"],
                "concepto_codigo": g["concepto_codigo"],
                "atributos_impuestos": g["atributos_impuestos"],
                "motivo": g["motivo"],
                "accion": g["accion"],
                "veces": g["veces"],
                "colegios": sorted(g["colegios"]),
                "grados": sorted(g["grados"]),
                "apariciones": g["apariciones"],
            }
        )

    unicos.sort(key=lambda x: (x["accion"], -x["veces"], _sin_tildes(x["texto"])))
    return resúmenes, unicos


def _md_tabla_resumen(resúmenes: list[dict]) -> str:
    lineas = [
        "| Archivo | Págs | Grados | ¿Papá rechazado? | Rec | Abst | Sin | Hueco | Fuera | Fallidas |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in resúmenes:
        grados = ", ".join(r["grados"]) if r["grados"] else "—"
        papa = "sí" if r["papa_rechazaria_varios_grados"] else "no"
        fall = (
            ", ".join(str(p["pagina"]) for p in r["paginas_fallidas"])
            if r["paginas_fallidas"]
            else ("ERROR: " + (r["error"] or "—") if r.get("error") else "—")
        )
        lineas.append(
            f"| {r['archivo']} | {r['paginas']} | {grados} | {papa} | "
            f"{r['reconocido']} | {r['abstencion']} | {r['sin_match']} | "
            f"{r['hueco_catalogo']} | {r['fuera_busqueda']} | {fall} |"
        )
    return "\n".join(lineas)


def escribir_reporte(resúmenes: list[dict], unicos: list[dict]) -> None:
    por_accion: dict[str, list[dict]] = defaultdict(list)
    for u in unicos:
        por_accion[u["accion"]].append(u)

    orden_acciones = [
        "agregar concepto",
        "agregar producto",
        "declarar atributo",
        "descartar",
        "libro por revisar a mano",
        "directamente con el colegio",
        "directamente con la editorial",
        "aún no proveemos",
        "aún no se compra",
        "no comprar",
        "licencia digital / plataforma",
    ]
    extras = [a for a in por_accion if a not in orden_acciones]
    orden = [a for a in orden_acciones if a in por_accion] + sorted(extras)

    md = []
    md.append("# Reporte de huecos de catálogo (curaduría)")
    md.append("")
    md.append(
        "Consolidado de renglones de listas escolares que **no** quedaron reconocidos "
        "tras percepción (Gemini) + parseo + emparejamiento contra el catálogo local. "
        "Los reconocidos no aparecen en el cuerpo; sí en el resumen por archivo."
    )
    md.append("")
    md.append("## Resumen por PDF")
    md.append("")
    md.append(_md_tabla_resumen(resúmenes))
    md.append("")
    for r in resúmenes:
        if r.get("mensaje") or r.get("fuente"):
            fuente = f"(fuente: {r['fuente']})" if r.get("fuente") else ""
            md.append(f"- **{r['archivo']}**: {r.get('mensaje') or ''} {fuente}".rstrip())
    md.append("")
    md.append(f"## Faltantes únicos ({len(unicos)})")
    md.append("")
    md.append(
        "Agrupados por acción sugerida. Clave de deduplicación: texto normalizado + "
        "estado + concepto + atributos impuestos."
    )
    md.append("")

    for accion in orden:
        grupo = por_accion[accion]
        md.append(f"### {accion} ({len(grupo)})")
        md.append("")
        for u in grupo:
            corr = f" → *corregido:* `{u['texto_corregido']}`" if u.get("texto_corregido") else ""
            concepto = u.get("concepto") or "—"
            attrs = u.get("atributos_impuestos") or {}
            attrs_s = ", ".join(f"{k}={v}" for k, v in sorted(attrs.items())) if attrs else "—"
            colegios = ", ".join(u["colegios"])
            grados = ", ".join(u["grados"]) if u["grados"] else "—"
            md.append(f"- **`{u['texto']}`**{corr}")
            md.append(f"  - estado: `{u['estado']}` · concepto: {concepto} · attrs: {attrs_s}")
            if u.get("motivo"):
                md.append(f"  - motivo: {u['motivo']}")
            md.append(f"  - colegios ({u['veces']}×): {colegios} · grados: {grados}")
            md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {"resumen_por_archivo": resúmenes, "faltantes_unicos": unicos},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    DIR_PERCEPCION.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        print("Falta GEMINI_API_KEY en el entorno.", file=sys.stderr)
        return 2

    carpeta = _carpeta_listas()
    pdfs = sorted({p.resolve() for p in list(carpeta.glob("*.pdf")) + list(carpeta.glob("*.PDF"))})
    pdfs = [Path(p) for p in pdfs]
    print(f"PDFs: {len(pdfs)} en {carpeta}", flush=True)

    percepciones: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_PDF_PARALELO) as pool:
        futuros = {pool.submit(procesar_un_pdf, p): p for p in pdfs}
        for fut in as_completed(futuros):
            p = futuros[fut]
            try:
                percepciones.append(fut.result())
            except Exception as exc:
                print(f"FALLO TOTAL {p.name}: {exc}", flush=True)
                traceback.print_exc()
                percepciones.append(
                    {
                        "archivo": p.name,
                        "error": "excepcion",
                        "mensaje": str(exc),
                        "paginas": 0,
                        "paginas_fallidas": [],
                        "grados": [],
                        "items": [],
                        "truncado_tope": False,
                        "papa_rechazaria_varios_grados": False,
                    }
                )

    percepciones.sort(key=lambda d: d["archivo"].lower())

    print("Cargando índice de catálogo…", flush=True)
    conceptos, productos = asyncio.run(cargar_indice())
    print(f"Conceptos={len(conceptos)} productos={len(productos)}", flush=True)

    resúmenes, unicos = clasificar_y_emparejar(percepciones, conceptos, productos)
    escribir_reporte(resúmenes, unicos)
    print(f"Escrito {OUT_MD}", flush=True)
    print(f"Escrito {OUT_JSON}", flush=True)
    print(f"Faltantes únicos: {len(unicos)}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
