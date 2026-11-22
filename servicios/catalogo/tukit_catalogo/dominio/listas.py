from __future__ import annotations

from typing import Any

from tukit_comun.http import ErrorDominio

_MODOS_SURTIBLES = {"mercado_abierto", "libro_libre"}


def _exigir_sin_revisar(fila: Any) -> None:
    if fila is None:
        raise ErrorDominio("version_no_existe", "No hay ninguna version con ese identificador.", estado=404)
    if fila.revisada_en is not None:
        raise ErrorDominio(
            "lista_ya_revisada",
            "Esa version ya fue revisada. Para corregirla, crea una version nueva.",
            estado=409,
        )


def _cuidar_invariantes(concepto_id: Any, requiere_revision: Any, modo: Any, instruccion: Any) -> None:
    if concepto_id is None and requiere_revision is False:
        raise ErrorDominio(
            "renglon_sin_concepto_va_a_revision",
            "Un renglon sin concepto siempre requiere revision.",
            estado=422,
            campo="requiere_revision",
        )
    if modo is not None and modo not in _MODOS_SURTIBLES and not instruccion:
        raise ErrorDominio(
            "no_surtible_sin_instruccion",
            "Un renglon que Tukit no surte tiene que decir como conseguirlo (instruccion_colegio).",
            estado=422,
            campo="instruccion_colegio",
        )


def _item_publico(fila: Any) -> dict[str, Any]:
    return {
        "item_id": str(fila.id),
        "orden": int(fila.orden),
        "texto_original": fila.texto_original,
        "cantidad": int(fila.cantidad),
        "unidad": fila.unidad,
        "tipo_item": fila.tipo_item,
        "modo_adquisicion": fila.modo_adquisicion,
        "instruccion_colegio": fila.instruccion_colegio,
        "url_externa": fila.url_externa,
        "atributos": dict(fila.atributos or {}),
        "requiere_revision": bool(fila.requiere_revision),
        "concepto": (
            {"codigo": fila.concepto_codigo, "nombre": fila.concepto_nombre} if fila.concepto_codigo else None
        ),
    }


def _pagina_percepcion(pagina: Any) -> dict[str, Any]:
    if not isinstance(pagina, dict):
        return {"pagina": 1, "crudo": str(pagina)}
    crudo = pagina.get("crudo")
    if isinstance(crudo, list):
        crudo = "\n".join(
            f"{it.get('cantidad')} {it.get('descripcion', '')}".strip()
            if isinstance(it, dict) and it.get("cantidad")
            else (it.get("descripcion", "") if isinstance(it, dict) else str(it))
            for it in crudo
        )
    elif not isinstance(crudo, str):
        crudo = "" if crudo is None else str(crudo)
    return {"pagina": pagina.get("pagina", 1), "crudo": crudo}
