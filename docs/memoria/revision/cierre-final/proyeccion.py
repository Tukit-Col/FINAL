"""Proyección a tres años (estructura de Daniel, Dossier OE1) recalculada con el
escenario base vigente de docs/negocio/punto_equilibrio.py.

Por kit: ticket medido Ahorrador solo útiles, comisión 15 %, Wompi + IVA, IA,
logística a domicilio base y CAC (todo importado del script vigente).
Rampa de kits, costos fijos por año, inversión, reparto de la inversión,
amortización a 5 años y tasa de descuento: supuestos del equipo (Daniel).
Uso: python3 -I proyeccion.py
"""
import importlib.util, pathlib, statistics

RAIZ = pathlib.Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location("pe", RAIZ / "docs/negocio/punto_equilibrio.py")
pe = importlib.util.module_from_spec(spec); spec.loader.exec_module(pe)

TICKET = statistics.mean(g[1] for g in pe.KITS_CANONICOS)        # $609.343
COMISION = TICKET * pe.COMISION
VARIABLE = pe.wompi(TICKET) + pe.IA_POR_KIT + pe.LOGISTICA["domicilio_base"] + pe.CAC
CONTRIB = COMISION - VARIABLE                                     # $29.353

# Supuestos del equipo (Daniel, Dossier OE1)
KITS = [1_500, 8_000, 25_000]
FIJOS = [15e6, 40e6, 120e6]
INVERSION = 70e6
PLATAFORMA = 0.55 * INVERSION      # desarrollo 40 % + infraestructura 15 %
MERCADEO = 0.25 * INVERSION        # gasto del año 1
AMORT = PLATAFORMA / 5
TASA = 0.20

M = lambda x: f"{x/1e6:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
print(f"Ticket {TICKET:,.0f}  comisión {COMISION:,.0f}  variables {VARIABLE:,.0f}  contribución {CONTRIB:,.0f}")
print(f"Equilibrio año 1 (fijos {FIJOS[0]/1e6:.0f} M): {pe.equilibrio(FIJOS[0], CONTRIB)} kits")
filas = {k: [] for k in ["Kits", "Ingresos", "Variables", "Contribución", "Fijos", "Operativo",
                         "Mercadeo", "Amortización", "Antes de impuestos", "Efectivo", "Plataforma neta",
                         "Acumulados"]}
caja, acum = INVERSION - PLATAFORMA, 0.0
for t, (k, f) in enumerate(zip(KITS, FIJOS)):
    ing, var = k * COMISION, k * VARIABLE
    op = ing - var - f
    mk = MERCADEO if t == 0 else 0
    ai = op - mk - AMORT
    caja += op - mk
    acum += ai
    for n, v in zip(filas, [k, ing, var, ing - var, f, op, mk, AMORT, ai, caja, PLATAFORMA - AMORT * (t + 1), acum]):
        filas[n].append(v)
for n, vs in filas.items():
    print(f"{n:20s}", " | ".join(f"{v:,}".replace(",", ".") if n == "Kits" else M(v) for v in vs))
vpn = sum(op / (1 + TASA) ** (t + 1) for t, op in enumerate(filas["Operativo"])) - INVERSION
print("VPN (operativos al 20 %, menos la inversión):", M(vpn), "M")
