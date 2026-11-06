"""Contribución por kit y punto de equilibrio de Tukit, con cada supuesto y su fuente.

Python puro, sin red ni base de datos: los datos medidos van copiados abajo con la
consulta que los produjo, para que el cálculo se pueda repetir y auditar.

Uso:
    python3 docs/negocio/punto_equilibrio.py

Cada supuesto lleva una etiqueta:
    medido            sale de una corrida o consulta nuestra, reproducible
    tarifa publicada  precio que publica el proveedor (con fecha de consulta)
    supuesto del equipo  decisión o estimación interna, sin medición detrás
"""

from __future__ import annotations

import math
from statistics import mean, median

# ---------------------------------------------------------------------------
# 1. Ticket: kits canónicos publicados del Agustiniano (colegio piloto)
# ---------------------------------------------------------------------------
# MEDIDO. Fuente: tukit_inteligencia.kit_canonico + kit + linea_kit, base local,
# 13 kits canónicos del COLEGIO AGUSTINIANO CIUDAD SALITRE (colegio_id
# bccf0294-f6b2-5203-84dd-e7fc643ae17f), año lectivo 2026, publicados el
# 2026-11-02 por trabajos con origen 'canonico_lista' y sin usuario (no son
# pedidos ni datos de la prueba de carga del 2026-11-05). Consulta (solo lectura):
#   SELECT kc.grado, k.perfil, k.total_cop,
#          SUM(l.subtotal_cop) FILTER (WHERE l.tipo='util'),
#          SUM(l.subtotal_cop) FILTER (WHERE l.tipo='libro_libre')
#   FROM kit_canonico kc JOIN kit k ON k.trabajo_id = kc.trabajo_id
#   JOIN linea_kit l ON l.kit_id = k.id
#   WHERE kc.colegio_id = 'bccf0294-...' GROUP BY 1, 2, 3;
# Control: `python ensayos/kits_offline.py` sobre datos/ del commit 7aba82c da
# los mismos totales (Ahorrador $10.604.060, Premium $19.812.327).
# Columnas: grado, Ahorrador (útiles, libros), Premium (útiles, libros).
# 'libros' son los textos del plan lector (concepto libro_libre); uniformes,
# licencias y lo que no se vende llegan en $0 y no suman.
KITS_CANONICOS = [
    ("Jardin", 801290, 0, 1535495, 0),
    ("Transicion", 755930, 0, 1290724, 0),
    ("Primero", 452114, 75223, 820949, 105000),
    ("Segundo", 481215, 83623, 862040, 241000),
    ("Tercero", 562797, 83623, 1100198, 241000),
    ("Cuarto", 542048, 119263, 997288, 276640),
    ("Quinto", 522288, 137933, 1067128, 295310),
    ("Sexto", 406780, 282161, 742255, 472538),
    ("Septimo", 701433, 285185, 1315010, 494962),
    ("Octavo", 668353, 298775, 1361580, 508552),
    ("Noveno", 669403, 380675, 1323520, 590452),
    ("Decimo", 622350, 527531, 1296497, 737308),
    ("Once", 735460, 408607, 1518497, 618384),
]

# MEDIDO (muestra chica). A tu Medida y Fan solo se arman cuando un acudiente los
# pide (ADR 0030), así que no hay kit canónico. Estos son los trabajos publicados
# del Agustiniano con un solo hijo, creados antes del 2026-11-05 (sesiones OE5 del
# 2-3 nov y dos cuentas del equipo). No cubren los 13 grados: no sirven de ticket.
OTROS_PERFILES = {
    "A tu Medida": [937129, 1539404, 1312445, 1164835, 992251, 1407085],
    "Fan": [840336, 1081978, 1233817, 1070580, 698180],
}

# SUPUESTO DEL EQUIPO (estimación por cursos). Estudiantes por grado para ponderar
# el ticket: docs/validacion/oe5/06_agustiniano_tamano.md §4 (error ±15 % por grado).
ESTUDIANTES = {
    "Jardin": 60, "Transicion": 60, "Primero": 144, "Segundo": 120, "Tercero": 168,
    "Cuarto": 144, "Quinto": 120, "Sexto": 144, "Septimo": 144, "Octavo": 144,
    "Noveno": 144, "Decimo": 144, "Once": 144,
}

