"""Aumentacion de datos para CALIBRAR constantes y para PRUEBAS DE ESTRES (no entrena ningun modelo).
Uso: uv run python ensayos/calibracion/aumentacion.py"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import random
import re
import sys
import time
import unicodedata
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import barrido as b  # noqa: E402
import clasificacion as k  # noqa: E402
from particion import SEMILLA_BASE, SEMILLAS, partir  # noqa: E402

SEMILLA_PERT = 20261115
N_VARIANTES = 5
LEVE, FUERTE = "leve", "fuerte"
RUTA_CACHE = k.DATOS / "vectores_perturbados.npz"
RESCATE_APAGADO = 1.01
ACTUAL_SR = {**k.ACTUAL, "res_cos": RESCATE_APAGADO}
LEXICO = {**k.ACTUAL, "w_cos": 0.0, "res_cos": RESCATE_APAGADO}

PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
VECINAS = {
    "q": "wa",
    "w": "qes",
    "e": "wrd",
    "r": "etf",
    "t": "ryg",
    "y": "tuh",
    "u": "yij",
    "i": "uok",
    "o": "ipl",
    "p": "ol",
    "a": "qsz",
    "s": "awdx",
    "d": "sefc",
    "f": "drgv",
    "g": "fthb",
    "h": "gyjn",
    "j": "hukm",
    "k": "jil",
    "l": "kop",
    "z": "asx",
    "x": "zsc",
    "c": "xdv",
    "v": "cfb",
    "b": "vgn",
    "n": "bhm",
    "m": "nj",
}
ABREVIATURAS = {
    "cuaderno": "cdno.",
    "cuadriculado": "cuad.",
    "cuadriculada": "cuad.",
    "lápiz": "lap.",
    "lapiz": "lap.",
    "cartulina": "cart.",
    "hojas": "hjs",
    "hoja": "hj",
    "unidades": "und.",
    "unidad": "und.",
    "tamaño": "tam.",
    "pequeño": "peq.",
    "pequeña": "peq.",
    "grande": "gde.",
    "carpeta": "carp.",
    "borrador": "borr.",
    "colores": "col.",
    "color": "col.",
    "marcador": "marc.",
    "marcadores": "marc.",
    "paquete": "paq.",
    "centímetros": "cm",
    "rayado": "ray.",
    "plástica": "plást.",
    "plástico": "plást.",
    "blanco": "bco.",
    "blancas": "bcas.",
    "pegante": "peg.",
    "tijeras": "tij.",
}
PREFIJOS_LEVE = ["Material escolar:", "Útiles:", "Materiales:", "Lista de útiles:"]
PREFIJOS_FUERTE = [
    "Kit de aseo:",
    "Papelería:",
    "Kit de arte:",
    "Para el salón:",
    "Kit de aseo personal -",
    "Material de apoyo:",
]
MARCAS = ["Norma", "Scribe", "Faber-Castell", "Pelikan", "Mirado", "Prismacolor", "Pentel"]
ATRIBUTOS = ["rojo", "azul", "grande", "x12", "nuevo"]
NO_PLURAL = {
    "para",
    "como",
    "entre",
    "sobre",
    "desde",
    "hasta",
    "cada",
    "pero",
    "tipo",
    "este",
    "esta",
    "ese",
    "esa",
}
TIPOS = [
    "tipeo",
    "tildes",
    "mayusculas",
    "plural",
    "abreviaturas",
    "orden",
    "prefijo",
    "sufijo",
    "ocr",
    "espacios",
    "marca",
]
TIPOS_TODOS = TIPOS + ["mixta"]


def _rng(*partes) -> random.Random:
    return random.Random(zlib.crc32("|".join(str(p) for p in partes).encode()))


def _palabras(t: str, minimo: int = 4) -> list[re.Match]:
    return [m for m in PALABRA.finditer(t) if len(m.group()) >= minimo]


def _reemplazar(t: str, cambios: dict[int, tuple[int, str]]) -> str:
    for ini in sorted(cambios, reverse=True):
        fin, nuevo = cambios[ini]
        t = t[:ini] + nuevo + t[fin:]
    return t


def p_tipeo(t: str, sev: str, r: random.Random) -> str:
    ms = _palabras(t)
    if not ms:
        return t
    n = 1 if sev == LEVE else max(2, math.ceil(0.25 * len(ms)))
    cambios = {}
    for m in r.sample(ms, min(n, len(ms))):
        w = m.group()
        i = r.randrange(1, len(w) - 1)
        op = r.choice(["trans", "omit", "dup", "vecina"])
        if op == "trans":
            w2 = w[: i - 1] + w[i] + w[i - 1] + w[i + 1 :] if i >= 1 else w
        elif op == "omit":
            w2 = w[:i] + w[i + 1 :]
        elif op == "dup":
            w2 = w[:i] + w[i] + w[i:]
        else:
            v = VECINAS.get(w[i].lower())
            w2 = w[:i] + (r.choice(v) if v else w[i]) + w[i + 1 :]
        cambios[m.start()] = (m.end(), w2)
    return _reemplazar(t, cambios)


def _sin_tildes(t: str, tambien_enie: bool) -> str:
    out = []
    for ch in t:
        if ch in "ñÑ" and not tambien_enie:
            out.append(ch)
            continue
        out.append("".join(c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn"))
    return "".join(out)


def p_tildes(t: str, sev: str, r: random.Random) -> str:
    if sev == LEVE:
        return _sin_tildes(t, False)
    t = _sin_tildes(t, True)
    ms = [m for m in _palabras(t) if re.search(r"[aeiou]", m.group())]
    cambios = {}
    for m in r.sample(ms, min(2, len(ms))):
        w = m.group()
        pos = [i for i, c in enumerate(w) if c in "aeiou"]
        i = r.choice(pos)
        w2 = w[:i] + {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}[w[i]] + w[i + 1 :]
        cambios[m.start()] = (m.end(), w2)
    return _reemplazar(t, cambios)


def p_mayusculas(t: str, sev: str, r: random.Random) -> str:
    if sev == LEVE:
        return t.lower()
    if r.random() < 0.5:
        return t.upper()
    return "".join(c.swapcase() if r.random() < 0.3 else c.lower() for c in t)


def _alternar_numero(w: str) -> str:
    wl = w.lower()
    if wl in NO_PLURAL or len(w) < 4:
        return w
    if wl.endswith("ces"):
        return w[:-3] + "z"
    if wl.endswith("ones"):
        return w[:-4] + "ón"
    if wl.endswith("ón"):
        return w[:-2] + "ones"
    if wl.endswith("es") and len(w) > 4 and wl[-3] not in "aeiou":
        return w[:-2]
    if wl.endswith("s"):
        return w[:-1]
    if wl.endswith("z"):
        return w[:-1] + "ces"
    return w + ("s" if wl[-1] in "aeiouáéíóú" else "es")


def p_plural(t: str, sev: str, r: random.Random) -> str:
    ms = _palabras(t)
    if not ms:
        return t
    elegidas = [r.choice(ms)] if sev == LEVE else ms
    return _reemplazar(t, {m.start(): (m.end(), _alternar_numero(m.group())) for m in elegidas})


def p_abreviaturas(t: str, sev: str, r: random.Random) -> str:
    ms = [m for m in PALABRA.finditer(t) if m.group().lower() in ABREVIATURAS]
    if not ms:
        return t
    elegidas = [r.choice(ms)] if sev == LEVE else ms
    return _reemplazar(t, {m.start(): (m.end(), ABREVIATURAS[m.group().lower()]) for m in elegidas})


def p_orden(t: str, sev: str, r: random.Random) -> str:
    pal = t.split()
    if len(pal) < 2:
        return t
    if sev == LEVE:
        i = r.randrange(len(pal) - 1)
        pal[i], pal[i + 1] = pal[i + 1], pal[i]
    else:
        orig = pal[:]
        for _ in range(5):
            r.shuffle(pal)
            if pal != orig:
                break
    return " ".join(pal)


def p_prefijo(t: str, sev: str, r: random.Random) -> str:
    if sev == LEVE:
        return f"{r.choice(PREFIJOS_LEVE)} {t}"
    return f"{r.choice(PREFIJOS_FUERTE)} {r.choice(PREFIJOS_LEVE + PREFIJOS_FUERTE)} {t}"


def p_sufijo(t: str, sev: str, r: random.Random) -> str:
    if sev == LEVE:
        return t.rstrip() + r.choice([" x 12", " x 2", " (2 unidades)", " x 6"])
    return (
        t.rstrip() + r.choice([" (2 unidades)", " x 12"]) + r.choice([" - cant. 3", " x 24 pp", " (3 und.)"])
    )


OCR = [
    ("rn", "m"),
    ("m", "rn"),
    ("l", "1"),
    ("1", "l"),
    ("O", "0"),
    ("0", "O"),
    ("i", "l"),
    ("l", "i"),
    ("o", "0"),
]


def p_ocr(t: str, sev: str, r: random.Random) -> str:
    sitios = []
    for a, b2 in OCR:
        for m in re.finditer(re.escape(a), t):
            en_palabra = (
                m.start() > 0 and t[m.start() - 1].isalnum() or (m.end() < len(t) and t[m.end()].isalnum())
            )
            if en_palabra:
                sitios.append((m.start(), m.end(), b2))
    if not sitios:
        return t
    n = 1 if sev == LEVE else max(2, round(0.12 * len(sitios)))
    cambios, ocupados = {}, set()
    for ini, fin, nuevo in r.sample(sitios, min(len(sitios), n * 3)):
        if len(cambios) >= n:
            break
        if ocupados & set(range(ini, fin)):
            continue
        cambios[ini] = (fin, nuevo)
        ocupados |= set(range(ini, fin))
    return _reemplazar(t, cambios)


def p_espacios(t: str, sev: str, r: random.Random) -> str:
    pal = t.split(" ")
    if sev == LEVE:
        i = r.randrange(len(pal))
        pal[i] = pal[i] + " "
        return " ".join(pal).rstrip() + " ."
    ms = [m for m in _palabras(t, 6)]
    if ms:
        m = r.choice(ms)
        cut = r.randrange(2, len(m.group()) - 1)
        t = t[: m.start() + cut] + " " + t[m.start() + cut :]
    pal = t.split(" ")
    for _ in range(max(2, len(pal) // 4)):
        i = r.randrange(len(pal))
        pal[i] = pal[i] + r.choice([" ", " ,", " ;", "  ", " ."])
    return " ".join(pal) + " ."


def p_marca(t: str, sev: str, r: random.Random) -> str:
    base = t.rstrip().rstrip(".")
    if sev == LEVE:
        return f"{base} {r.choice(MARCAS)}"
    return f"{base}{r.choice(MARCAS)} {r.choice(ATRIBUTOS)}"


FUNCIONES = {
    "tipeo": p_tipeo,
    "tildes": p_tildes,
    "mayusculas": p_mayusculas,
    "plural": p_plural,
    "abreviaturas": p_abreviaturas,
    "orden": p_orden,
    "prefijo": p_prefijo,
    "sufijo": p_sufijo,
    "ocr": p_ocr,
    "espacios": p_espacios,
    "marca": p_marca,
}


def perturbar(texto: str, tipo: str, sev: str, semilla: str = "") -> str:
    r = _rng(SEMILLA_PERT, tipo, sev, semilla, texto)
    if tipo == "mixta":
        t = texto
        for sub in r.sample(TIPOS, 3):
            t = FUNCIONES[sub](t, sev, _rng(SEMILLA_PERT, sub, sev, semilla, texto))
        return t
    return FUNCIONES[tipo](texto, sev, r)


def variante_aumentada(texto: str, j: int) -> str:
    r = _rng(SEMILLA_PERT, "aug", j, texto)
    sev = LEVE if r.random() < 0.7 else FUERTE
    t = texto
    for sub in r.sample(TIPOS, r.choice([1, 2, 3])):
        t = FUNCIONES[sub](t, sev, _rng(SEMILLA_PERT, "aug", j, sub, texto))
    return t if t.strip() else texto


def conjuntos_de_estres(textos: list[str]) -> dict[tuple[str, str], list[str]]:
    return {(tp, sv): [perturbar(t, tp, sv) for t in textos] for tp in TIPOS_TODOS for sv in (LEVE, FUERTE)}


def conjuntos_aumentados(textos: list[str]) -> list[list[str]]:
    return [[variante_aumentada(t, j) for t in textos] for j in range(N_VARIANTES)]


LLAMADAS = {"solicitudes": 0, "textos": 0, "reintentos": 0, "desde_cache": 0}


def _cargar_cache() -> dict[str, np.ndarray]:
    if not RUTA_CACHE.exists():
        return {}
    z = np.load(RUTA_CACHE, allow_pickle=False)
    return dict(zip(z["textos"].tolist(), z["vectores"], strict=True))


def _guardar_cache(cache: dict[str, np.ndarray]) -> None:
    ts = sorted(cache)
    np.savez_compressed(
        RUTA_CACHE, textos=np.array(ts), vectores=np.array([cache[t] for t in ts], dtype=np.float16)
    )


def vectorizar_nuevos(textos: set[str], hilos: int = 4) -> dict[str, np.ndarray]:
    cache = _cargar_cache()
    faltan = sorted(t for t in textos if t not in cache)
    LLAMADAS["desde_cache"] = len(textos) - len(faltan)
    if faltan:
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            raise RuntimeError("falta GEMINI_API_KEY: solo se puede hacer la parte lexica")
        from tukit_catalogo.embeddings import embeder_gemini

        lotes = [faltan[i : i + 100] for i in range(0, len(faltan), 100)]

        ultimo = [""]

        def pedir(lote: list[str]) -> list[list[float]]:
            for intento in range(25):
                try:
                    return embeder_gemini(lote)
                except Exception as exc:  # noqa: BLE001
                    LLAMADAS["reintentos"] += 1
                    ultimo[0] = str(exc)[:200]
                    time.sleep(min(60, 2 + 4 * intento))
            raise RuntimeError(f"Gemini no respondio tras 25 intentos: {ultimo[0]}")

        t0 = time.time()
        with ThreadPoolExecutor(hilos) as ex:
            for n, (lote, vs) in enumerate(zip(lotes, ex.map(pedir, lotes), strict=True), 1):
                LLAMADAS["solicitudes"] += 1
                LLAMADAS["textos"] += len(lote)
                for t, v in zip(lote, vs, strict=True):
                    cache[t] = np.array(v, dtype=np.float16)
                if n % 20 == 0:
                    _guardar_cache(cache)
                    print(f"  vectores {n}/{len(lotes)} lotes, {time.time() - t0:.0f}s", flush=True)
        _guardar_cache(cache)
    return cache


def _unit(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.float64)
    return v / (np.linalg.norm(v) or 1.0)


def contexto_con_textos(cx: b.Contexto, textos: list[str], cache: dict[str, np.ndarray] | None) -> b.Contexto:
    lex = k.lexico_de(cx.d.conceptos)
    vec = None
    if cx.d.vectores is not None and cache is not None:
        base = {t: cx.d.vectores[i] for i, t in enumerate(cx.d.textos)}
        vec = np.array([base[t] if t in base else _unit(cache[t]) for t in textos])
    d2 = dataclasses.replace(
        cx.d, textos=list(textos), vectores=vec, corr=[k.corregir(t, lex) for t in textos]
    )
    c2 = object.__new__(b.Contexto)
    c2.d, c2.r = d2, k.construir_rasgos(d2)
    c2.y, c2.u, c2.lista, c2.colegio, c2._cache = cx.y, cx.u, cx.lista, cx.colegio, {}
    return c2


class Pila:
    def __init__(self, cx: b.Contexto, cxs: list[b.Contexto]):
        self.cx, self.cxs = cx, [cx, *cxs]
        self.n = len(cx.y)
        self.y = np.tile(cx.y, len(self.cxs))
        self.lista = np.tile(cx.lista, len(self.cxs))
        self.origen = np.repeat(np.arange(len(self.cxs)), self.n)
        self.textos = [t for c in self.cxs for t in (c.d.textos[i] for i in c.u)]
        self.base = np.tile(cx.u, len(self.cxs))
        self._cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}

    def puntuar(self, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
        clave = tuple(round(cfg[c], 6) for c in k.CLAVES_PUNTAJE)
        if clave not in self._cache:
            ps = [c.puntuar(cfg) for c in self.cxs]
            self._cache[clave] = (np.concatenate([p for p, _ in ps]), np.concatenate([s for _, s in ps]))
        return self._cache[clave]

    def medir(self, cfg: dict, mask: np.ndarray) -> dict:
        p, s = self.puntuar(cfg)
        return k.metricas(p[mask], s[mask], self.y[mask], cfg["corte"], cfg["tau"])


def mascaras(pila: Pila, parte: dict[str, list[str]], textos_prohibidos: set[str]) -> dict:
    cx = pila.cx
    en = {p: np.isin(pila.lista, ls) for p, ls in parte.items()}
    limpias = pila.origen == 0
    textos_vp_base = {
        cx.d.textos[i] for i in np.unique(cx.u[np.isin(cx.lista, parte["validacion"] + parte["prueba"])])
    }
    base_vp = np.array([cx.d.textos[i] in textos_vp_base for i in range(len(cx.d.textos))])[pila.base]
    cadena_prohibida = np.array([t in textos_prohibidos for t in pila.textos])
    var_ok = ~limpias & en["entrenamiento"] & ~base_vp & ~cadena_prohibida
    return {
        "train_limpio": en["entrenamiento"] & limpias,
        "train_aum": (en["entrenamiento"] & limpias) | var_ok,
        "val": en["validacion"] & limpias,
        "prueba": en["prueba"] & limpias,
        "_variantes_excluidas_por_texto_base": int((~limpias & en["entrenamiento"] & base_vp).sum()),
        "_variantes_excluidas_por_cadena": int(
            (~limpias & en["entrenamiento"] & ~base_vp & cadena_prohibida).sum()
        ),
        "_variantes_usadas": int(var_ok.sum()),
    }


def comprobar_fuga(pila: Pila, parte: dict[str, list[str]], m: dict, cadenas_vp: set[str]) -> dict:
    cx = pila.cx
    tr_aum = m["train_aum"]
    listas_tr = {l for l in pila.lista[tr_aum]}
    sin_lista = not (listas_tr & set(parte["validacion"]) or listas_tr & set(parte["prueba"])) and not (
        set(parte["entrenamiento"]) & (set(parte["validacion"]) | set(parte["prueba"]))
    )
    var_tr = tr_aum & (pila.origen > 0)
    base_tr_var = {cx.d.textos[i] for i in np.unique(pila.base[var_tr])}
    base_vp = {
        cx.d.textos[i] for i in np.unique(cx.u[np.isin(cx.lista, parte["validacion"] + parte["prueba"])])
    }
    cadenas_tr_var = {pila.textos[i] for i in np.where(var_tr)[0]}
    return {
        "listas_compartidas_entre_particiones": 0 if sin_lista else 1,
        "variantes_de_entrenamiento_con_texto_base_de_val_o_prueba": len(base_tr_var & base_vp),
        "cadenas_de_variantes_de_entrenamiento_iguales_a_algun_texto_de_val_o_prueba": len(
            cadenas_tr_var & cadenas_vp
        ),
        "renglones_limpios_de_entrenamiento_con_texto_base_tambien_en_val_o_prueba": int(
            sum(1 for i in np.where(m["train_limpio"])[0] if cx.d.textos[pila.base[i]] in base_vp)
        ),
    }


def cadenas_prohibidas(
    cx: b.Contexto, parte: dict[str, list[str]], estres: dict[tuple[str, str], list[str]]
) -> set[str]:
    idx = np.unique(cx.u[np.isin(cx.lista, parte["validacion"] + parte["prueba"])])
    s = {cx.d.textos[i] for i in idx}
    for lst in estres.values():
        s |= {lst[i] for i in idx}
    return s


def construir_pila(cx: b.Contexto, con_vectores: bool = True):
    textos = cx.d.textos
    estres = conjuntos_de_estres(textos)
    aum = conjuntos_aumentados(textos)
    cache = None
    if con_vectores and cx.d.vectores is not None:
        todos = {t for lst in aum for t in lst} | {t for lst in estres.values() for t in lst}
        cache = vectorizar_nuevos(todos - set(textos))
    cxs = [contexto_con_textos(cx, lst, cache) for lst in aum]
    return Pila(cx, cxs), estres, aum, cache


GRILLA = {
    "piso": [0.5, 0.55, 0.6, 0.65, 0.7],
    "w_jac": [0.2, 0.3, 0.4, 0.5, 0.6],
    "w_cos": [0.0, 0.05, 0.1, 0.15, 0.2, 0.3],
}
CORTES = [0.4, 0.45, 0.5, 0.55, 0.6]
REJ_UNICA = {
    "piso": [round(x, 3) for x in np.arange(0.30, 0.9001, 0.05)],
    "w_jac": [round(x, 3) for x in np.arange(0.0, 0.8001, 0.05)],
    "w_cos": [round(x, 3) for x in np.arange(0.0, 0.5001, 0.05)],
    "corte": [round(x, 3) for x in np.arange(0.30, 0.8001, 0.05)],
    "tau": [round(x, 3) for x in np.arange(0.50, 1.0001, 0.025)],
}


def _dist_actual(cfg: dict) -> int:
    return sum(abs(cfg[c] - ACTUAL_SR[c]) > 1e-9 for c in (*GRILLA, "corte"))


class Espacio:
    def __init__(self, pila: Pila):
        import itertools

        self.pila = pila
        self.cfgs = [
            {**ACTUAL_SR, **dict(zip(GRILLA, v, strict=True))} for v in itertools.product(*GRILLA.values())
        ]
        res = [pila.puntuar(c) for c in self.cfgs]
        self.P = np.array([p for p, _ in res])
        self.S = np.array([s for _, s in res])
        self.dist = np.array([[_dist_actual({**c, "corte": j}) for j in CORTES] for c in self.cfgs])
        self.n = len(self.cfgs) * len(CORTES)

    def acc(self, mask: np.ndarray) -> np.ndarray:
        y = self.pila.y[mask]
        out = np.zeros((len(self.cfgs), len(CORTES)))
        for j, c in enumerate(CORTES):
            out[:, j] = (np.where(self.S[:, mask] >= c, self.P[:, mask], -1) == y).mean(1)
        return out

    def elegir(self, train: np.ndarray, val: np.ndarray, topk: int = 5) -> dict:
        a = self.acc(train)
        orden = sorted(
            ((i, j) for i in range(len(self.cfgs)) for j in range(len(CORTES))),
            key=lambda t: (-round(a[t], 12), self.dist[t]),
        )
        cand = orden[:topk]
        av = self.acc(val)
        cand = sorted(cand, key=lambda t: (-round(av[t], 12), cand.index(t)))
        i, j = cand[0]
        cfg = {**self.cfgs[i], "corte": CORTES[j]}
        pc = np.where(self.S[i, train] >= cfg["corte"], self.P[i, train], -1)
        taus = {
            str(o): b.regla_tau(self.S[i, train], pc, self.pila.y[train], cfg["corte"], o)
            for o in (0.95, 0.98)
        }
        return {
            "cfg": cfg,
            "taus": taus,
            "acc_train": float(a[i, j]),
            "empates": int(sum(abs(a[t] - a[i, j]) < 1e-12 for t in orden)),
        }


def barrido_unico_mascara(pila: Pila, mask: np.ndarray, clave: str) -> list[dict]:
    out = []
    for v in REJ_UNICA[clave]:
        out.append({"valor": v, **pila.medir({**ACTUAL_SR, clave: v}, mask)})
    return out


def optimo(filas: list[dict], clave: str) -> dict:
    if clave == "tau":
        return {}
    ex = np.array([f["exactitud"] for f in filas])
    vs = np.array([f["valor"] for f in filas])
    top = ex.max()
    emp = vs[ex >= top - 1e-12]
    mejor = float(emp[np.argmin(np.abs(emp - ACTUAL_SR[clave]))])
    cerca = vs[ex >= top - 0.005]
    return {
        "valor": mejor,
        "exactitud": float(top),
        "empatados": [float(x) for x in emp],
        "meseta_0.5pp": [float(cerca.min()), float(cerca.max())],
    }


def resumen(v: list[float]) -> dict:
    a = np.array([x for x in v if x is not None], float)
    return (
        {
            "media": float(a.mean()),
            "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "min": float(a.min()),
            "max": float(a.max()),
            "n": int(len(a)),
        }
        if len(a)
        else {}
    )


def calibrar(cx: b.Contexto, pila: Pila, estres: dict) -> dict:
    listas = sorted(set(cx.lista))
    esp = Espacio(pila)
    por_semilla = []
    unico_por_semilla: dict[str, list] = {c: [] for c in REJ_UNICA}
    comprobaciones = []
    for i in range(SEMILLAS):
        parte = partir(listas, SEMILLA_BASE + i)
        proh = cadenas_prohibidas(cx, parte, estres)
        m = mascaras(pila, parte, proh)
        comp = comprobar_fuga(pila, parte, m, proh)
        comprobaciones.append(comp)
        e_l = esp.elegir(m["train_limpio"], m["val"])
        e_a = esp.elegir(m["train_aum"], m["val"])
        fila = {
            "semilla": SEMILLA_BASE + i,
            "renglones_train_limpio": int(m["train_limpio"].sum()),
            "renglones_train_aum": int(m["train_aum"].sum()),
            "variantes_usadas": m["_variantes_usadas"],
            "variantes_excluidas_texto_base": m["_variantes_excluidas_por_texto_base"],
            "variantes_excluidas_cadena": m["_variantes_excluidas_por_cadena"],
            "comprobacion_fuga": comp,
        }
        variantes = {
            "actual_sr_tau_0.75": (ACTUAL_SR, 0.75),
            "actual_con_rescate_tau_0.75": (k.ACTUAL, 0.75),
            "limpio_tau_0.75": (e_l["cfg"], 0.75),
            "aumentado_tau_0.75": (e_a["cfg"], 0.75),
            "limpio_tau_regla_0.95": (e_l["cfg"], e_l["taus"]["0.95"]),
            "aumentado_tau_regla_0.95": (e_a["cfg"], e_a["taus"]["0.95"]),
        }
        fila["elegido_limpio"], fila["elegido_aumentado"] = (
            {**e_l["cfg"], "taus": e_l["taus"]},
            {**e_a["cfg"], "taus": e_a["taus"]},
        )
        fila["empates"] = {"limpio": e_l["empates"], "aumentado": e_a["empates"]}
        for parte_n in ("val", "prueba"):
            fila[parte_n] = {n: pila.medir({**c, "tau": t}, m[parte_n]) for n, (c, t) in variantes.items()}
        fila["train_aum_medidas"] = {
            n: pila.medir({**c, "tau": t}, m["train_aum"]) for n, (c, t) in variantes.items()
        }
        fila["unico"] = {}
        for clave in REJ_UNICA:
            fl, fa = (
                barrido_unico_mascara(pila, m["train_limpio"], clave),
                barrido_unico_mascara(pila, m["train_aum"], clave),
            )
            fv, fp = (
                barrido_unico_mascara(pila, m["val"], clave),
                barrido_unico_mascara(pila, m["prueba"], clave),
            )
            ol, oa = optimo(fl, clave), optimo(fa, clave)
            ent = {"limpio": ol, "aumentado": oa}
            if clave != "tau":
                ix = {f["valor"]: f for f in fp}
                ent["prueba_exactitud_en_optimo_limpio"] = ix[ol["valor"]]["exactitud"]
                ent["prueba_exactitud_en_optimo_aumentado"] = ix[oa["valor"]]["exactitud"]
                ent["prueba_exactitud_en_actual"] = ix[min(ix, key=lambda v: abs(v - ACTUAL_SR[clave]))][
                    "exactitud"
                ]
            fila["unico"][clave] = ent
        por_semilla.append(fila)
        print(
            f"semilla {i + 1}/{SEMILLAS} train {fila['renglones_train_limpio']}->{fila['renglones_train_aum']}",
            flush=True,
        )
    return {"por_semilla": por_semilla, "comprobaciones": comprobaciones, "n_combinaciones": esp.n}


def agregar(cal: dict, cx: b.Contexto, pila: Pila) -> dict:
    ps = cal["por_semilla"]
    out: dict = {}
    out["prueba"] = {
        n: {
            m: resumen([f["prueba"][n][m] for f in ps])
            for m in ("exactitud", "aceptada", "precision_aceptada", "revision_humana")
        }
        for n in ps[0]["prueba"]
    }
    out["validacion"] = {
        n: {m: resumen([f["val"][n][m] for f in ps]) for m in ("exactitud", "aceptada", "precision_aceptada")}
        for n in ps[0]["val"]
    }

    def par(a: str, b2: str, medida: str = "exactitud") -> dict:
        d = np.array([100 * (f["prueba"][a][medida] - f["prueba"][b2][medida]) for f in ps])
        dv = np.array([100 * (f["val"][a][medida] - f["val"][b2][medida]) for f in ps])
        return {
            "media_pp": float(d.mean()),
            "sd_entre_semillas_pp": float(d.std(ddof=1)),
            "error_estandar_pp": float(d.std(ddof=1) / np.sqrt(len(d))),
            "semillas_gana": int((d > 1e-9).sum()),
            "empata": int((abs(d) <= 1e-9).sum()),
            "pierde": int((d < -1e-9).sum()),
            "validacion_media_pp": float(dv.mean()),
        }

    out["diferencias_en_prueba_exactitud"] = {
        "aumentado_menos_actual_sr": par("aumentado_tau_0.75", "actual_sr_tau_0.75"),
        "limpio_menos_actual_sr": par("limpio_tau_0.75", "actual_sr_tau_0.75"),
        "aumentado_menos_limpio": par("aumentado_tau_0.75", "limpio_tau_0.75"),
        "actual_sr_menos_actual_con_rescate": par("actual_sr_tau_0.75", "actual_con_rescate_tau_0.75"),
    }
    out["diferencias_en_prueba_aceptada"] = {
        n: par(a, b2, "aceptada")
        for n, (a, b2) in {
            "aumentado_menos_limpio": ("aumentado_tau_0.75", "limpio_tau_0.75"),
            "aumentado_menos_actual_sr": ("aumentado_tau_0.75", "actual_sr_tau_0.75"),
        }.items()
    }
    out["tau_regla_0.95_prueba"] = {
        n: {
            m: resumen([f["prueba"][n][m] for f in ps])
            for m in ("exactitud", "aceptada", "precision_aceptada")
        }
        for n in ("limpio_tau_regla_0.95", "aumentado_tau_regla_0.95")
    }
    out["tau_regla_en_entrenamiento"] = {
        v: resumen([f[f"elegido_{v}"]["taus"]["0.95"] for f in ps]) for v in ("limpio", "aumentado")
    }
    import collections

    def firma(c: dict) -> str:
        return json.dumps({x: c[x] for x in (*GRILLA, "corte")})

    for v in ("limpio", "aumentado"):
        cnt = collections.Counter(firma(f[f"elegido_{v}"]) for f in ps)
        out[f"combinaciones_elegidas_{v}"] = [
            {"combinacion": json.loads(c), "veces": n} for c, n in cnt.most_common(6)
        ]
        out[f"semillas_en_que_elegido_{v}_es_el_actual"] = int(
            sum(firma(f[f"elegido_{v}"]) == firma(ACTUAL_SR) for f in ps)
        )
    out["semillas_en_que_limpio_y_aumentado_eligen_lo_mismo"] = int(
        sum(firma(f["elegido_limpio"]) == firma(f["elegido_aumentado"]) for f in ps)
    )
    unico = {}
    for clave in ("piso", "w_jac", "w_cos", "corte"):
        vl = np.array([f["unico"][clave]["limpio"]["valor"] for f in ps])
        va = np.array([f["unico"][clave]["aumentado"]["valor"] for f in ps])
        dif = np.array(
            [
                100
                * (
                    f["unico"][clave]["prueba_exactitud_en_optimo_aumentado"]
                    - f["unico"][clave]["prueba_exactitud_en_optimo_limpio"]
                )
                for f in ps
            ]
        )
        da = np.array(
            [
                100
                * (
                    f["unico"][clave]["prueba_exactitud_en_optimo_aumentado"]
                    - f["unico"][clave]["prueba_exactitud_en_actual"]
                )
                for f in ps
            ]
        )
        dl = np.array(
            [
                100
                * (
                    f["unico"][clave]["prueba_exactitud_en_optimo_limpio"]
                    - f["unico"][clave]["prueba_exactitud_en_actual"]
                )
                for f in ps
            ]
        )
        unico[clave] = {
            "valor_actual": ACTUAL_SR[clave],
            "optimo_limpio_media": float(vl.mean()),
            "optimo_limpio_min_max": [float(vl.min()), float(vl.max())],
            "optimo_aumentado_media": float(va.mean()),
            "optimo_aumentado_min_max": [float(va.min()), float(va.max())],
            "desplazamiento_aumentado_menos_limpio": float((va - vl).mean()),
            "semillas_en_que_el_optimo_aumentado_es_el_actual": int(np.isclose(va, ACTUAL_SR[clave]).sum()),
            "semillas_en_que_el_actual_esta_en_la_meseta_0.5pp_aumentada": int(
                sum(
                    f["unico"][clave]["aumentado"]["meseta_0.5pp"][0] - 1e-9
                    <= ACTUAL_SR[clave]
                    <= f["unico"][clave]["aumentado"]["meseta_0.5pp"][1] + 1e-9
                    for f in ps
                )
            ),
            "semillas_en_que_el_actual_esta_en_la_meseta_0.5pp_limpia": int(
                sum(
                    f["unico"][clave]["limpio"]["meseta_0.5pp"][0] - 1e-9
                    <= ACTUAL_SR[clave]
                    <= f["unico"][clave]["limpio"]["meseta_0.5pp"][1] + 1e-9
                    for f in ps
                )
            ),
            "prueba_aumentado_menos_limpio_pp": {"media": float(dif.mean()), "sd": float(dif.std(ddof=1))},
            "prueba_optimo_aumentado_menos_actual_pp": {
                "media": float(da.mean()),
                "sd": float(da.std(ddof=1)),
            },
            "prueba_optimo_limpio_menos_actual_pp": {"media": float(dl.mean()), "sd": float(dl.std(ddof=1))},
        }
    unico["tau"] = {
        "nota": "tau se evalua con la regla del menor tau con precision >= 0,95 (ver tau_regla_en_entrenamiento) y con curvas de aceptada/precision"
    }
    out["constantes_una_a_una"] = unico
    todo_l = pila.origen == 0
    todo_a = np.ones(len(pila.y), bool)
    curvas = {}
    for clave in REJ_UNICA:
        curvas[clave] = {
            "limpio": barrido_unico_mascara(pila, todo_l, clave),
            "aumentado": barrido_unico_mascara(pila, todo_a, clave),
        }
    out["curvas_agrupadas_descriptivas"] = curvas
    return out


def figura(res: dict) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    AZ, NA, GR, VE = "#1F4E86", "#A8500F", "#4D4D4D", "#2E7D32"
    plt.rcParams.update(
        {"font.family": "serif", "font.size": 8, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, ejes = plt.subplots(2, 3, figsize=(7.5, 4.6))
    cur = res["curvas_agrupadas_descriptivas"]
    for ax, clave in zip(ejes.flat, ["piso", "w_jac", "w_cos", "corte", "tau"], strict=False):
        c = cur[clave]
        if clave == "tau":
            for n, col, ls in (("limpio", AZ, "-"), ("aumentado", NA, "--")):
                ax.plot(
                    [f["valor"] for f in c[n]],
                    [100 * (f["precision_aceptada"] or np.nan) for f in c[n]],
                    color=col,
                    ls=ls,
                    label=f"precision {n}",
                )
            ax.axhline(95, color=GR, lw=0.6, ls=":")
            ax.set_ylabel("precision de lo aceptado (%)")
            ax.legend(frameon=False, fontsize=6)
        else:
            for n, col, ls in (("limpio", AZ, "-"), ("aumentado", NA, "--")):
                ax.plot(
                    [f["valor"] for f in c[n]],
                    [100 * f["exactitud"] for f in c[n]],
                    color=col,
                    ls=ls,
                    marker="o",
                    ms=2,
                    label=n,
                )
            ax.set_ylabel("exactitud (%)")
            if clave == "piso":
                ax.legend(frameon=False, fontsize=6)
        ax.axvline(ACTUAL_SR[clave], color=GR, lw=0.8, ls="--")
        ax.set_title(clave, fontsize=8)
    ax = ejes.flat[5]
    ps = res["_por_semilla"]
    xs = np.arange(len(ps))
    ax.axhline(0, color=GR, lw=0.6)
    ax.plot(
        xs,
        [
            100
            * (
                f["prueba"]["aumentado_tau_0.75"]["exactitud"]
                - f["prueba"]["actual_sr_tau_0.75"]["exactitud"]
            )
            for f in ps
        ],
        "o",
        color=NA,
        ms=3,
        label="aumentado - actual",
    )
    ax.plot(
        xs,
        [
            100
            * (f["prueba"]["limpio_tau_0.75"]["exactitud"] - f["prueba"]["actual_sr_tau_0.75"]["exactitud"])
            for f in ps
        ],
        "s",
        color=AZ,
        ms=3,
        label="limpio - actual",
    )
    ax.set_title("prueba por semilla (pp)", fontsize=8)
    ax.set_xlabel("semilla")
    ax.legend(frameon=False, fontsize=6)
    fig.suptitle(
        "Calibracion con entrenamiento limpio (n~2.100) vs aumentado (n~12.000); linea punteada = valor actual",
        fontsize=7,
    )
    fig.tight_layout()
    ruta = k.SALIDA / "calibracion_aumentada.pdf"
    fig.savefig(ruta)
    return ruta


def main() -> int:
    t0 = time.time()
    cx = b.Contexto()
    pila, estres, aum, cache = construir_pila(cx)
    print("pila", len(pila.y), "filas; llamadas", LLAMADAS, f"{time.time() - t0:.0f}s", flush=True)
    cal = calibrar(cx, pila, estres)
    res = agregar(cal, cx, pila)
    ps = cal["por_semilla"]
    comp = cal["comprobaciones"]
    res_out = {
        "descripcion": "Calibracion aumentada: las constantes se calibran con entrenamiento (limpio + 5 variantes por renglon) y se evaluan en validacion y prueba reales (limpias). No se entrena ningun modelo.",
        "tamano_aumentacion": {
            "variantes_por_renglon": N_VARIANTES,
            "renglones_reales": len(cx.y),
            "casos_totales_pila": len(pila.y),
            "renglones_entrenamiento_limpio_media": resumen([f["renglones_train_limpio"] for f in ps]),
            "renglones_entrenamiento_aumentado_media": resumen([f["renglones_train_aum"] for f in ps]),
            "variantes_excluidas_por_texto_base_media": resumen(
                [f["variantes_excluidas_texto_base"] for f in ps]
            ),
            "variantes_excluidas_por_cadena_media": resumen([f["variantes_excluidas_cadena"] for f in ps]),
        },
        "base": "constantes actuales con la rama de rescate APAGADA (piso 0,6; w_jac 0,4; w_cos 0,15; corte 0,5; tau 0,75)",
        "espacio": {
            "grilla": GRILLA,
            "cortes": CORTES,
            "combinaciones": cal["n_combinaciones"],
            "regla_tau": "menor tau con precision >= 0,95 en el entrenamiento correspondiente",
        },
        "comprobacion_de_fuga": {
            "particiones_revisadas": len(comp),
            "max_listas_compartidas": max(c["listas_compartidas_entre_particiones"] for c in comp),
            "max_variantes_de_entrenamiento_con_texto_base_de_val_o_prueba": max(
                c["variantes_de_entrenamiento_con_texto_base_de_val_o_prueba"] for c in comp
            ),
            "max_cadenas_de_variantes_iguales_a_texto_de_val_o_prueba": max(
                c["cadenas_de_variantes_de_entrenamiento_iguales_a_algun_texto_de_val_o_prueba"] for c in comp
            ),
            "renglones_limpios_de_entrenamiento_con_texto_base_repetido_en_val_o_prueba_media": resumen(
                [c["renglones_limpios_de_entrenamiento_con_texto_base_tambien_en_val_o_prueba"] for c in comp]
            ),
            "nota": "Los renglones LIMPIOS de entrenamiento cuyo texto exacto tambien aparece en una lista de val/prueba (textos repetidos entre colegios/grados) ya estaban en el experimento anterior; sus variantes NO se usan.",
        },
        "vectores": {
            "llamadas": LLAMADAS,
            "textos_distintos_vectorizados_en_cache": len(cache) if cache else 0,
        },
        **{kk: v for kk, v in res.items()},
        "segundos": time.time() - t0,
    }
    res_out["_por_semilla"] = ps
    figura(res_out)
    guardar = {kk: v for kk, v in res_out.items() if kk != "_por_semilla"}
    guardar["por_semilla"] = ps
    (k.SALIDA / "calibracion_aumentada.json").write_text(
        json.dumps(guardar, ensure_ascii=False, indent=1, default=float), encoding="utf-8"
    )
    print("ok", f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
