"""Instancias -> escenarios de papa, cada uno con su optimo exacto.

Escenarios (todos con un solo hijo):
- `ahorrador`: sin preferencias; el objetivo es el kit mas barato.
- `premium`: sin preferencias; el objetivo es la mejor marca posible.
- `fan`: el papa pide el personaje mas frecuente en la lista; el objetivo es el
  kit con mas lineas de ese personaje, al menor costo.
- `presupuesto`: tope a mitad de camino entre el kit mas barato y el Premium
  exactos; el objetivo es la mayor fidelidad que quepa.

Una lista sin compromiso real para un escenario (sin lineas decidibles, o con el
optimo igual a todos los extremos) se omite de ese escenario y se cuenta.
"""

from __future__ import annotations

from comun import (
    HIJO,
    cargar_json,
    decidibles,
    guardar_json,
    objetivos,
    optimo_ahorrador,
    optimo_fan,
    optimo_premium,
    optimo_presupuesto,
    personaje_de_lista,
    renglones_de,
)

FRACCION_PRESUPUESTO = 0.5


def main() -> int:
    datos = cargar_json("instancias.json")
    escenarios = []
    omitidos: dict[str, int] = {}

    def omitir(nombre: str) -> None:
        omitidos[nombre] = omitidos.get(nombre, 0) + 1

    for inst in datos["instancias"]:
        dec = decidibles(renglones_de(inst))
        if not dec:
            for e in ("ahorrador", "premium", "fan", "presupuesto"):
                omitir(e)
            continue
        base = {"instancia": inst["id"], "lineas": len(dec)}

        a = optimo_ahorrador(dec)
        p = optimo_premium(dec)
        oa, op = objetivos(dec, a, {}), objetivos(dec, p, {})
        escenarios.append({**base, "escenario": "ahorrador", "preferencias": {}, "optimo": a, "objetivos_optimo": oa})
        escenarios.append({**base, "escenario": "premium", "preferencias": {}, "optimo": p, "objetivos_optimo": op})

        personaje = personaje_de_lista(dec)
        if personaje:
            prefs = {"personaje_por_hijo": {HIJO: [personaje]}}
            f = optimo_fan(dec, {personaje})
            escenarios.append(
                {
                    **base,
                    "escenario": "fan",
                    "personaje": personaje,
                    "preferencias": prefs,
                    "optimo": f,
                    "objetivos_optimo": objetivos(dec, f, prefs),
                }
            )
        else:
            omitir("fan")

        if op["costo"] > oa["costo"] and op["fidelidad"] > oa["fidelidad"]:
            tope = int(oa["costo"] + FRACCION_PRESUPUESTO * (op["costo"] - oa["costo"]))
            prefs = {"presupuesto_por_hijo": tope, "disposicion_sobreprecio": 0.0}
            b = optimo_presupuesto(dec, tope)
            escenarios.append(
                {
                    **base,
                    "escenario": "presupuesto",
                    "presupuesto": tope,
                    "preferencias": prefs,
                    "optimo": b,
                    "objetivos_optimo": objetivos(dec, b, prefs),
                    "costo_ahorrador": oa["costo"],
                    "costo_premium": op["costo"],
                }
            )
        else:
            omitir("presupuesto")

    guardar_json("escenarios.json", {"catalogo": datos["catalogo"], "omitidos": omitidos, "escenarios": escenarios})
    cuenta: dict[str, int] = {}
    for e in escenarios:
        cuenta[e["escenario"]] = cuenta.get(e["escenario"], 0) + 1
    print("escenarios:", cuenta, "omitidos:", omitidos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
