"""Rearmar los kits canonicos cuando cambia como se arman.

El poller no rearma una version que ya tiene canonico (aprobar dos veces no
cuesta dos optimizaciones). Cuando cambia la logica (filtro por atributos,
juntar herramientas), `regenerar_canonicos` los rearma; pero salta los que un
admin aprobo desde la previsualizacion o corrigio a mano, porque rearmarlos
borraria lo que eligio.
"""

from __future__ import annotations

import uuid

from test_canonico_lista import COLEGIO, GRADO, _preview, _puntero
from test_fastroute import _catalogo_verificado
from tukit_inteligencia import trabajos
from tukit_inteligencia.poller import armar_canonico, regenerar_canonicos


class TestRegenerarCanonicos:
    async def test_rearma_el_canonico_automatico_con_un_trabajo_nuevo(self, motor):
        catalogo = _catalogo_verificado()
        catalogo.grado = GRADO
        version = str(uuid.uuid4())
        primero = await armar_canonico(motor, catalogo, COLEGIO, GRADO, 2026, version)
        assert await _puntero(motor) == primero

        rearmados, saltados = await regenerar_canonicos(motor, catalogo)

        assert rearmados == 1
        assert saltados == []
        nuevo = await _puntero(motor)
        assert nuevo != primero

    async def test_salta_el_que_un_admin_aprobo_desde_la_previsualizacion(self, motor):
        preview = await _preview(motor, uuid.uuid4())
        await trabajos.fijar_como_canonico(motor, preview)

        rearmados, saltados = await regenerar_canonicos(motor, _catalogo_verificado())

        assert rearmados == 0
        assert len(saltados) == 1
        assert await _puntero(motor) == preview
