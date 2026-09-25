"""El directorio DUEB de Bogota, parseado a registros de colegio.

Lo que hay que fijar aqui no es que el parser lea lineas. Es el identificador
y la forma del registro que despues cruza a Catalogo. El colegio del directorio
todavia NO existe en ninguna base: nace cuando un administrador aprueba en la
cola la lista que un acudiente subio. Para que la referencia entre Catalogo
(donde vive la lista) e Identidad (donde nacera el colegio) resuelva, el UUID
tiene que derivarse del codigo DANE con el MISMO `derivar` compartido, en las
dos puntas. Por eso el parser expone ese id ya derivado y las pruebas lo
comparan contra `tukit_comun.derivar`, no contra un UUID copiado a mano.
"""

from __future__ import annotations

from tukit_comun import derivar
from tukit_identidad.directorio_bogota import (
    parsear_directorio,
)

_BLOQUE = """DIRECTORIO UNICO DE ESTABLECIMIENTOS EDUCATIVOS DE BOGOTA (DUEB)
Total de colegios: 2
Fuente: https://dueb.educacionbogota.edu.co/Dueb/
==============================================================================

NOMBRE       : ACADEMIA CENTRAL DE SISTEMAS
DANE 12      : 311001105731
SECTOR       : NO OFICIAL
LOCALIDAD    : BARRIOS UNIDOS
DIRECCION    : AV CARACAS # 68 - 11
TELEFONO     : 6012352887  --  3223573876
EMAIL        : acsi86.edu.co@gmail.com  --  acsicolegio@gmail.com
WEB          : www.acsi.edu.co
RECTOR       : SANDRA MILENA MURCIA CUENCA

NOMBRE       : ACADEMIA LA SALLE SAN BENILDO
DANE 12      : 111848001097
SECTOR       : NO OFICIAL
LOCALIDAD    : USAQUEN
DIRECCION    : KR 7 # 172 - 85
TELEFONO     : 6711955 -- 6718299 -- 6797687
EMAIL        :
WEB          :
RECTOR       : HNO JAIRO ANTONIO HERNANDEZ JAUREGUI
"""


class TestParsearDirectorio:
    def test_lee_todos_los_colegios_del_bloque(self):
        colegios = parsear_directorio(_BLOQUE)
        assert len(colegios) == 2
        assert colegios[0].nombre == "ACADEMIA CENTRAL DE SISTEMAS"
        assert colegios[1].nombre == "ACADEMIA LA SALLE SAN BENILDO"

    def test_mapea_los_campos_utiles(self):
        c = parsear_directorio(_BLOQUE)[0]
        assert c.dane == "311001105731"
        assert c.localidad == "BARRIOS UNIDOS"
        assert c.sector == "NO OFICIAL"
        assert c.direccion == "AV CARACAS # 68 - 11"
        assert c.rector == "SANDRA MILENA MURCIA CUENCA"
        assert c.sitio_web == "www.acsi.edu.co"

    def test_parte_multivalor_en_el_primero(self):
        # Telefono y email traen varios separados por " -- "; para el contacto
        # del colegio nos quedamos con el primero, que es el principal.
        c = parsear_directorio(_BLOQUE)[0]
        assert c.telefono == "6012352887"
        assert c.email == "acsi86.edu.co@gmail.com"

    def test_campos_vacios_quedan_en_none(self):
        c = parsear_directorio(_BLOQUE)[1]
        assert c.email is None
        assert c.sitio_web is None

    def test_el_id_se_deriva_del_dane_con_el_contrato_compartido(self):
        # LA pieza que comparten dos bases: el mismo UUID desde Identidad (aqui)
        # y desde Catalogo (donde se guarda la lista antes de que el colegio
        # exista). Si esto se desviara, la lista apuntaria a un colegio fantasma.
        c = parsear_directorio(_BLOQUE)[0]
        assert c.id == derivar("colegio", "311001105731")

    def test_registro_sin_dane_se_descarta(self):
        # Sin DANE no hay identificador estable: no se puede crear el colegio de
        # forma idempotente, asi que no entra al directorio.
        bloque = "NOMBRE       : SIN CODIGO\nSECTOR       : NO OFICIAL\n"
        assert parsear_directorio(bloque) == []


class TestParaServirAlFrontend:
    def test_a_dict_trae_lo_que_el_buscador_necesita(self):
        # El JSON que sirve el web app: el buscador de /empezar filtra por
        # nombre y localidad, y manda el dane+nombre al subir. No lleva el UUID
        # (lo deriva el backend) ni el rector (no aporta a elegir el colegio).
        c = parsear_directorio(_BLOQUE)[0]
        d = c.a_dict_busqueda()
        assert d == {
            "dane": "311001105731",
            "nombre": "ACADEMIA CENTRAL DE SISTEMAS",
            "localidad": "BARRIOS UNIDOS",
        }

    def test_a_datos_colegio_nuevo_remapea_al_formulario(self):
        # El bloque con que la cola pre-llena el perfil del colegio nuevo: los
        # campos del DUEB se remapean a los del formulario. El rector es el
        # `contacto_nombre` (secretaria/contacto) y NO va `logo_url` (el DUEB no
        # lo trae; lo completa el revisor a mano).
        c = parsear_directorio(_BLOQUE)[0]
        assert c.a_datos_colegio_nuevo() == {
            "dane": "311001105731",
            "nombre": "ACADEMIA CENTRAL DE SISTEMAS",
            "direccion": "AV CARACAS # 68 - 11",
            "sitio_web": "www.acsi.edu.co",
            "contacto_email": "acsi86.edu.co@gmail.com",
            "contacto_telefono": "6012352887",
            "contacto_nombre": "SANDRA MILENA MURCIA CUENCA",
        }
        assert "logo_url" not in c.a_datos_colegio_nuevo()
