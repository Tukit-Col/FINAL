"""Piezas del ensayo de ajuste de la instruccion de lectura (ver ajuste_instruccion.py)."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CACHE = RAIZ / ".cache" / "ajuste_instruccion"
PDFS = CACHE / "pdfs"
RESPUESTAS = CACHE / "respuestas"
LIBRO_GASTO = CACHE / "gasto.jsonl"
GOLD_CSV = RAIZ / "ensayos" / "calibracion" / "datos" / "lectura_gold_80.csv"
SALIDA = RAIZ / "ensayos" / "calibracion" / "salidas"
CGS_DIR = (
    RAIZ.parent / "_archivo" / "2026-11-05" / "borradores_arquitectura" / "Arquitectura" / "Listas de Útiles"
)

MODELO = "gemini-3.5-flash-lite"
USD_IN, USD_OUT = 0.10, 0.40

UMBRAL_FUZZY = 0.75


def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r"[^\w\sáéíóúñü]", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto


def calcular_prf1(items_pred: list[dict], items_gold: list[dict]) -> dict:
    if not items_gold:
        return {"precision": 0, "recall": 0, "f1": 0, "tp": 0, "fp": len(items_pred), "fn": 0, "matches": []}
    usados_gold = set()
    tp = 0
    matches = []
    gold_norm = [normalizar(g.get("descripcion", "")) for g in items_gold]
    gold_map: dict[str, list[int]] = {}
    for j, g_text in enumerate(gold_norm):
        gold_map.setdefault(g_text, []).append(j)
    items_pendientes = []
    for ip, pred in enumerate(items_pred):
        desc_pred = pred.get("descripcion", "")
        norm_p = normalizar(desc_pred)
        match_encontrado = False
        if norm_p in gold_map:
            for idx in gold_map[norm_p]:
                if idx not in usados_gold:
                    tp += 1
                    usados_gold.add(idx)
                    matches.append(
                        {
                            "pred": desc_pred,
                            "gold": items_gold[idx].get("descripcion", ""),
                            "score": 1.0,
                            "ip": ip,
                            "ig": idx,
                        }
                    )
                    match_encontrado = True
                    break
        if not match_encontrado:
            items_pendientes.append((ip, pred, norm_p))
    for ip, pred, norm_p in items_pendientes:
        desc_pred = pred.get("descripcion", "")
        mejor_score = 0
        mejor_idx = -1
        set_p = set(norm_p.split())
        chars_p = set(norm_p)
        for j, g_text in enumerate(gold_norm):
            if j in usados_gold:
                continue
            len_p = len(norm_p)
            len_g = len(g_text)
            if abs(len_p - len_g) > max(len_p, len_g) * 0.35:
                continue
            chars_g = set(g_text)
            if len(chars_p & chars_g) / max(len(chars_p | chars_g), 1) < 0.55:
                continue
            set_g = set(g_text.split())
            if not (set_p & set_g) and len(norm_p) > 10:
                if norm_p[:4] != g_text[:4]:
                    continue
            score = SequenceMatcher(None, norm_p, g_text).ratio()
            if score > mejor_score:
                mejor_score = score
                mejor_idx = j
        if mejor_score >= UMBRAL_FUZZY and mejor_idx >= 0:
            tp += 1
            usados_gold.add(mejor_idx)
            matches.append(
                {
                    "pred": desc_pred,
                    "gold": items_gold[mejor_idx].get("descripcion", ""),
                    "score": round(mejor_score, 3),
                    "ip": ip,
                    "ig": mejor_idx,
                }
            )
    fp = len(items_pred) - tp
    fn = len(items_gold) - tp
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "matches": matches,
    }


def agregar(metricas: list[dict]) -> dict:
    tp = sum(m["tp"] for m in metricas)
    fp = sum(m["fp"] for m in metricas)
    fn = sum(m["fn"] for m in metricas)
    p = tp / max(tp + fp, 1)
    r = tp / max(tp + fn, 1)
    f1 = 2 * p * r / max(p + r, 1e-10)
    k = max(len(metricas), 1)
    return {
        "P": p,
        "R": r,
        "F1_micro": f1,
        "F1_macro": sum(m["f1"] for m in metricas) / k,
        "P_macro": sum(m["precision"] for m in metricas) / k,
        "R_macro": sum(m["recall"] for m in metricas) / k,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "listas": len(metricas),
    }


def bootstrap(metricas: list[dict], b: int = 2000, semilla: int = 7) -> dict:
    import random

    rnd = random.Random(semilla)
    vals: dict[str, list[float]] = {"P": [], "R": [], "F1_micro": [], "F1_macro": []}
    for _ in range(b):
        mm = [metricas[rnd.randrange(len(metricas))] for _ in metricas]
        a = agregar(mm)
        for k in vals:
            vals[k].append(a[k])
    out = {}
    for k, v in vals.items():
        v.sort()
        out[k] = [v[int(0.025 * b)], v[int(0.975 * b) - 1]]
    return out


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def tipos_de_error(pred: list[dict], gold: list[dict], m: dict) -> dict:
    ip_ok = {x["ip"] for x in m["matches"]}
    ig_ok = {x["ig"] for x in m["matches"]}
    fps = [i for i in range(len(pred)) if i not in ip_ok]
    fns = [j for j in range(len(gold)) if j not in ig_ok]
    usados_p: set[int] = set()
    usados_g: set[int] = set()
    cuenta = {
        k: 0
        for k in (
            "fila_partida",
            "renglones_unidos",
            "duplicado",
            "texto_alterado",
            "extra_no_pedido",
            "omitido",
            "cantidad_distinta",
        )
    }
    ejemplos: dict[str, list] = {k: [] for k in cuenta}
    np_ = {i: normalizar(pred[i]["descripcion"]) for i in fps}
    ng_ = {j: normalizar(gold[j]["descripcion"]) for j in fns}
    for j in fns:
        partes = [i for i in fps if i not in usados_p and len(np_[i]) >= 3 and np_[i] in ng_[j]]
        if len(partes) >= 2:
            cuenta["fila_partida"] += 1
            usados_g.add(j)
            usados_p.update(partes)
            ejemplos["fila_partida"].append(
                (gold[j]["descripcion"], [pred[i]["descripcion"] for i in partes])
            )
    for i in fps:
        if i in usados_p:
            continue
        partes = [j for j in fns if j not in usados_g and len(ng_[j]) >= 3 and ng_[j] in np_[i]]
        if len(partes) >= 2:
            cuenta["renglones_unidos"] += 1
            usados_p.add(i)
            usados_g.update(partes)
            ejemplos["renglones_unidos"].append(
                (pred[i]["descripcion"], [gold[j]["descripcion"] for j in partes])
            )
    ok_norm = {normalizar(pred[i]["descripcion"]) for i in ip_ok}
    for i in fps:
        if i in usados_p:
            continue
        if np_[i] in ok_norm:
            cuenta["duplicado"] += 1
            usados_p.add(i)
            ejemplos["duplicado"].append(pred[i]["descripcion"])
    for i in fps:
        if i in usados_p:
            continue
        mejor, mj = 0.0, -1
        for j in fns:
            if j in usados_g:
                continue
            r = _ratio(pred[i]["descripcion"], gold[j]["descripcion"])
            if r > mejor:
                mejor, mj = r, j
        if mejor >= 0.5:
            cuenta["texto_alterado"] += 1
            usados_p.add(i)
            usados_g.add(mj)
            ejemplos["texto_alterado"].append((pred[i]["descripcion"], gold[mj]["descripcion"]))
    for i in fps:
        if i not in usados_p:
            cuenta["extra_no_pedido"] += 1
            ejemplos["extra_no_pedido"].append(pred[i]["descripcion"])
    for j in fns:
        if j not in usados_g:
            cuenta["omitido"] += 1
            ejemplos["omitido"].append(gold[j]["descripcion"])
    for x in m["matches"]:
        cp = pred[x["ip"]].get("cantidad")
        cg = gold[x["ig"]].get("cantidad")
        cp = 1 if cp in (None, 0) else int(cp)
        if cg is not None and int(cg) != cp:
            cuenta["cantidad_distinta"] += 1
            ejemplos["cantidad_distinta"].append((x["gold"], cg, cp))
    return {"cuenta": cuenta, "ejemplos": ejemplos}


_PG = {**os.environ, "PGGSSENCMODE": "disable", "PGPASSWORD": "tukit"}


def _select(base: str, sql: str) -> list[list[str]]:
    assert sql.lstrip().lower().startswith("select")
    r = subprocess.run(
        [
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            "tukit",
            "-d",
            base,
            "-At",
            "-c",
            f"copy ({sql}) to stdout with csv",
        ],
        capture_output=True,
        text=True,
        env=_PG,
        timeout=300,
        check=True,
    )
    return list(csv.reader(r.stdout.splitlines()))


def exportar() -> None:
    import io

    col = {i: n for i, n in _select("tukit_identidad", "select id, nombre from colegio")}
    filas = _select(
        "tukit_catalogo",
        """select v.id, l.colegio_id, l.grado, l.anio_lectivo, v.numero,
        (select count(*) from correccion_lista k where k.version_id=v.id), i.orden, i.texto_original, i.cantidad
        from item_lista_oficial i join version_lista_oficial v on v.id=i.version_id join lista_oficial l on l.id=v.lista_id
        where v.vigente and v.revisada_en is not null order by 2,3,7""",
    )
    GOLD_CSV.parent.mkdir(parents=True, exist_ok=True)
    with GOLD_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "version_id",
                "colegio",
                "grado",
                "anio",
                "numero_version",
                "correcciones_version",
                "orden",
                "descripcion",
                "cantidad",
            ]
        )
        for vid, cid, g, a, num, nc, o, t, c in filas:
            w.writerow([vid, col.get(cid, cid), g, a, num, nc, o, t, c])
    PDFS.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            "psql",
            "-h",
            "127.0.0.1",
            "-U",
            "tukit",
            "-d",
            "tukit_catalogo",
            "-At",
            "-c",
            "copy (select t.version_id, encode(t.documento,'hex') from tarea_importacion t join "
            "version_lista_oficial v on v.id=t.version_id where v.vigente and v.revisada_en is not null "
            "and t.documento is not null) to stdout",
        ],
        capture_output=True,
        text=True,
        env=_PG,
        timeout=300,
        check=True,
    )
    n = 0
    for linea in io.StringIO(r.stdout):
        vid, hx = linea.rstrip("\n").split("\t")
        hx = hx[2:] if hx.startswith("\\x") else hx
        (PDFS / f"{vid}.pdf").write_bytes(bytes.fromhex(hx))
        n += 1
    print(f"gold: {len(filas)} renglones -> {GOLD_CSV.relative_to(RAIZ)}; PDFs: {n}")


def cargar_listas() -> dict[str, dict]:
    listas: dict[str, dict] = {}
    for r in csv.DictReader(GOLD_CSV.open(encoding="utf-8")):
        d = listas.setdefault(
            r["version_id"],
            {
                "id": r["version_id"],
                "colegio": r["colegio"],
                "grado": r["grado"],
                "numero_version": int(r["numero_version"]),
                "correcciones": int(r["correcciones_version"]),
                "gold": [],
            },
        )
        d["gold"].append({"descripcion": r["descripcion"], "cantidad": int(r["cantidad"])})
    for d in listas.values():
        d["pdf"] = PDFS / f"{d['id']}.pdf"
    return listas


_LOCK = threading.Lock()
_RENDER = threading.Lock()
TOPE_USD = float(os.environ.get("GEMINI_BUDGET_USD", "5")) * 0.8


class PresupuestoAgotado(RuntimeError):
    pass


def gasto_total() -> float:
    if not LIBRO_GASTO.exists():
        return 0.0
    return sum(json.loads(x)["usd"] for x in LIBRO_GASTO.read_text().splitlines() if x.strip())


def _registrar(entrada: dict) -> float:
    with _LOCK:
        LIBRO_GASTO.parent.mkdir(parents=True, exist_ok=True)
        with LIBRO_GASTO.open("a") as f:
            f.write(json.dumps(entrada) + "\n")
        return gasto_total()


def costo(uso: dict) -> float:
    ent = int(uso.get("promptTokenCount") or 0)
    sal = int(uso.get("candidatesTokenCount") or 0) + int(uso.get("thoughtsTokenCount") or 0)
    return ent * USD_IN / 1e6 + sal * USD_OUT / 1e6


def _pedir(instruccion: str, png: bytes, numero: int) -> dict:
    from tukit_inteligencia import gemini

    clave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not clave:
        raise RuntimeError("falta GEMINI_API_KEY")
    cuerpo = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{instruccion}\n\nEsta es la pagina {numero}."},
                    {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png).decode()}},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": gemini._ESQUEMA,
        },
    }
    pedido = urllib.request.Request(
        gemini._URL.format(modelo=MODELO, clave=clave),
        data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    ultimo_error = None
    for intento in range(3):
        try:
            with urllib.request.urlopen(pedido, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            ultimo_error = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as exc:
            ultimo_error = type(exc).__name__
        time.sleep(4 * (intento + 1))
    raise RuntimeError(f"Gemini fallo: {ultimo_error}")


def leer_documento(pdf: Path, version: str, instruccion: str, max_paginas: int | None = None) -> dict:
    from tukit_inteligencia.paginas import renderizar

    contenido = pdf.read_bytes()
    huella = hashlib.sha256(contenido).hexdigest()
    hi = hashlib.sha256(instruccion.encode()).hexdigest()[:10]
    carpeta = RESPUESTAS / MODELO / f"{version}-{hi}" / huella[:24]
    carpeta.mkdir(parents=True, exist_ok=True)
    with _RENDER:
        paginas = renderizar(contenido)
    if max_paginas:
        paginas = paginas[:max_paginas]
    items: list[dict] = []
    usd = 0.0
    llamadas = 0
    for numero, png in enumerate(paginas, start=1):
        f = carpeta / f"p{numero:02d}.json"
        if f.exists():
            crudo = json.loads(f.read_text())
        else:
            if gasto_total() >= TOPE_USD:
                raise PresupuestoAgotado(f"gasto {gasto_total():.4f} >= {TOPE_USD:.2f} USD")
            crudo = _pedir(instruccion, png, numero)
            f.write_text(json.dumps(crudo, ensure_ascii=False))
            c = costo(crudo.get("usageMetadata") or {})
            total = _registrar(
                {
                    "t": time.time(),
                    "version": version,
                    "huella": huella[:16],
                    "pagina": numero,
                    "uso": crudo.get("usageMetadata"),
                    "usd": c,
                }
            )
            usd += c
            llamadas += 1
            if total >= TOPE_USD:
                raise PresupuestoAgotado(f"gasto acumulado {total:.4f} USD alcanzo el 80 %")
        try:
            texto = crudo["candidates"][0]["content"]["parts"][0]["text"]
            pagina = json.loads(texto)
            for it in pagina.get("items") or []:
                if str(it.get("descripcion", "")).strip():
                    items.append({"descripcion": it["descripcion"], "cantidad": it.get("cantidad")})
        except (KeyError, IndexError, ValueError, TypeError):
            pass
    return {
        "items": items,
        "paginas": len(paginas),
        "usd_nuevo": usd,
        "llamadas_nuevas": llamadas,
        "huella": huella,
    }
