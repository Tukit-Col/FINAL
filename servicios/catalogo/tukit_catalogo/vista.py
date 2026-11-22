from __future__ import annotations

import argparse
import asyncio
import html
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SALIDA = Path("catalogo.html")

ESTILOS = """
:root {
  --tinta: #16181d; --suave: #6b7280; --linea: #e5e7eb; --fondo: #fbfbfc;
  --ok: #15803d; --aviso: #b45309; --malo: #b91c1c; --acento: #1d4ed8;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--tinta);
  font: 15px/1.55 ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif; }
header { background: #fff; border-bottom: 1px solid var(--linea); padding: 28px 32px; }
h1 { margin: 0 0 4px; font-size: 22px; letter-spacing: -0.02em; }
.sub { color: var(--suave); font-size: 13px; }
.cifras { display: flex; flex-wrap: wrap; gap: 28px; margin-top: 18px; }
.cifra b { display: block; font-size: 22px; font-variant-numeric: tabular-nums; }
.cifra span { color: var(--suave); font-size: 12px; text-transform: uppercase;
  letter-spacing: .04em; }
main { padding: 24px 32px 64px; }
.barra { position: sticky; top: 0; z-index: 5; background: var(--fondo);
  padding: 14px 0; border-bottom: 1px solid var(--linea); margin-bottom: 22px; }
.barra input, .barra select { font: inherit; padding: 7px 11px; border: 1px solid var(--linea);
  border-radius: 7px; background: #fff; }
.barra input { width: 300px; }
.concepto { margin-bottom: 30px; background: #fff; border: 1px solid var(--linea);
  border-radius: 11px; overflow: hidden; }
.cab { display: flex; align-items: baseline; gap: 12px; padding: 13px 17px;
  border-bottom: 1px solid var(--linea); flex-wrap: wrap; }
.cab h2 { margin: 0; font-size: 15px; }
.cab .cod { color: var(--suave); font-size: 12px; font-variant-numeric: tabular-nums; }
.pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--linea);
  color: var(--suave); }
.pill.completo { color: var(--ok); border-color: #bbf7d0; background: #f0fdf4; }
.pill.parcial  { color: var(--aviso); border-color: #fde68a; background: #fffbeb; }
.pill.vacio    { color: var(--malo); border-color: #fecaca; background: #fef2f2; }
.pill.libro    { color: var(--acento); border-color: #bfdbfe; background: #eff6ff; }
.rejilla { display: grid; gap: 1px; background: var(--linea);
  grid-template-columns: repeat(auto-fill, minmax(232px, 1fr)); }
.prod { background: #fff; padding: 14px; display: flex; flex-direction: column; gap: 7px; }
.prod img { width: 100%; height: 132px; object-fit: contain; background: #fff; }
.sinfoto { width: 100%; height: 132px; display: grid; place-items: center; background: #f6f7f9;
  color: #b6bcc6; font-size: 12px; border-radius: 6px; }
.nom { font-size: 13px; line-height: 1.35; min-height: 35px; }
.precio { font-size: 17px; font-variant-numeric: tabular-nums; font-weight: 600; }
.meta { font-size: 11px; color: var(--suave); display: flex; gap: 7px; flex-wrap: wrap; }
.nivel { font-size: 10.5px; text-transform: uppercase; letter-spacing: .05em; font-weight: 600; }
.nivel.economico { color: var(--ok); }
.nivel.confiable { color: var(--acento); }
.nivel.premium   { color: #7c3aed; }
.attrs { font-size: 11px; color: var(--suave); }
.attrs code { background: #f2f3f5; padding: 1px 5px; border-radius: 4px; margin-right: 3px; }
.revisar { font-size: 10.5px; color: var(--aviso); }
.oculto { display: none !important; }
a { color: inherit; }
"""

GUION = """
const caja = document.getElementById('buscar');
const filtro = document.getElementById('filtro');
function aplicar() {
  const q = caja.value.toLowerCase().trim();
  const f = filtro.value;
  document.querySelectorAll('.concepto').forEach(c => {
    const texto = c.dataset.buscar;
    const coincide = !q || texto.includes(q);
    const pasa = f === 'todo'
      || (f === 'huecos' && c.dataset.estado !== 'completo')
      || (f === 'libros' && c.dataset.libro === '1')
      || (f === 'revisar' && c.dataset.revisar === '1');
    c.classList.toggle('oculto', !(coincide && pasa));
  });
}
caja.addEventListener('input', aplicar);
filtro.addEventListener('change', aplicar);
"""


