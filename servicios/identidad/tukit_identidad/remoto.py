"""Lo que el inventario de "mis datos" lee de los otros servicios.

Identidad no lee la base de Comercio, Operacion ni Inteligencia (invariante de
fronteras): les pregunta por HTTP con el MISMO Bearer del titular, a las rutas
que ya sirven su propio panel (`/v1/comercio/mis-pedidos`,
`/v1/operacion/mis-casos`, `/v1/trabajos`). Cada servicio valida ese token
contra Identidad como siempre, asi que no hay credencial nueva ni ruta interna
nueva: el titular ve lo mismo que ya ve en su panel, juntado en un lugar.

Es solo lectura y degrada por seccion: si un servicio no responde, esa seccion
sale con `disponible: false` y el resto del inventario sigue. Un inventario
parcial y honesto es mejor que un 502 sobre un derecho del titular.

Ojo con el sentido del grafo: aqui Identidad llama a los demas, que es al reves
de lo habitual. Es una lectura sincrona del titular sobre sus propios datos, no
una dependencia de dato (ninguna tabla ajena se declara ni se lee).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from tukit_comun.http import cliente_efimero

ESPERA_SEGUNDOS = 5.0


@dataclass(frozen=True)
class Fuente:
    """Una seccion del inventario: de que servicio sale y que lista trae."""

    seccion: str
    variable: str
    por_omision: str
    camino: str
    lista: str
    campos: tuple[str, ...]


FUENTES: tuple[Fuente, ...] = (
    Fuente(
        "pedidos",
        "TUKIT_COMERCIO_URL",
        "http://127.0.0.1:8014",
        "/v1/comercio/mis-pedidos",
        "pedidos",
        ("pedido_id", "estado", "total", "creado_en"),
    ),
    Fuente(
        "casos",
        "TUKIT_OPERACION_URL",
        "http://127.0.0.1:8015",
        "/v1/operacion/mis-casos",
        "casos",
        ("caso_id", "categoria", "estado", "abierto_en"),
    ),
    Fuente(
        "trabajos_kit",
        "TUKIT_INTELIGENCIA_URL",
        "http://127.0.0.1:8013",
        "/v1/trabajos",
        "trabajos",
        ("trabajo_id", "estado", "creado_en"),
    ),
)


@dataclass
class InventarioRemoto:
    """Los resumenes de los otros servicios. `cliente` se inyecta en pruebas."""

    cliente: httpx.AsyncClient | None = None
    fuentes: tuple[Fuente, ...] = field(default=FUENTES)

    async def resumen(self, token: str) -> dict[str, Any]:
        salida: dict[str, Any] = {}
        for fuente in self.fuentes:
            salida[fuente.seccion] = await self._uno(fuente, token)
        return salida

    async def _uno(self, fuente: Fuente, token: str) -> dict[str, Any]:
        base = os.environ.get(fuente.variable, fuente.por_omision).rstrip("/")
        try:
            async with cliente_efimero(self.cliente, ESPERA_SEGUNDOS) as cliente:
                r = await cliente.get(f"{base}{fuente.camino}", headers={"Authorization": f"Bearer {token}"})
            if r.status_code != 200:
                return {"disponible": False}
            cuerpo = r.json()
        except (httpx.HTTPError, ValueError):
            return {"disponible": False}
        elementos = cuerpo.get(fuente.lista) or []
        return {
            "disponible": True,
            "total": int(cuerpo.get("total", len(elementos))),
            # Solo punteros (id, estado, fecha): el detalle sigue en su servicio.
            "elementos": [
                {c: e.get(c) for c in fuente.campos if c in e} for e in elementos if isinstance(e, dict)
            ],
        }
