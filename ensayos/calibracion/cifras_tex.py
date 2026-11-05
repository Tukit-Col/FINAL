"""Cifras y tablas de `optimizacion.tex`, escritas desde los JSON de la calibracion.

Ningun numero del texto se escribe a mano: cada macro `\\cal...` y cada tabla
`tabla_*.tex` sale de un JSON de `docs/informes/calibracion/`. Si se vuelve a
correr un experimento, basta con correr este script y recompilar.

Uso: uv run python ensayos/calibracion/cifras_tex.py
Salida: docs/informes/calibracion/cifras.tex y docs/informes/calibracion/tabla_*.tex
"""

from __future__ import annotations

import json
import math

import nucleo as n
import numpy as np
from calibrar_nsga import PARTIDA, generaciones_con, poblacion_con
from tukit_inteligencia import optimizador as opt

SAL = n.SALIDA


def leer(nombre: str):
    ruta = SAL / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def num(x: float, dec: int = 3) -> str:
    """Numero con coma decimal, como lo pide babel en espanol."""
    return f"{x:.{dec}f}".replace(".", "{,}")


def entero(x: int) -> str:
    s = f"{int(x):,}".replace(",", "\\,")
    return s


def pct(x: float, dec: int = 1) -> str:
    return num(100 * x, dec) + "\\,\\%"


