# ADR 0037 — La curaduría de listas y del catálogo viaja por git como CSV

- **Estado:** aceptada
- **Fecha:** 2026-10-04
- **Servicios tocados:** `catalogo`, `identidad` (exportar e importar), raíz (`Makefile`, `tukit.ps1`)

## Contexto

Curar una lista, es decir, decidir a qué concepto corresponde cada renglón y aprobarla en la
cola, deja el resultado en la base local de quien cura. Lo mismo pasa con los conceptos que crea
y con los productos que aprueba. Cada integrante del equipo tiene su propia base en Docker, así
que lo curado en una máquina no existía en las otras y cada uno habría tenido que repetir el
trabajo, o volver a pagar la lectura de las listas con Gemini.

El catálogo ya se cargaba desde CSV versionados (`datos/catalogo/`) con `bd-cargar`, y esos CSV
tienen pruebas de calidad que la tesis cita (`test_catalogo_curado`: un representante por celda,
EAN válido, escalera de precios por nivel).

## Decisión

La curaduría se **exporta a CSV versionados** y se **importa** desde ellos:

- `datos/curaduria/listas_revisadas.csv`: la última versión revisada de cada lista, con el
  concepto por **código**, nunca por id de base.
- `datos/curaduria/colegios.csv` y `sedes.csv`: los colegios que esas listas nombran, sin datos
  de contacto. Los escribe `identidad`, que es su dueño.
- `datos/catalogo/conceptos.csv`: se fusionan los conceptos creados y los sinónimos editados.
- `datos/catalogo/productos_*.csv`: los productos aprobados y sus atributos editados a mano.

`exportar` encadena `representantes → volcar → nivelar → cargador`, de modo que lo exportado
cumple las mismas pruebas que el catálogo semilla. `importar` corre `bd-cargar` primero, porque una
lista no entra sin sus conceptos, y es idempotente: una lista que ya dice lo mismo no crea otra
versión.

Cada servicio exporta e importa solo sus tablas. Ninguno lee la base de otro, como exige el
manifiesto.

## Alternativas rechazadas

- **Un volcado de la base (`pg_dump`).** Arrastra datos de prueba, pedidos y contactos, choca con
  las migraciones de cada máquina y no se puede revisar en un diff.
- **Una base compartida en la nube.** Agrega infraestructura y un punto de falla a un proyecto que
  hoy corre completo en cada portátil, y no deja historia de quién cambió qué.
- **Exportar solo las listas.** Una lista apunta a conceptos y productos por código: sin ellos, al
  importarla quedaría huérfana.

## Consecuencias

- El historial de git dice cuándo cambió cada sinónimo y cada lista curada.
- Los vectores semánticos no viajan, porque cuestan cupo de Gemini Embedding. Se recalculan con
  `make bd-enriquecer`; sin ellos el emparejamiento funciona solo por palabras.
- Los códigos `C1NN` se asignan en cada base: dos personas creando conceptos a la vez chocarían.
  Hoy cura una sola persona. Si eso cambia, el código tiene que salir de un lugar común.
- Hay que exportar **antes** de `git pull`: `bd-cargar` reescribe los conceptos desde el CSV.
