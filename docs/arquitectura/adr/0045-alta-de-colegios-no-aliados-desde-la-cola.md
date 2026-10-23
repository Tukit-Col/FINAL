# ADR 0045 — El staff sube desde la cola la lista de cualquier colegio de Bogotá, con un solo directorio y una regla de logo

- **Estado:** aceptada
- **Fecha:** 2026-10-10
- **Servicios tocados:** `inteligencia` (`POST /v1/admin/onboarding`), `catalogo` e `identidad` (sin cambios de API), `@tukit/contrato` (directorio y búsqueda), `apps/admin` (`/cola`, `/colegios`), `apps/web` (`/empezar`)

## Contexto

El onboarding de `/cola` exigía un `colegio_id`: solo se podía subir la lista de un colegio que
Tukit ya tenía. Para sumar un colegio nuevo, el staff tenía que esperar a que un acudiente lo
eligiera en `/empezar`. Ese camino sí sabía crear colegios del directorio o escritos a mano: los
datos viajaban en `colegio_datos` y se creaban al aprobar la lista.

Además, el directorio de colegios de Bogotá vivía como archivo estático en `apps/web/public`. El
admin no lo tenía, y no traía logos. Los colegios sin `logo_url` en `identidad`, que son casi
todos, se veían con iniciales en todas partes.

## Decisión

1. **El onboarding designa el colegio igual que el acudiente.** `POST /v1/admin/onboarding`
   acepta `colegio_id`, `colegio_dane` + `colegio_nombre`, o solo `colegio_nombre`. Usa la misma
   regla, extraída a `ColegioElegido.resolver_colegio()`: el id se deriva del DANE o del nombre
   normalizado, y `colegio_datos` se completa con el directorio de `identidad`. Con solo
   `colegio_id`, todo es igual que antes. Sin colegio, `422 colegio_requerido` antes de leer el
   archivo.
2. **El colegio nace al aprobar la lista, no al subirla.** La cola muestra su nombre y la
   revisión ofrece completarlo (`CompletarColegio`). Borrar la versión no deja un colegio
   huérfano en `identidad`. No hay tablas nuevas ni un endpoint de alta aparte.
3. **Una sola copia del directorio, en el contrato.**
   `@tukit/contrato/directorio-colegios.json` (`dane`, `nombre`, `localidad`, `imageURL`). Cada
   app lo sirve estático en `/directorio-colegios.json` para buscar en el navegador, y las
   páginas de servidor lo importan. `identidad` lo regenera y conserva cada `imageURL`. La
   búsqueda es una función pura del contrato (`buscarColegios`), la misma en `/empezar` y en
   `/cola`.
4. **Un DANE que ya es de un colegio se reconduce a ese colegio.** Elegir del directorio un
   colegio que Tukit ya tiene (por ejemplo, el Agustiniano Ciudad Salitre, que en la base se
   llama "Colegio CACS") manda su `colegio_id`. Así no se crea un duplicado. Se hace en el
   buscador y otra vez en la ruta del admin.
5. **La regla del logo.** Primero el `logo_url` de `identidad`; si no hay, el `imageURL` del
   directorio con el mismo DANE; si tampoco, las iniciales. Un logo que no carga cae a las
   iniciales en el navegador. Solo se ponen URLs del sitio oficial del colegio, verificadas, y
   nunca de redes sociales (fbcdn).

## Alternativas rechazadas

- **Un endpoint para crear el colegio en `identidad` antes de subir la lista.** Deja colegios
  sin lista cuando el staff se arrepiente. Además duplica lo que el poller de `identidad` ya
  hace al aprobar.
- **Copiar el directorio en `apps/admin/public`.** Dos copias que se desincronizan al
  regenerar. Importarlo de una app a otra rompe las fronteras (`make fronteras`).
- **Guardar el logo del directorio en `identidad.colegio.logo_url`.** Mezcla un dato curado del
  colegio aliado con uno de referencia, y obliga a una migración de datos por cada logo nuevo.
- **Descargar los logos a `public/`.** Los colegios los cambian, y la copia queda vieja sin que
  nadie lo note.

## Consecuencias

- El staff puede sumar un colegio a Tukit subiendo una lista. Hasta que la aprueba, el colegio
  solo existe en la cola.
- Subir una lista crea colegios, así que el onboarding exige sesión de staff: `inteligencia`
  llama a `_exigir_staff` antes de leer el archivo, y el BFF del admin reenvía el token de la
  sesión como Bearer (contrato 1.8, §12.8).
- Un logo nuevo se agrega editando `imageURL` en el JSON del contrato. Regenerar el directorio
  no lo pierde.
- El JSON pesa lo mismo que antes, más una clave por entrada. El navegador lo descarga una vez
  por página, cuando se usa el buscador.
