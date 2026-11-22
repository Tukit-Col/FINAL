"""Exporta (SOLO SELECT) los renglones de versiones vigentes revisadas, con origen de la revision.
Salida: datos/renglones_etiquetados_v2.csv. Excluye versiones vigentes sin revision (listas de demostracion 'sugerencia_padre').
Salida: datos/renglones_etiquetados_v2.csv. Excluye versiones vigentes sin revision (listas de demostracion 'sugerencia_padre')."""

import csv
import io
import os
import subprocess
from pathlib import Path

E = {**os.environ, "PGGSSENCMODE": "disable", "PGPASSWORD": "tukit"}


def q(base, sql):
    assert sql.lstrip().lower().startswith("select")
    r = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-U", "tukit", "-d", base, "-c", f"copy ({sql}) to stdout with csv"],
        capture_output=True,
        text=True,
        env=E,
        timeout=120,
        check=True,
    )
    return list(csv.reader(io.StringIO(r.stdout)))


col = {i: n for i, n in q("tukit_identidad", "select id, nombre from colegio")}
rows = q(
    "tukit_catalogo",
    """select l.colegio_id,l.grado,l.anio_lectivo,i.orden,i.texto_original,c.codigo,v.revisada_en,
 coalesce(v.revisada_por::text,''),
 exists(select 1 from correccion_lista k where k.campo='concepto' and k.aprendido->>'retroactivo' is not null and k.texto_original = i.texto_original) ,
 exists(select 1 from correccion_lista k where k.version_id=v.id and k.campo='concepto' and k.aprendido->>'sinonimo' is not null and lower(k.aprendido->>'sinonimo')=lower(i.texto_original)),
 exists(select 1 from correccion_lista k where k.item_id=i.id and k.campo='aviso'),
 exists(select 1 from correccion_lista k where k.version_id=v.id)
 from item_lista_oficial i join version_lista_oficial v on v.id=i.version_id join lista_oficial l on l.id=v.lista_id
 left join concepto c on c.id=i.concepto_id where v.vigente and v.revisada_en is not null order by 1,2,4""",
)
out = Path(__file__).resolve().parent / "datos" / "renglones_etiquetados_v2.csv"
n = 0
with out.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "colegio",
            "grado",
            "anio",
            "orden",
            "texto_original",
            "concepto_codigo",
            "revisada_en",
            "revisada_por",
            "origen_revision",
            "concepto_corregido_por_persona",
        ]
    )
    for cid, g, a, o, t, c, rev, por, cor1, cor2, avi, vcor in rows:
        corr = cor1 == "t" or cor2 == "t"
        if corr:
            org = "concepto_corregido_en_revision"
        elif avi == "t":
            org = "salida_aceptada_aviso_descartado_por_revisor"
        elif vcor == "t":
            org = "salida_aceptada_sin_tocar_en_version_con_correcciones"
        else:
            org = "salida_aceptada_sin_tocar_version_aprobada_sin_correcciones"
        n += corr
        w.writerow([col.get(cid, cid), g, a, o, t, c, rev, por, org, int(corr)])
print(len(rows), "renglones; corregidos", n)