# Referencias históricas (para la conciliación, no para el cálculo nuevo).
TICKET_DOSSIER = 180_000  # supuesto del equipo: Dossier OE1 (oct 2026) §Punto de equilibrio
TICKET_FLUJO_CAJA = 620_000  # $8.057.305 / 13: auditoría v4 (commit 4dc3bc8, 2026-10-12), sin libros

# ---------------------------------------------------------------------------
# 2. Costos y comisión
# ---------------------------------------------------------------------------
# SUPUESTO DEL EQUIPO. Comisión sobre el ticket: Dossier OE1 (base 15 %, pesimista
# 10 %, optimista 20 %). No hay acuerdo con proveedores que la respalde, y la
# encuesta (REQUISITOS_DIFERIDOS §2.1) dice que el 70 % no pagaría más de 5 % de
# sobreprecio.
COMISION = 0.15

# TARIFA PUBLICADA. Wompi Plan Avanzado: "2,65 % + $700 + IVA por transacción
# exitosa", igual para tarjetas, PSE, Nequi y Botón Bancolombia
# (https://wompi.com/es/co/planes-tarifas/, consultado 2026-11-05). El repo solo
# tenía la cifra de un tercero (Studio Contra: PSE 1,49 %, tarjeta 2,99 %).
WOMPI_PCT = 0.0265
WOMPI_FIJO = 700
IVA = 0.19  # tarifa general de IVA en Colombia, sobre la comisión de Wompi

# SUPUESTO DEL EQUIPO (cota alta). IA por kit: Dossier OE1. No hay medición del
# costo de leer una lista; la lista oficial se lee una vez por grado y sirve a
# todas las familias. Lo único medido es el NL2C: 616 tokens de entrada y 40 de
# salida por pedido, US$0,000078 con un precio de lista también supuesto
# (docs/informes/nl2c/tablas_ronda3.md). El consumo de Gemini del piloto ya va
# dentro de la infraestructura (estudio 07 §D: ~$16.000/mes).
IA_POR_KIT = 1_000

# SUPUESTO DEL EQUIPO armado con tarifas publicadas de terceros. Logística por kit
# (empaque + recogida + entrega): docs/validacion/oe5/07_logistica_e_infra_piloto.md.
LOGISTICA = {
    "domicilio_bajo": 20_000, "domicilio_base": 33_000, "domicilio_alto": 54_000,
    "colegio_bajo": 8_000, "colegio_base": 13_000, "colegio_alto": 22_000,
}

# SUPUESTO DEL EQUIPO. CAC por kit: Dossier OE1 ("decisión interna, sin respaldo").
CAC = 8_000

# Infraestructura al mes.
# Piloto: SUPUESTO DEL EQUIPO sobre TARIFAS PUBLICADAS. El estudio 07 §D suma
# ~$63.000/mes (Hetzner CX33, backups, dominio .co, Gemini); el flujo de caja usa
# $100.000 para dejar margen.
INFRA_PILOTO_MES = 100_000
# Escalable: SUPUESTO DEL EQUIPO. Son los $15.000.000/año de costos fijos del
# Dossier (cloud $12M + herramientas $3M) divididos entre 12.
INFRA_ESCALABLE_MES = 1_250_000

# SUPUESTO DEL EQUIPO. Gastos de arranque del piloto (Nestle/scripts/flujo_caja.py):
# constitución de la SAS $1.000.000 y sesiones de validación $300.000.
ARRANQUE = 1_300_000

# Proyección del piloto.
# MEDIDO + supuesto: 1.705 alumnos (MEN 2025, dato oficial) llevados a 1.680 en 2026
# y 1,25 hijos por familia (encuesta: 78,3 % con un solo hijo) = ~1.340 familias
# (estudio 06 §5).
FAMILIAS = 1_340
# SUPUESTO DEL EQUIPO. Conversión: no hay medición de compra; el 58,3 % es intención.
CONVERSIONES = {"floja": 0.05, "base": 0.08, "buena": 0.15}


