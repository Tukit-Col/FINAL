from __future__ import annotations

import uuid
from typing import Any

_PLANTILLAS = {
    "kits_publicados": "kits_publicados",
    "pedido_pagado": "pedido_pagado",
    "incidencia": "incidencia",
    "pedido_en_preparacion": "pedido_en_preparacion",
    "pedido_cancelado": "pedido_cancelado",
    "pedido_despachado": "pedido_despachado",
    "pedido_en_reparto": "pedido_en_reparto",
    "pedido_entregado": "pedido_entregado",
    "caso_respuesta": "caso_respuesta",
}

_USUARIO_EN_CARGA = frozenset(
    {
        "pedido_pagado",
        "incidencia",
        "pedido_en_preparacion",
        "pedido_cancelado",
        "pedido_despachado",
        "pedido_en_reparto",
        "pedido_entregado",
        "caso_respuesta",
    }
)

_REPARTIDOR_POR_OMISION = "nuestro repartidor"


def plantilla_para(tipo: str) -> str | None:
    return _PLANTILLAS.get(tipo)


def destinatario_en_carga(tipo: str, carga: dict[str, Any] | None) -> str | None:
    if tipo not in _USUARIO_EN_CARGA:
        return None
    usuario = (carga or {}).get("usuario_id")
    return str(usuario) if usuario else None


def destinatario_de_la_cola(tipo: str, carga: dict[str, Any] | None) -> str | None:
    if tipo not in _PLANTILLAS:
        return None
    usuario = (carga or {}).get("usuario_id")
    return str(usuario) if usuario else None


def lugar_de(colegio_nombre: str | None, grado: str | None) -> str:
    partes = []
    if colegio_nombre and colegio_nombre.strip():
        partes.append(colegio_nombre.strip())
    if grado and str(grado).strip():
        partes.append(f"grado {str(grado).strip()}")
    return ", ".join(partes) or "tu lista escolar"


def _y(partes: list[str]) -> str:
    if len(partes) <= 1:
        return partes[0] if partes else ""
    return f"{', '.join(partes[:-1])} y {partes[-1]}"


def _listas_de(carga: dict[str, Any]) -> list[dict[str, str]]:
    crudas = carga.get("listas")
    if isinstance(crudas, list) and crudas:
        salida = []
        for lista in crudas:
            if isinstance(lista, dict):
                par = {
                    "colegio_id": str(lista.get("colegio_id") or ""),
                    "grado": str(lista.get("grado") or ""),
                }
                if par not in salida:
                    salida.append(par)
        if salida:
            return salida
    return [{"colegio_id": str(carga.get("colegio_id") or ""), "grado": str(carga.get("grado") or "")}]


def lugares_de(listas: list[dict[str, Any]], nombres: dict[str, str | None]) -> str:
    if not listas:
        return lugar_de(None, None)
    grupos: dict[str, list[str]] = {}
    for lista in listas:
        colegio = str(lista.get("colegio_id") or "")
        grado = str(lista.get("grado") or "").strip()
        grados = grupos.setdefault(colegio, [])
        if grado and grado not in grados:
            grados.append(grado)
    partes = []
    for colegio, grados in grupos.items():
        nombre = (nombres.get(colegio) or "").strip()
        trozo = []
        if nombre:
            trozo.append(nombre)
        if grados:
            trozo.append(f"{'grados' if len(grados) > 1 else 'grado'} {_y(grados)}")
        if trozo:
            partes.append(", ".join(trozo))
    return _y(partes) or lugar_de(None, None)


def _uuid_o_none(valor: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(valor)) if valor else None
    except ValueError:
        return None


def datos_plantilla(
    tipo: str,
    agregado_id: uuid.UUID,
    carga: dict[str, Any] | None,
    *,
    base_web: str,
    colegio_nombre: str | None = None,
    colegios: dict[str, str | None] | None = None,
) -> dict[str, object]:
    carga = carga or {}
    datos: dict[str, object] = {}
    pedido_id = _uuid_o_none(carga.get("pedido_id"))
    if pedido_id is not None:
        datos["pedido"] = str(pedido_id)[:8].upper()
        datos["enlace"] = f"{base_web}/pedidos/{pedido_id}"
    if tipo == "pedido_pagado" and carga.get("total") is not None:
        datos["total"] = carga["total"]
    if tipo == "incidencia" and carga.get("motivo"):
        datos["motivo"] = str(carga["motivo"])
    if tipo == "pedido_en_preparacion":
        datos["retoma"] = bool(carga.get("retoma"))
    if tipo == "pedido_cancelado":
        datos["reembolso"] = bool(carga.get("reembolso"))
    if tipo == "caso_respuesta":
        datos["caso"] = str(agregado_id)[:8].upper()
    if tipo == "kits_publicados":
        datos["enlace"] = f"{base_web}/kits/{agregado_id}"
        listas = _listas_de(carga)
        nombres = dict(colegios or {})
        if colegio_nombre and carga.get("colegio_id"):
            nombres.setdefault(str(carga["colegio_id"]), colegio_nombre)
        datos["lugar"] = lugares_de(listas, nombres)
        datos["listas"] = [lugar_de(nombres.get(li["colegio_id"]), li["grado"]) for li in listas]
    if tipo == "pedido_despachado":
        datos["repartidor"] = str(carga.get("repartidor") or "").strip() or _REPARTIDOR_POR_OMISION
    return datos