def _pesos(centavos: int | None) -> str:
    return f"${centavos // 100:,.0f}".replace(",", ".") if centavos else "sin precio"


def _tarjeta(p: dict[str, Any]) -> str:
    e = html.escape
    foto = (
        f'<img src="{e(p["imagen_url"])}" alt="" loading="lazy">'
        if p["imagen_url"]
        else '<div class="sinfoto">sin foto</div>'
    )
    empaque = (
        f"x{p['unidades_por_empaque']} {p['unidad_base']}" if p["unidades_por_empaque"] > 1 else "unidad"
    )
    attrs = "".join(f"<code>{e(str(k))}: {e(str(v))}</code>" for k, v in (p["atributos"] or {}).items())
    personaje = f"<span>{e(p['personaje'])}</span>" if p["personaje"] else ""
    revisar = (
        '<div class="revisar">sugerido por busqueda, sin revisar</div>'
        if float(p["quality_score"] or 0) < 0.5
        else ""
    )
    nombre = e(p["nombre"])
    enlace = f'<a href="{e(p["url"])}" target="_blank" rel="noopener">{nombre}</a>' if p["url"] else nombre
    return f"""<div class="prod">
      {foto}
      <div class="nivel {e(p["nivel"])}">{e(p["nivel"])}</div>
      <div class="nom">{enlace}</div>
      <div class="precio">{_pesos(p["precio"])}</div>
      <div class="meta"><span>{e(p["tienda"] or "sin tienda")}</span>
        <span>{e(empaque)}</span>{personaje}</div>
      <div class="attrs">{attrs or "<em>sin atributos</em>"}</div>
      {revisar}
    </div>"""


def construir(conceptos: list[dict[str, Any]], resumen: dict[str, int]) -> str:
    e = html.escape
    bloques = []
    for c in conceptos:
        niveles = {p["nivel"] for p in c["productos"]}
        if not c["productos"]:
            estado, etiqueta = "vacio", "sin productos"
        elif len(niveles) >= 3:
            estado, etiqueta = "completo", "3 niveles"
        else:
            estado, etiqueta = "parcial", f"{len(niveles)} de 3 niveles"

        por_revisar = any(float(p["quality_score"] or 0) < 0.5 for p in c["productos"])
        es_libro = c["tipo_item"] == "libro_libre"
        buscar = " ".join(
            [c["nombre"], c["codigo"], *(c["sinonimos"] or []), *(p["nombre"] for p in c["productos"])]
        ).lower()

        pastillas = [f'<span class="pill {estado}">{etiqueta}</span>']
        if es_libro:
            pastillas.append('<span class="pill libro">libro</span>')
        if c["tipo_item"] == "no_comprar":
            pastillas.append('<span class="pill vacio">no se surte</span>')
        if por_revisar:
            pastillas.append('<span class="pill parcial">tiene sin revisar</span>')
        pastillas.append(f'<span class="pill">pedido {c["demanda"]}x</span>')

        tarjetas = "".join(_tarjeta(p) for p in c["productos"]) or (
            '<div class="prod"><div class="sinfoto">nada que ofrecer todavia</div></div>'
        )
        bloques.append(f"""<section class="concepto" data-estado="{estado}"
        data-libro="{1 if es_libro else 0}" data-revisar="{1 if por_revisar else 0}"
        data-buscar="{e(buscar)}">
      <div class="cab"><h2>{e(c["nombre"])}</h2><span class="cod">{e(c["codigo"])}</span>
        {"".join(pastillas)}</div>
      <div class="rejilla">{tarjetas}</div>
    </section>""")

    momento = datetime.now(UTC).astimezone().strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Catalogo Tukit</title><style>{ESTILOS}</style></head>
<body>
<header>
  <h1>Catalogo Tukit</h1>
  <div class="sub">Lo que hoy se le puede ofrecer a un papa. Generado el {momento}
    desde la base, no desde los CSV.</div>
  <div class="cifras">
    <div class="cifra"><b>{resumen["productos"]}</b><span>productos</span></div>
    <div class="cifra"><b>{resumen["conceptos"]}</b><span>conceptos</span></div>
    <div class="cifra"><b>{resumen["completos"]}</b><span>con los 3 niveles</span></div>
    <div class="cifra"><b>{resumen["con_foto"]}</b><span>con foto</span></div>
    <div class="cifra"><b>{resumen["tiendas"]}</b><span>tiendas</span></div>
    <div class="cifra"><b>{resumen["por_revisar"]}</b><span>sin revisar</span></div>
  </div>