# ---------------------------------------------------------------------------
# 3. Cálculo
# ---------------------------------------------------------------------------
def wompi(ticket: float, pct: float = WOMPI_PCT) -> float:
    return (ticket * pct + WOMPI_FIJO) * (1 + IVA)


def contribucion(ticket: float, logistica: float, comision: float = COMISION,
                 cac: float = CAC, pct: float = WOMPI_PCT) -> float:
    return ticket * comision - wompi(ticket, pct) - IA_POR_KIT - logistica - cac


def equilibrio(fijo_anual: float, contrib: float) -> int | None:
    """Kits al año para cubrir el costo fijo; None si cada kit pierde plata."""
    return math.ceil(fijo_anual / contrib) if contrib > 0 else None


def cop(x: float) -> str:
    return f"${round(x):,}".replace(",", ".").replace("$-", "-$")


def kits(x: int | None) -> str:
    return "no se alcanza" if x is None else f"{x:,}".replace(",", ".")


def main() -> None:
    util_a = [g[1] for g in KITS_CANONICOS]
    total_a = [g[1] + g[2] for g in KITS_CANONICOS]
    util_p = [g[3] for g in KITS_CANONICOS]
    total_p = [g[3] + g[4] for g in KITS_CANONICOS]
    pesos = [ESTUDIANTES[g[0]] for g in KITS_CANONICOS]
    pond = sum(u * w for u, w in zip(util_a, pesos)) / sum(pesos)

    ticket = mean(util_a)  # ticket base: Ahorrador, solo útiles, promedio simple

    print("## 1. Ticket medido (Agustiniano, 13 grados, kits canónicos del 2026-11-02)\n")
    print("| Perfil | Base | Kits | Promedio | Mediana | Mínimo | Máximo |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for nombre, base, serie in (
        ("Ahorrador", "solo útiles", util_a),
        ("Ahorrador", "útiles + plan lector", total_a),
        ("Premium", "solo útiles", util_p),
        ("Premium", "útiles + plan lector", total_p),
        *((p, "útiles + plan lector (pedidos OE5)", s) for p, s in OTROS_PERFILES.items()),
    ):
        print(f"| {nombre} | {base} | {len(serie)} | {cop(mean(serie))} | {cop(median(serie))} "
              f"| {cop(min(serie))} | {cop(max(serie))} |")
    print(f"\nAhorrador solo útiles ponderado por estudiantes por grado: {cop(pond)}.")
    print(f"Suma Ahorrador solo útiles: {cop(sum(util_a))}; con plan lector: {cop(sum(total_a))}.\n")

    print("## 2. Contribución y punto de equilibrio\n")
    escenarios = [
        ("Bajo (domicilio caro)", ticket, LOGISTICA["domicilio_alto"]),
        ("Base (domicilio)", ticket, LOGISTICA["domicilio_base"]),
        ("Alto (entrega en el colegio)", ticket, LOGISTICA["colegio_base"]),
    ]
    print("| Escenario | Ticket | Comisión 15 % | Wompi + IVA | IA | Logística | CAC "
          "| Contribución por kit | Equilibrio, infra piloto ($1,2 M/año) "
          "| Equilibrio, infra escalable ($15 M/año) |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for nombre, t, log in escenarios:
        c = contribucion(t, log)
        print(f"| {nombre} | {cop(t)} | {cop(t * COMISION)} | {cop(wompi(t))} | {cop(IA_POR_KIT)} "
              f"| {cop(log)} | {cop(CAC)} | **{cop(c)}** | {kits(equilibrio(12 * INFRA_PILOTO_MES, c))} "
              f"| {kits(equilibrio(12 * INFRA_ESCALABLE_MES, c))} |")

    print("\n## 3. Sensibilidad sobre el escenario base (cambia una sola cosa)\n")
    print("| Cambio | Contribución por kit | Equilibrio piloto | Equilibrio escalable |")
    print("| --- | ---: | ---: | ---: |")
    sens = [
        ("Ticket con plan lector", contribucion(mean(total_a), LOGISTICA["domicilio_base"])),
        ("Ticket mediano (solo útiles)", contribucion(median(util_a), LOGISTICA["domicilio_base"])),
        ("Ticket ponderado por estudiantes", contribucion(pond, LOGISTICA["domicilio_base"])),
        ("Ticket del flujo de caja ($620.000)", contribucion(TICKET_FLUJO_CAJA, LOGISTICA["domicilio_base"])),
        ("Comisión 10 %", contribucion(ticket, LOGISTICA["domicilio_base"], comision=0.10)),
        ("Comisión 20 %", contribucion(ticket, LOGISTICA["domicilio_base"], comision=0.20)),
        ("Wompi 2,99 % (cifra de tercero)", contribucion(ticket, LOGISTICA["domicilio_base"], pct=0.0299)),
        ("Sin CAC", contribucion(ticket, LOGISTICA["domicilio_base"], cac=0)),
    ]
    for nombre, c in sens:
        print(f"| {nombre} | {cop(c)} | {kits(equilibrio(12 * INFRA_PILOTO_MES, c))} "
              f"| {kits(equilibrio(12 * INFRA_ESCALABLE_MES, c))} |")

    print("\n## 4. Proyección del piloto (1.340 familias, escenario base)\n")
    c_base = contribucion(ticket, LOGISTICA["domicilio_base"])
    print("| Conversión (supuesto) | Kits | Contribución total | Infra del año | Arranque | Resultado |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    for nombre, conv in CONVERSIONES.items():
        n = round(FAMILIAS * conv)
        res = n * c_base - 12 * INFRA_PILOTO_MES - ARRANQUE
        print(f"| {nombre} ({conv:.0%}) | {n} | {cop(n * c_base)} | {cop(12 * INFRA_PILOTO_MES)} "
              f"| {cop(ARRANQUE)} | {cop(res)} |")
    n_min = math.ceil((12 * INFRA_PILOTO_MES + ARRANQUE) / c_base)
    print(f"\nKits para cubrir infra del año más arranque: {n_min} "
          f"({str(round(100 * n_min / FAMILIAS, 1)).replace(".", ",")} % de las familias).")

    print("\n## 5. Conciliación con las cifras anteriores\n")
    c_dossier = TICKET_DOSSIER * COMISION - wompi(TICKET_DOSSIER) - IA_POR_KIT
    c_dossier_log = contribucion(TICKET_DOSSIER, LOGISTICA["domicilio_base"])
    c_flujo = contribucion(TICKET_FLUJO_CAJA, LOGISTICA["domicilio_base"])
    print("| Cifra | Cálculo | Resultado |")
    print("| --- | --- | ---: |")
    print(f"| 770 (Dossier) | $15.000.000 / ($27.000 - Wompi {cop(wompi(TICKET_DOSSIER))} - IA $1.000"
          f" = {cop(c_dossier)}); sin logística ni CAC | {kits(equilibrio(15_000_000, c_dossier))} |")
    print(f"| Dossier con logística y CAC | ticket $180.000, logística $33.000, CAC $8.000:"
          f" contribución {cop(c_dossier_log)} | {kits(equilibrio(15_000_000, c_dossier_log))} |")
    print(f"| 40 (flujo de caja) | $1.200.000 / {cop(c_flujo)} | {kits(equilibrio(1_200_000, c_flujo))} |")
    print(f"| 490 (flujo de caja) | $15.000.000 / {cop(c_flujo)} | {kits(equilibrio(15_000_000, c_flujo))} |")
    c_299 = contribucion(TICKET_FLUJO_CAJA, LOGISTICA["domicilio_base"], pct=0.0299)
    print(f"| 43 (sin fuente) | candidato 1: flujo de caja con Wompi 2,99 %: $1.200.000 / {cop(c_299)}"
          f" | {kits(equilibrio(1_200_000, c_299))} |")
    print(f"| 43 (sin fuente) | candidato 2: kits de diciembre del flujo de caja:"
          f" ROUND(1.340 x 8 % x 40 %) | {round(FAMILIAS * 0.08 * 0.40)} |")
    print("| 47 (dicho en sesión) | ninguna fórmula documentada lo produce | n/a |")


if __name__ == "__main__":
    main()
