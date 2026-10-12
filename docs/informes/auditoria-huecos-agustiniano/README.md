# Auditorías de huecos del Agustiniano

Las auditorías renglón por renglón de las listas 2026 del Colegio Agustiniano Ciudad Salitre (Jardín a
Once) y de sus kits canónicos Ahorrador y Premium, en el orden en que se hicieron. Cada una se hizo
sobre un commit distinto, con bases aisladas cargadas desde `datos/` de ese commit. Una versión no
reemplaza a la anterior: juntas muestran cómo evolucionó el sistema. La última es la vigente.

| Versión | Commit auditado | Renglones | Cumplen (de los comprables) | HUECO_CATALOGO | Kits A / P (13 grados) | Qué cambió antes de esta |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| [v1](v1-a565aeb.md) | `a565aeb` | 1.092 | 263 | 240 | $13.864.663 / $32.031.940 | Primera auditoría: 13 listas revisadas y exportadas |
| [v2](v2-d4ea7cb.md) | `d4ea7cb` | 1.092 | 465 de 888 (52,4 %) | 385 | $9.857.452 / $17.602.526 | Atributos del catálogo, filtro por renglón, curaduría de Séptimo, juntar herramientas |
| [v3](v3-02d8f24.md) | `02d8f24` | 1.098 | 617 de 886 (69,6 %) | 220 | $8.959.420 / $14.159.658 | [Afinamiento del Agustiniano](../../diseno/planes/2026-10-11-afinar-kits-agustiniano.md) y [ADR 0040](../../arquitectura/adr/0040-como-se-compara-cada-atributo.md) |

Las tres usan las mismas categorías: A (hueco real), B (falso hueco), C (mal elegido) y D. A, B y C
hablan del catálogo y del armador; D, del alcance del negocio. Desde v3, D se llama «Fuera del
surtido de Tukit»: uniformes, licencias, lo que se trae de casa o entrega el colegio, lo que Tukit
decidió no vender y los textos con título. En v1 y v2 se llamaba «No es hueco»; es la misma
categoría con otro nombre. Cada una trae una sección que la compara con la anterior: v2 §8 frente a v1, y v3 §8 frente
a v2.

- v1 se llamaba `nuevo-reporte-huecos-agustiniano-viejo.md`, y v2, `nuevo-reporte-huecos-agustiniano.md`.
  Se movieron aquí sin cambiar su contenido, así que los enlaces y rutas que citan dentro siguen
  siendo los de su fecha.
- El ADR 0040, el plan del afinamiento, la [lista del scraper](../surtido-huecos-agustiniano.md) y
  las pruebas de `ensayos/test_kits_offline.py` citan la v2, que fue su origen.
- v2 cuenta como OK tres líneas informativas de Séptimo (`7#9`, `7#27`, `7#69`), y v3 las cuenta como D.
