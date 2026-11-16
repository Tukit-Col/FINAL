"""Costo de AWS en temporada escolar, con las tarifas de la Tabla tab:costos-aws.

Uso: uv run python ensayos/calibracion/costo_temporada.py
Escribe docs/informes/calibracion/costo_temporada.json y tabla_costo_temporada.tex.
No cambia las hipotesis de docs/negocio/punto_equilibrio.py (se importan).

Nota: la tabla de la memoria muestra Fargate 16,22 para 6 tareas (2,7033 c/u); aqui se usa 2,70 (diferencia 0,02 USD/mes).
Etiquetas: [M] sale de la memoria; [D] derivado de la memoria (se explica);
[S] supuesto mio (tarifa publica de AWS us-east-1 recordada, NO verificada en vivo).
"""
from __future__ import annotations
import importlib.util, json, math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pe", RAIZ / "docs/negocio/punto_equilibrio.py")
pe = importlib.util.module_from_spec(spec); spec.loader.exec_module(pe)

# ---- parametros ----
MESES_PICO = 2            # [S] diciembre y enero (piloto); parametro
N_TAREAS = (2, 3, 4)      # tareas de MS-Inteligencia y MS-Catalogo en pico
BD_ESCALADAS = 2          # [S] RDS que sube de clase: las de Inteligencia y Catalogo (variante: 5)
HORAS_MES = 730           # [S] convencion de la calculadora de AWS
FX = 3183                 # [S] COP por USD: estudio 07 (open.er-api.com, 2026-10-18); punto_equilibrio.py no trae tasa
BASE_USD = 142.46         # [M] total de la tabla
# ---- tarifas ----
IPV4_MES = 3.65           # [M] 0,005 USD/h x 730
FARGATE_SPOT_TAREA = 2.70 # [M] por tarea de 0,25 vCPU y 0,5 GB
VCPU_H, GB_H = 0.012144, 0.001334  # [S] Fargate Spot us-east-1; 0,25*VCPU_H+0,5*GB_H por 730 h = 2,70 (cuadra con la memoria)
RDS_MICRO_H, RDS_SMALL_H = 0.016, 0.032  # [S] db.t4g.micro / db.t4g.small, PostgreSQL, Single-AZ
GP3_GB = 0.115            # [S] 20 GB gp3; micro: 0,016x730+20x0,115 = 13,98 [M] (cuadra)
GB_BD = 20

tarea_calc = (0.25 * VCPU_H + 0.5 * GB_H) * HORAS_MES
rds_micro = RDS_MICRO_H * HORAS_MES + GB_BD * GP3_GB
rds_small = RDS_SMALL_H * HORAS_MES + GB_BD * GP3_GB
tarea_total = FARGATE_SPOT_TAREA + IPV4_MES  # cada tarea lleva su IPv4 publica (la memoria cobra 6 IPv4 por 6 tareas)
delta_bd = rds_small - rds_micro


def extra_mensual(n: int, bds: int, tarea_usd: float = tarea_total) -> float:
    return 2 * (n - 1) * tarea_usd + bds * delta_bd


def escenario(n: int, bds: int, meses: int = MESES_PICO) -> dict:
    ex = extra_mensual(n, bds)
    temporada_usd = ex * meses
    anual_base = BASE_USD * 12
    anual_temp = anual_base + temporada_usd
    contrib = pe.contribucion(pe.mean([g[1] for g in pe.KITS_CANONICOS]), pe.LOGISTICA["domicilio_base"])
    cop_temp = temporada_usd * FX
    return {
        "tareas_por_servicio": n, "bases_rds_en_small": bds, "meses_pico": meses,
        "mes_pico_usd": round(BASE_USD + ex, 2), "extra_mes_usd": round(ex, 2),
        "costo_temporada_usd": round(temporada_usd, 2), "costo_temporada_cop": round(cop_temp),
        "anual_sin_temporada_usd": round(anual_base, 2), "anual_con_temporada_usd": round(anual_temp, 2),
        "anual_con_temporada_cop": round(anual_temp * FX),
        "kits_adicionales": math.ceil(cop_temp / contrib),
    }


def main() -> None:
    contrib = round(pe.contribucion(pe.mean([g[1] for g in pe.KITS_CANONICOS]), pe.LOGISTICA["domicilio_base"]))
    esc = [escenario(n, b) for n in N_TAREAS for b in (0, BD_ESCALADAS)]
    var5 = [escenario(n, 5) for n in N_TAREAS]
    anual_cop = BASE_USD * 12 * FX
    out = {
        "parametros": {"meses_pico": MESES_PICO, "horas_mes": HORAS_MES, "fx_cop_por_usd": FX,
                       "bases_rds_escaladas": BD_ESCALADAS, "contribucion_por_kit_cop": contrib,
                       "comision": pe.COMISION},
        "verificacion_tarifas": {
            "tarea_fargate_spot_calculada": round(tarea_calc, 2), "tarea_memoria": FARGATE_SPOT_TAREA,
            "rds_micro_calculada": round(rds_micro, 2), "rds_micro_memoria": 13.98,
            "rds_small_supuesta": round(rds_small, 2), "delta_rds_por_base": round(delta_bd, 2),
            "costo_por_tarea_extra_con_ipv4": round(tarea_total, 2)},
        "base_mensual_usd": BASE_USD, "base_anual_usd": round(BASE_USD * 12, 2),
        "base_anual_cop": round(anual_cop),
        "equilibrio_base_memoria": {"piloto_kits": 82, "escalable_kits": 193},
        "equilibrio_recalculado_con_AWS_base": math.ceil(anual_cop / contrib),
        "escenarios": esc, "variante_5_bases_rds": var5,
    }
    d = RAIZ / "docs/informes/calibracion"
    (d / "costo_temporada.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    c = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    k = lambda x: f"{x:,}".replace(",", ".")
    L = [r"\begin{table}[!htbp]", r"\centering",
         r"\caption{Costo de AWS en temporada con las tarifas de la Tabla~\ref{tab:costos-aws} (" + f"{MESES_PICO}" + r" meses pico; tasa " + k(FX) + r" COP/USD, supuesto). Contribución por kit: \$" + k(contrib) + r".}",
         r"\label{tab:costo-temporada}", r"\footnotesize", r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
         r"\textbf{Escenario} & \textbf{Mes pico (USD)} & \textbf{Temporada (USD)} & \textbf{Año (USD)} & \textbf{Temporada (COP)} & \textbf{Kits extra} \\", r"\midrule",
         f"Base (sin temporada) & {c(BASE_USD)} & 0,00 & {c(BASE_USD*12)} & 0 & 0 \\\\"]
    for e in esc:
        nom = f"{e['tareas_por_servicio']} tareas" + (", RDS small en 2 bases" if e["bases_rds_en_small"] else "")
        L.append(f"{nom} & {c(e['mes_pico_usd'])} & {c(e['costo_temporada_usd'])} & {c(e['anual_con_temporada_usd'])} & {k(e['costo_temporada_cop'])} & {e['kits_adicionales']} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (d / "tabla_costo_temporada.tex").write_text("\n".join(L) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
