"""Las reglas del ciclo de un caso, como dominio puro.

Que categorias puede abrir un acudiente (y por que se rechazan las otras), con
que prioridad nace un caso, cuando vence segun su SLA y como se ordena la
bandeja: todo calculo puro sobre las tablas de `modelos/base.py`, sin base ni
HTTP. Aqui se prueban de frente —la red de seguridad que la suite de la
superficie solo da de refilon (por el 422 y el orden de la bandeja)—; en
particular los desempates que hoy no toca ninguna prueba: prioridad desconocida
y caso sin vencimiento.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tukit_operacion.dominio.casos import (
    CategoriaRechazada,
    admitir_categoria_acudiente,
    clave_orden,
    prioridad_inicial,
    vence_en,
)
from tukit_operacion.modelos import CategoriaCaso, Prioridad

AHORA = datetime(2026, 1, 1, tzinfo=UTC)


def test_admite_una_categoria_de_acudiente():
    assert admitir_categoria_acudiente("peticion") is CategoriaCaso.PETICION


def test_rechaza_categoria_de_saga_como_no_permitida():
    # mapeo_lista es una falla de la saga: la abre el sistema, no una persona.
    rechazo = admitir_categoria_acudiente("mapeo_lista")
    assert isinstance(rechazo, CategoriaRechazada)
    assert rechazo.razon == "categoria_no_permitida"
    assert rechazo.estado == 422


def test_rechaza_categoria_inexistente_como_invalida():
    # Un texto que no es ninguna categoria: distinto del "no permitida".
    rechazo = admitir_categoria_acudiente("inventada")
    assert isinstance(rechazo, CategoriaRechazada)
    assert rechazo.razon == "categoria_invalida"
    assert rechazo.estado == 422


def test_prioridad_inicial_por_categoria():
    assert prioridad_inicial(CategoriaCaso.PAGO) is Prioridad.URGENTE
    assert prioridad_inicial(CategoriaCaso.SUGERENCIA) is Prioridad.BAJA


def test_vence_en_pago_antes_que_peticion():
    pago = vence_en(CategoriaCaso.PAGO, AHORA)
    peticion = vence_en(CategoriaCaso.PETICION, AHORA)
    assert pago == AHORA + timedelta(hours=24)
    assert pago < peticion  # 24 h de negocio contra 15 dias de Ley 1755


def test_clave_orden_urgente_va_antes_que_media():
    assert clave_orden("urgente", AHORA) < clave_orden("media", AHORA)


def test_clave_orden_sin_vencimiento_va_al_final_de_su_grupo():
    # Mismo rango de prioridad: el que vence primero va antes; el que no vence
    # nunca, al fondo del grupo.
    assert clave_orden("alta", AHORA) < clave_orden("alta", None)


def test_clave_orden_prioridad_desconocida_va_al_fondo():
    # Una prioridad que no existe no revienta el orden: cae al rango 99.
    assert clave_orden("inexistente", AHORA) > clave_orden("baja", AHORA)