</header>
<main>
  <div class="barra">
    <input id="buscar" type="search" placeholder="buscar un util, una marca, un personaje...">
    <select id="filtro">
      <option value="todo">todo el catalogo</option>
      <option value="huecos">solo lo incompleto</option>
      <option value="libros">solo libros</option>
      <option value="revisar">solo lo que falta revisar</option>
    </select>
  </div>
  {"".join(bloques)}
</main>
<script>{GUION}</script>
</body></html>"""


async def _leer() -> tuple[list[dict[str, Any]], dict[str, int]]:
    from sqlalchemy import text
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    text("""
                SELECT c.codigo, c.nombre_canonico, c.tipo_item, c.frecuencia_demanda, c.sinonimos,
                       p.id AS pid, p.nombre, p.nivel, p.imagen_url, p.personaje, p.atributos,
                       p.unidad_base, p.unidades_por_empaque, p.quality_score,
                       t.nombre AS tienda, o.url,
                       -- El precio mas barato entre las tiendas que lo venden.
                       -- Es la cifra honesta: si el kit lo va a comprar donde
                       -- salga mejor, mostrar otra seria prometer de mas.
                       (SELECT min(pr.valor_centavos)
                          FROM oferta_tienda o2
                          JOIN precio_oferta pr ON pr.oferta_id = o2.id
                         WHERE o2.producto_canonico_id = p.id) AS precio
                  FROM concepto c
                  LEFT JOIN producto_canonico p ON p.concepto_id = c.id AND p.activo
                  LEFT JOIN LATERAL (
                        SELECT * FROM oferta_tienda o1
                         WHERE o1.producto_canonico_id = p.id AND o1.activo LIMIT 1
                  ) o ON true
                  LEFT JOIN tienda t ON t.id = o.tienda_id
                 WHERE c.activo
                 ORDER BY c.frecuencia_demanda DESC, c.codigo,
                          CASE p.nivel WHEN 'economico' THEN 1 WHEN 'confiable' THEN 2 ELSE 3 END
            """)
                )
            ).all()
            tiendas = (await conexion.execute(text("SELECT count(*) FROM tienda WHERE activa"))).scalar_one()
    finally:
        await motor.cerrar()

    conceptos: list[dict[str, Any]] = []
    indice: dict[str, dict[str, Any]] = {}
    for f in filas:
        bloque = indice.get(f.codigo)
        if bloque is None:
            bloque = {
                "codigo": f.codigo,
                "nombre": f.nombre_canonico,
                "tipo_item": f.tipo_item,
                "demanda": f.frecuencia_demanda,
                "sinonimos": list(f.sinonimos or ()),
                "productos": [],
            }
            indice[f.codigo] = bloque
            conceptos.append(bloque)
        if f.pid is not None:
            bloque["productos"].append(
                {
                    "nombre": f.nombre,
                    "nivel": f.nivel,
                    "imagen_url": f.imagen_url,
                    "personaje": f.personaje,
                    "atributos": f.atributos,
                    "unidad_base": f.unidad_base,
                    "unidades_por_empaque": f.unidades_por_empaque,
                    "quality_score": f.quality_score,
                    "tienda": f.tienda,
                    "url": f.url,
                    "precio": f.precio,
                }
            )

    productos = [p for c in conceptos for p in c["productos"]]
    resumen = {
        "productos": len(productos),
        "conceptos": len(conceptos),
        "completos": sum(1 for c in conceptos if len({p["nivel"] for p in c["productos"]}) >= 3),
        "con_foto": sum(1 for p in productos if p["imagen_url"]),
        "tiendas": tiendas,
        "por_revisar": sum(1 for p in productos if float(p["quality_score"] or 0) < 0.5),
    }
    return conceptos, resumen


async def _principal(destino: Path, abrir: bool) -> int:
    conceptos, resumen = await _leer()
    destino.write_text(construir(conceptos, resumen), encoding="utf-8")
    print(f"Escrito {destino.resolve()}")
    print(
        f"  {resumen['productos']} productos en {resumen['conceptos']} conceptos, "
        f"{resumen['completos']} con los 3 niveles, {resumen['por_revisar']} sin revisar"
    )
    if abrir:
        import webbrowser

        webbrowser.open(destino.resolve().as_uri())
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--salida", type=Path, default=SALIDA)
    analizador.add_argument("--abrir", action="store_true")
    args = analizador.parse_args()
    return asyncio.run(_principal(args.salida, args.abrir))


if __name__ == "__main__":
    sys.exit(main())
