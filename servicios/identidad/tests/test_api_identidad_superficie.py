from __future__ import annotations

import pytest
from tukit_identidad.api import app


def test_las_rutas_vienen_de_un_router_incluido(cliente):
    from tukit_identidad.routers import router

    montadas = {r.path for r in router.routes}
    assert "/v1/colegios" in montadas
    assert "/v1/sesiones" in montadas
    assert "/v1/cuenta/direcciones/{direccion_id}" in montadas


class TestLaSuperficieDeMenoresNoEstaAbierta:
    @pytest.mark.parametrize(
        "ruta",
        ["/v1/estudiantes", "/v1/matriculas", "/v1/usuarios", "/v1/colegios/2.4/estudiantes"],
    )
    async def test_no_hay_ruta_que_devuelva_datos_de_menores(self, cliente, ruta):
        assert (await cliente.get(ruta)).status_code in {404, 422}

    def test_el_esquema_publicado_no_anuncia_ninguna(self):
        rutas = set(app.openapi()["paths"])
        assert rutas == {
            "/salud",
            "/health/live",
            "/health/ready",
            "/v1/colegios",
            "/v1/colegios/{colegio_id}",
            "/v1/grados",
            "/v1/contactos",
            "/v1/contactos/{usuario_id}",
            "/v1/contactos/{usuario_id}/credencial",
            "/v1/directorio/{dane}",
            "/v1/usuarios/nombres",
            "/v1/sesiones",
            "/v1/sesiones/actual",
            "/v1/sesiones/cierre",
            "/v1/cuenta",
            "/v1/cuenta/direcciones",
            "/v1/cuenta/direcciones/{direccion_id}",
            "/v1/cuenta/hijos",
            "/v1/cuenta/matriculas",
            "/v1/cuenta/matriculas/{matricula_id}",
            "/v1/cuenta/mis-datos",
            "/v1/cuenta/mis-datos/exportar",
            "/v1/cuenta/consentimientos/revocar",
            "/v1/cuenta/supresion",
            "/v1/registro",
            "/v1/admin/acudientes",
        }