def main() -> int:
    macros: dict[str, str] = {}

    # ------------------------------------------------------------ hardware
    u = leer("umbral.json")
    hw = u["hardware"]
    macros["calCPU"] = hw["cpu"]
    macros["calNucleos"] = hw["nucleos"]
    macros["calRAM"] = str(int(hw["memoria_bytes"]) // 2**30)
    macros["calPython"] = hw["python"]
    macros["calPymoo"] = hw["pymoo"]

    # ------------------------------------------------------------ pesos P21
    p = leer("pesos_p21.json")
    macros["calEncuestados"] = str(p["encuestados"])
    macros["calRemuestreos"] = entero(p["remuestreos"])
    for c, nombre in (
        ("precio", "Precio"),
        ("marca_exigida", "Marca"),
        ("calidad", "Calidad"),
        ("personaje", "Personaje"),
    ):
        macros[f"calW{nombre}"] = num(p["pesos"][c])
        macros[f"calW{nombre}Bajo"] = num(p["ic95"][c][0])
        macros[f"calW{nombre}Alto"] = num(p["ic95"][c][1])
        macros[f"calW{nombre}Antes"] = num(p["pesos_anteriores_del_codigo"][c], 2)
        macros[f"calPuntos{nombre}"] = num(p["puntos_promedio"][c], 2)
        macros[f"calPrimero{nombre}"] = pct(p["fraccion_en_primer_lugar"][c])

    # ------------------------------------------------------------ umbral
    filas = u["filas"]
    con_exacto = [f for f in filas if f["exacto"]]
    S = np.array([f["S"] for f in con_exacto], float)
    t = np.array([f["exacto"]["t_total"] for f in con_exacto])
    k, logc = np.polyfit(np.log(S), np.log(t), 1)
    res = np.log(t) - (k * np.log(S) + logc)
    sd = float(res.std())
    t_nsga_med = float(np.median([np.mean(f["t_nsga_s"]) for f in filas]))
    cruce = math.exp((math.log(t_nsga_med) - logc) / k)
    cruce_p95 = math.exp((math.log(t_nsga_med) - logc - 1.645 * sd) / k)
    macros["calSubproblemas"] = str(len(filas))
    macros["calSubproblemasExacto"] = str(len(con_exacto))
    macros["calNivelMin"] = str(min(f["bits"] for f in filas))
    macros["calNivelMax"] = str(max(f["bits"] for f in filas))
    macros["calNivelMaxExacto"] = str(max(f["bits"] for f in con_exacto))
    macros["calExponente"] = num(k, 2)
    macros["calConstante"] = (
        f"{math.exp(logc):.2e}".replace(".", "{,}").replace("e-0", "e-").replace("e-", "\\times10^{-") + "}"
    )
    macros["calSdResiduo"] = num(sd, 2)
    macros["calTNsgaMediana"] = num(t_nsga_med, 2)
    macros["calCruce"] = entero(round(cruce))
    macros["calCruceLog"] = num(math.log2(cruce), 1)
    macros["calCruceP"] = entero(round(cruce_p95))
    macros["calCrucePLog"] = num(math.log2(cruce_p95), 1)
    macros["calSemillasHV"] = str(len(u["semillas_hv"]))
    razones = [r for f in filas for r in f["razon_hv"]]
    macros["calRazonHVMin"] = num(min(razones), 4)
    macros["calRazonHVMediana"] = num(float(np.median(razones)), 4)
    macros["calCorridasHV"] = entero(len(razones))
    poda_ok = [f.get("poda_igual_a_enumeracion") for f in filas if "poda_igual_a_enumeracion" in f]
    macros["calPodaIgual"] = f"{sum(bool(x) for x in poda_ok)} de {len(poda_ok)}"
    macros["calPodaMax"] = num(max(f["t_poda_s"] for f in filas) * 1000, 1)
    limite = opt.LIMITE_ENUMERACION
    macros["calLimite"] = entero(limite)
    macros["calLimiteLog"] = str(int(math.log2(limite)))
    bajo = [f for f in con_exacto if f["S"] <= limite]
    macros["calExactoGanaBajo"] = (
        f"{sum(f['exacto']['t_total'] < np.mean(f['t_nsga_s']) for f in bajo)} de {len(bajo)}"
    )
    sobre = [f for f in con_exacto if f["S"] > limite]
    macros["calExactoGanaSobre"] = (
        f"{sum(f['exacto']['t_total'] < np.mean(f['t_nsga_s']) for f in sobre)} de {len(sobre)}"
    )
    macros["calExactoMaxBajo"] = num(max(f["exacto"]["t_total"] for f in bajo), 3)

    # tabla por nivel
    lineas = []
    for b in sorted({f["bits"] for f in filas}):
        xs = [f for f in filas if f["bits"] == b]
        te = [f["exacto"]["t_total"] for f in xs if f["exacto"]]
        tn = [float(np.mean(f["t_nsga_s"])) for f in xs]
        rz = [r for f in xs for r in f["razon_hv"]]
        gana = sum(1 for f in xs if f["exacto"] and f["exacto"]["t_total"] < np.mean(f["t_nsga_s"]))
        te_txt = num(float(np.median(te)), 3) if te else "---"
        te_max = num(max(te), 3) if te else "---"
        lineas.append(
            f"{b} & {len(xs)} & {te_txt} & {te_max} & {num(float(np.median(tn)), 3)} & "
            f"{gana} & {num(min(rz), 4)} \\\\"
        )
    (SAL / "tabla_umbral.tex").write_text("\n".join([*lineas, "\\bottomrule"]) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ corpus
    insts = n.instancias()
    macros["calListas"] = str(len(insts))
    macros["calColegios"] = str(len({i["colegio"] for i in insts}))
    espacios = []
    for i in insts:
        dec = n.decidibles(n.renglones_de(i))
        espacios.append(n.espacio_de(n.opciones_de(dec)) if dec else 0)
    macros["calListasNsga"] = str(sum(s > limite for s in espacios))
    macros["calListasExacto"] = str(sum(1 < s <= limite for s in espacios))
    macros["calListasTriviales"] = str(sum(s <= 1 for s in espacios))
    macros["calEspacioMaxLog"] = str(int(math.log10(max(espacios))))

    # ------------------------------------------------------------ tau
    tau = leer("tau.json")
    tr = tau["tabla_transicion_resolucion"]
    fila_tr = tr["transiciones(estado_anterior, estado_nuevo, decidida_por_humano, filas)"][0]
    macros["calTauTransiciones"] = entero(int(fila_tr[3]))
    macros["calTauPares"] = str(tau["pares"])
    macros["calTauListas"] = str(tau["listas"])
    macros["calTauColegios"] = str(len(tau["colegios"]))
    macros["calTauColegioMayor"] = str(max(tau["colegios"].values()))
    macros["calTauAciertos"] = str(tau["aciertos"])
    macros["calTauAUC"] = num(tau["auc_parecido"], 3)
    macros["calTauValores"] = str(tau["parecido_valores_distintos"])
    macros["calTauPrecision"] = pct(tau["en_tau_actual"]["precision"])
    macros["calTauAceptada"] = pct(tau["en_tau_actual"]["fraccion_aceptada"])
    mc, ic = tau["matriz_tau_actual"], tau["ic95_bootstrap_tau_actual"]
    for k in ("tp", "fp", "fn", "tn"):
        macros[f"calTau{k.upper()}"] = str(mc[k])
    for k, nombre in (("precision", "P"), ("recall", "R"), ("f1", "F"), ("auc", "AUC")):
        if k != "auc":
            macros[f"calTau{nombre}"] = num(mc[k], 3)
        macros[f"calTau{nombre}Bajo"] = num(ic[k][0], 3)
        macros[f"calTau{nombre}Alto"] = num(ic[k][1], 3)
    taus = [p["tau"] for p in tau["validacion_cruzada_agrupada"]]
    macros["calTauCVMin"] = num(min(taus), 2)
    macros["calTauCVMax"] = num(max(taus), 2)

    # ------------------------------------------------------------ NSGA-II
    c = leer("calibracion_nsga.json")
    if c:
        macros["calGrandes"] = str(c["listas_grandes"])
        macros["calPrueba"] = str(c["particion"]["prueba"])
        macros["calColegiosPrueba"] = str(len(c["particion"]["colegios_prueba"]))
        macros["calPliegues"] = str(len(c["particion"]["pliegues"]))
        macros["calPlieguesListas"] = ", ".join(str(x) for x in c["particion"]["pliegues"])
        macros["calCVListas"] = str(sum(c["particion"]["pliegues"]))
        macros["calSemillasCV"] = str(c["semillas_validacion"])
        macros["calSemillasPrueba"] = str(c["semillas_prueba"])
        macros["calFactores"] = "; ".join(num(f, 2) for f in c["factores"])
        macros["calUmbralHV"] = pct(c["umbral_hv"])
        e = c["elegida"]
        macros["calA"] = num(e["a"], 2)
        macros["calB"] = num(e["b"], 2)
        cv = c["validacion_cruzada"]
        macros["calPlieguesIguales"] = f"{sum(p['elegida'] == e for p in cv)} de {len(cv)}"
        macros["calPlieguesDentro"] = f"{sum(p['dentro_del_umbral_en_apartado'] for p in cv)} de {len(cv)}"
        macros["calCVHVMin"] = num(min(p["hv_medio_apartado"] for p in cv), 4)
        pr = c["prueba"]
        for nombre, clave in (("Actual", "actual"), ("Elegida", "elegida")):
            macros[f"calPrueba{nombre}HV"] = num(pr[clave]["hv_medio"], 4)
            macros[f"calPrueba{nombre}HVMin"] = num(pr[clave]["hv_min"], 4)
            macros[f"calPrueba{nombre}T"] = num(pr[clave]["t_medio_s"], 2)
            macros[f"calPrueba{nombre}TMax"] = num(pr[clave]["t_max_s"], 2)
            macros[f"calPrueba{nombre}Evals"] = entero(round(pr[clave]["evals_medios"]))
        d = pr["dif_hv_elegida_menos_actual"]
        macros["calDifHV"] = num(d["media"], 4)
        macros["calDifHVBajo"] = num(d["ic95"][0], 4)
        macros["calDifHVAlto"] = num(d["ic95"][1], 4)
        macros["calDifHVp"] = num(d["wilcoxon_p"], 3)
        d = pr["dif_t_s_elegida_menos_actual"]
        macros["calDifT"] = num(d["media"], 2)
        macros["calDifTBajo"] = num(d["ic95"][0], 2)
        macros["calDifTAlto"] = num(d["ic95"][1], 2)
        macros["calDifTp"] = (
            f"{d['wilcoxon_p']:.1e}".replace(".", "{,}").replace("e-0", "e-").replace("e-", "\\times10^{-")
            + "}"
        )
        macros["calFraccionHV"] = pct(pr["fraccion_corridas_elegida_hv_ge_0999"])
        macros["calRazonMinPrueba"] = num(pr["razon_min_corrida_elegida"], 4)
        macros["calTRejillaMin"] = str(round(c["t_rejilla_s"] / 60))
        macros["calPobMin"] = str(PARTIDA["pob_min"])
        macros["calPobMax"] = str(PARTIDA["pob_max"])
        macros["calGenMin"] = str(PARTIDA["gen_min"])
        macros["calGenMax"] = str(PARTIDA["gen_max"])
        macros["calPobProdMin"] = str(opt._POBLACION_MIN)
        macros["calPobProdMax"] = str(opt._POBLACION_MAX)
        macros["calPobProdLinea"] = str(opt._POBLACION_POR_LINEA)
        macros["calGenProdMin"] = str(opt._GENERACIONES_MIN)
        macros["calGenProdMax"] = str(opt._GENERACIONES_MAX)
        macros["calGenProdDecada"] = str(opt._GENERACIONES_POR_DECADA)
        partida = next(r for r in c["rejilla"] if (r["a"], r["b"]) == (1.0, 1.0))
        macros["calEvalsCVPartida"] = entero(round(partida["evals_medios"]))
        lineas = []
        for r in c["rejilla"]:
            marca = "$\\star$" if (r["a"], r["b"]) == (e["a"], e["b"]) else ""
            marca += "$\\circ$" if (r["a"], r["b"]) == (1.0, 1.0) else ""
            lineas.append(
                f"{num(r['a'], 2)} & {num(r['b'], 2)} & {entero(round(r['evals_medios']))} & "
                f"{num(r['hv_medio'], 4)} & {num(r['hv_min_lista'], 4)} & "
                f"{num(r['t_medio_s'], 2)} & {marca} \\\\"
            )
        (SAL / "tabla_rejilla.tex").write_text("\n".join([*lineas, "\\bottomrule"]) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ sensibilidad
    s = leer("sensibilidad.json")
    if s:
        macros["calSensListas"] = str(s["listas"])
        macros["calSensPerturbaciones"] = entero(s["perturbaciones"])
        macros["calSensFrenteMediana"] = num(s["puntos_del_frente_mediana"], 0)
        lineas = []
        for d in s["dentro_ic95_p21"]:
            lineas.append(
                f"{pct(d['sobreprecio'], 0)} & IC 95\\,\\% P21 & --- & {num(d['estable_medio'], 3)} & "
                f"[{num(d['ic95'][0], 3)}; {num(d['ic95'][1], 3)}] & {num(d['estable_minimo_lista'], 3)} \\\\"
            )
        for d in s["celdas"]:
            lineas.append(
                f"{pct(d['sobreprecio'], 0)} & Dirichlet $\\kappa={d['kappa']}$ & "
                f"{num(d['sd_componente_precio'], 3)} & "
                f"{num(d['estable_medio'], 3)} & [{num(d['ic95'][0], 3)}; {num(d['ic95'][1], 3)}] & "
                f"{num(d['estable_minimo_lista'], 3)} \\\\"
            )
        (SAL / "tabla_sensibilidad.tex").write_text(
            "\n".join([*lineas, "\\bottomrule"]) + "\n", encoding="utf-8"
        )
        sin = next(d for d in s["dentro_ic95_p21"] if d["sobreprecio"] == 0.0)
        macros["calSensIC"] = num(sin["estable_medio"], 3)
        con_sigma = [d for d in s["dentro_ic95_p21"] if d["sobreprecio"] > 0]
        macros["calSensICMin"] = num(min(d["estable_medio"] for d in con_sigma), 3)
        macros["calSensICMinLista"] = num(min(d["estable_minimo_lista"] for d in con_sigma), 3)
        k20 = [d for d in s["celdas"] if d["kappa"] == min(x["kappa"] for x in s["celdas"])]
        macros["calSensKappaMin"] = str(k20[0]["kappa"])
        macros["calSensKappaMinEstable"] = num(min(d["estable_medio"] for d in k20), 3)

    # ------------------------------------------------------------ hipervolumen por perfil
    h = leer("hipervolumen_prueba.json")
    if h:
        macros["calHVListas"] = str(h["listas"])
        macros["calHVListasNsga"] = str(h["listas_nsga2"])
        macros["calHVFrente"] = num(h["razon_hv_frente_media"], 4)
        macros["calHVFrenteBajo"] = num(h["razon_hv_frente_ic95"][0], 4)
        macros["calHVFrenteAlto"] = num(h["razon_hv_frente_ic95"][1], 4)
        macros["calHVFrenteMin"] = num(h["razon_hv_frente_minima"], 4)
        macros["calHVCobertura"] = num(h["cobertura_dos_kits_media"], 3)
        lineas = [
            f"Frente de producci\\'on & {num(h['razon_hv_frente_media'], 4)} & "
            f"[{num(h['razon_hv_frente_ic95'][0], 4)}; {num(h['razon_hv_frente_ic95'][1], 4)}] \\\\",
            f"Ahorrador $\\cup$ Premium & {num(h['cobertura_dos_kits_media'], 3)} & "
            f"[{num(h['cobertura_dos_kits_ic95'][0], 3)}; {num(h['cobertura_dos_kits_ic95'][1], 3)}] \\\\",
        ]
        nombres = {"Ahorrador": "Ahorrador", "Premium": "Premium", "MAUT_P21": "MAUT con pesos P21"}
        for p, d in h["hv_relativo_por_perfil"].items():
            macros[f"calHV{p.replace('_P21', 'Pesos').replace('_', '')}"] = num(d["media"], 3)
            lineas.append(
                f"{nombres[p]} & {num(d['media'], 3)} & [{num(d['ic95'][0], 3)}; {num(d['ic95'][1], 3)}] \\\\"
            )
        (SAL / "tabla_hipervolumen.tex").write_text(
            "\n".join([*lineas, "\\bottomrule"]) + "\n", encoding="utf-8"
        )

    # ------------------------------------------------------------ umbral con la configuracion elegida
    ue = leer("umbral_elegida.json")
    if ue and c:
        macros["calTNsgaElegidaMediana"] = num(ue["t_nsga_mediana_s"], 2)
        macros["calCruceElegida"] = entero(round(ue["cruce_mediana"]))
        macros["calCruceElegidaLog"] = num(math.log2(ue["cruce_mediana"]), 1)
        macros["calCruceElegidaP"] = entero(round(ue["cruce_percentil95"]))
        macros["calCruceElegidaPLog"] = num(math.log2(ue["cruce_percentil95"]), 1)
        rz = [r for f in ue["filas"] for r in f["razon_hv"]]
        macros["calRazonHVElegidaMin"] = num(min(rz), 4)
        bajo_e = [f for f in ue["filas"] if f["t_exacto"] and f["S"] <= limite]
        sobre_e = [f for f in ue["filas"] if f["t_exacto"] and f["S"] > limite]
        macros["calExactoGanaBajoElegida"] = (
            f"{sum(f['t_exacto'] < np.mean(f['t_nsga_s']) for f in bajo_e)} de {len(bajo_e)}"
        )
        macros["calExactoGanaSobreElegida"] = (
            f"{sum(f['t_exacto'] < np.mean(f['t_nsga_s']) for f in sobre_e)} de {len(sobre_e)}"
        )
        # Umbral teorico S* = N * sqrt(G): donde el filtro por pares del exhaustivo,
        # O(S^2 M) en el peor caso, iguala al ordenamiento no dominado, O(G M N^2).
        cerca = [f for f in filas if abs(f["S"] - limite) <= limite]
        n_tipico = int(np.median([f["lineas"] for f in cerca]))
        pob = poblacion_con(c["elegida"]["a"])(n_tipico)
        gen = generaciones_con(c["elegida"]["b"])(limite)
        macros["calNTipico"] = str(n_tipico)
        macros["calPobTipica"] = str(pob)
        macros["calGenTipica"] = str(gen)
        macros["calSTeorico"] = entero(round(pob * math.sqrt(gen)))
        macros["calSTeoricoLog"] = num(math.log2(pob * math.sqrt(gen)), 1)
        macros["calSEvals"] = entero(pob * gen)
        macros["calSEvalsLog"] = num(math.log2(pob * gen), 1)
        macros["calSCuadrado"] = entero(gen * pob**2)
        macros["calSCuadradoLog"] = num(math.log2(gen * pob**2), 1)
        # Tabla por nivel con las dos configuraciones del NSGA-II.
        lineas = []
        for b in sorted({f["bits"] for f in filas}):
            xs = [f for f in filas if f["bits"] == b]
            ys = [f for f in ue["filas"] if f["bits"] == b]
            te = [f["exacto"]["t_total"] for f in xs if f["exacto"]]
            tn = [float(np.mean(f["t_nsga_s"])) for f in xs]
            tne = [float(np.mean(f["t_nsga_s"])) for f in ys]
            rz = [r for f in ys for r in f["razon_hv"]]
            gana = sum(1 for f in ys if f["t_exacto"] and f["t_exacto"] < np.mean(f["t_nsga_s"]))
            te_txt = num(float(np.median(te)), 3) if te else "---"
            te_max = num(max(te), 3) if te else "---"
            lineas.append(
                f"{b} & {len(xs)} & {te_txt} & {te_max} & {num(float(np.median(tn)), 3)} & "
                f"{num(float(np.median(tne)), 3)} & {gana} & {num(min(rz), 4)} \\\\"
            )
        (SAL / "tabla_umbral.tex").write_text("\n".join([*lineas, "\\bottomrule"]) + "\n", encoding="utf-8")

    texto = ["% Generado por ensayos/calibracion/cifras_tex.py. No editar a mano."]
    texto += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in macros.items()]
    (SAL / "cifras.tex").write_text("\n".join(texto) + "\n", encoding="utf-8")
    print(len(macros), "macros")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
