"""Agrega hermanos.json por numero de hijos (imprime y devuelve el resumen)."""

import collections
import json
import statistics as st
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def resumen(d=None):
    d = d or json.loads((AQUI / "hermanos.json").read_text())
    por = collections.defaultdict(list)
    for f in d["filas"]:
        por[f["hijos"]].append(f)
    out = {}
    for k in sorted(por):
        fs = por[k]
        m = lambda xs: st.mean(xs) if xs else None  # noqa: E731
        pdc = [f for f in fs if f["pd_costo"]["estado"] == "ok"]
        pdp = [f for f in fs if f["pd_pres"]["estado"] == "ok"]
        ns_ah = [f for f in fs for f in [f] if True]

        def med(f, clave, lado):
            return m([x[clave] for x in f[lado] if x[clave] is not None])

        perd_base_vs_pd = [(med(f, "ah_costo", "base") - f["pd_costo"]["costo"]) for f in pdc]
        perd_ns_vs_pd = [(med(f, "ah_costo", "ns") - f["pd_costo"]["costo"]) for f in pdc]
        perd_base_vs_ns = [(med(f, "ah_costo", "base") - min(x["ah_costo"] for x in f["ns"])) for f in fs]
        perd_base_vs_ns_pct = [
            (med(f, "ah_costo", "base") - min(x["ah_costo"] for x in f["ns"])) / med(f, "ah_costo", "base")
            for f in fs
        ]
        fid_ns = [med(f, "pr_fid", "ns") for f in fs if all(x["pr_fid"] is not None for x in f["ns"])]
        fid_base = [med(f, "pr_fid", "base") for f in fs if all(x["pr_fid"] is not None for x in f["base"])]
        fid_pd = [f["pd_pres"]["fid"] for f in pdp]
        dif_pres = [
            med(f, "pr_fid", "ns") - med(f, "pr_fid", "base")
            for f in fs
            if all(x["pr_fid"] is not None for x in f["ns"] + f["base"])
        ]
        out[k] = {
            "hogares": len(fs),
            "lineas": m([f["lineas"] for f in fs]),
            "compartidos": m([f["compartidos"] for f in fs]),
            "pd_costo_ok": len(pdc),
            "pd_pres_ok": len(pdp),
            "pd_pres_estados_med": st.median(f["pd_pres"]["estados"] for f in fs),
            "pd_pres_s_med": st.median(f["pd_pres"]["s"] for f in fs),
            "pd_motivos": dict(collections.Counter(f["pd_pres"]["estado"] for f in fs)),
            "ns_s_med": st.median(x["s"] for f in fs for x in f["ns"]),
            "ns_evals": st.median(x["evals"] for f in fs for x in f["ns"]),
            "base_s_med": st.median(x["s"] for f in fs for x in f["base"]),
            "perd_ah_base_vs_pd_cop": m(perd_base_vs_pd),
            "perd_ah_ns_vs_pd_cop": m(perd_ns_vs_pd),
            "perd_ah_base_vs_ns_cop": m(perd_base_vs_ns),
            "perd_ah_base_vs_ns_pct": m(perd_base_vs_ns_pct),
            "fid_pres_pd": m(fid_pd),
            "fid_pres_ns": m(fid_ns),
            "fid_pres_base": m(fid_base),
            "dif_fid_ns_menos_base": m(dif_pres),
            "base_sin_kit_presupuesto": sum(1 for f in fs if any(x["pr_fid"] is None for x in f["base"])),
            "ns_peor_que_base_pres": sum(
                1
                for f in fs
                if all(x["pr_fid"] is not None for x in f["ns"] + f["base"])
                and med(f, "pr_fid", "ns") < med(f, "pr_fid", "base") - 1e-9
            ),
            "mem_pd": m([f["mem_pd_pico_mib"] for f in fs if "mem_pd_pico_mib" in f]),
            "mem_ns": m([f["mem_ns_pico_mib"] for f in fs if "mem_ns_pico_mib" in f]),
            "desajustes_valid": sum(f["valid_desajustes_de_5"] for f in fs),
        }
    return out


if __name__ == "__main__":
    for k, v in resumen().items():
        print(k, json.dumps(v, default=lambda x: round(x, 4)))
