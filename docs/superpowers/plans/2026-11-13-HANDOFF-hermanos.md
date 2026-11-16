# Handoff: arreglos entre hermanos (13-nov-2026)

**Siguiente paso:** ejecutar `docs/superpowers/plans/2026-11-13-hermanos-fan-correo.md`, **en la sesión, sin subagentes** (lo decidió el usuario). Se usa `superpowers:executing-plans`, tarea por tarea con TDD y un commit por tarea, y al final un revisor sobre toda la rama (`skeptic-reviewer`, Opus).

## Dónde estamos
- **Repo y rama:** repo `tukit/`, rama `mejoras/datos-multihijo`, sin push ni merge (el usuario dijo "Aún no").
- **Últimos commits de hoy:**
  - `74f8149`: correos por fase del pedido.
  - `fcdc99c`: empezar con correo ya registrado y barra de pasos fija.
- **Sin commit:** quedan cambios en `servicios/inteligencia/tests/test_descartar_y_opciones.py` y en `docs/validacion/oe5/.../CHECKLIST_LLAMADAS_HOY.md`, que vienen de otra tarea anterior. No los commitees sin revisar qué son. Los `AGENTS.md` los reescribe `next dev`, así que ignóralos.
- **Servicios:** backend con `make reanudar`. La web (:3000) y el admin (:3001) los corre el usuario con `npm run dev`.

## El plan, en una línea por tarea (caso real `febe34cf-3511-4ca7-b28e-cf11ca07d13d`)
1. **Anclas de personaje con varias variantes por hijo.** Hoy `producto_de_personaje` trae 1 por (concepto, personaje). El único cuaderno Spiderman es multimaterias y la lista pide 1 materia. Se pasa a una lista y se elige por `puntaje_de_encaje`. Cuando nada encaja, se registra en `personaje_sin_encaje`.
2. **NL2C de variedad (`nl2c_lote.elegir_variante`).** Que no traiga personajes que el hijo no pidió (hoy trae Bluey, Stitch o Toy Story) y que prefiera opciones con foto.
3. **Web.** La franja Fan va por hijo y solo con los personajes pedidos (`productosDelPersonaje(lineas, pedidos)`), con una nota cuando un ancla no encaja. "Lo que juntamos" muestra `explicacion` y el grado de cada hijo.
4. **Correo `kits_publicados`.** La carga lleva `listas` de todos los hijos (hoy solo `hijos[0]`), y `lugares_de` arma "Colegio X, grados Séptimo y Jardín". Los eventos viejos sin `listas` deben seguir funcionando.

Ojo: Spiderman no va a salir en cuadernos mientras el catálogo no tenga un C001 Spiderman cosido de 1 materia. Eso es curaduría del catálogo y no se arregla con código.

## Hecho hoy (ya verificado)
- **Correos (operación, notificador):**
  - 9 plantillas, una por fase del dashboard, más incidencia, cancelación con o sin reembolso, retoma y caso.
  - Barra de fases segmentada, logo adjunto por CID (`tukit_operacion/recursos/logo.png`) y pie legal con BAJA, Ley 1581 y `List-Unsubscribe`.
  - Sin "Turno". El código del pedido es `pedido_id[:8]` y el botón lleva a `/pedidos/<id>`.
  - Comercio emite `pedido_en_preparacion` (con `retoma`) y `pedido_cancelado` (con `reembolso`). Ambos están agregados a `topologia.py`.
  - El usuario aprobó el diseño ("muchísimo mejor").
- **`Makefile`:** hace `-include .env` y exporta solo las variables SMTP/Wompi definidas. Una variable vacía tumba comercio (`WOMPI_MODO=''`).
- **SMTP Gmail (tukit.ayuda) funcionando.** El script de prueba es `/tmp/enviar_plantillas.py` con `/tmp/probar.mk` (`make -s -f /tmp/probar.mk probar-correo`). Está en `/tmp`, así que puede desaparecer.
- **Registro en `/empezar`.** Si el correo ya existe con otra clave, responde 409 `correo_ya_registrado` y el formulario pasa a "ya tengo cuenta". Antes esto dejaba una solicitud huérfana sin dueño y sin correo. La espera ahora lleva al panel, y la barra de pasos es sticky (`top: 76px`, ajustado a ojo).
- **Limpieza de datos.** Borré las cuentas @example.test, .org, ejemplo.com, prueba.tukit.co y y.co con todos sus datos, la solicitud huérfana y la cuenta crackmaps. El respaldo está en `.ejecucion/respaldos/*-2026-11-13.dump`.

## Pendientes fuera del plan
- **Wompi sandbox.** Faltan las 4 llaves que tiene que mandar Gabo (`WOMPI_LLAVE_PUBLICA/PRIVADA`, `WOMPI_SECRETO_EVENTOS/INTEGRIDAD`) y `WOMPI_MODO=sandbox` en `.env`. Para el webhook hace falta un túnel; si no, se usa "Reconciliar con Wompi" en el admin.
- **`TUKIT_PUBLIC_URL`** no está definido, así que los enlaces de los correos apuntan a `localhost:3000`.
- **196 solicitudes publicadas sin dueño** (hay otras 19 que sí sostienen kits canónicos). El usuario no ha decidido si se borran.
- **Bajas por correo.** "Responde BAJA" es manual y no hay lista de exclusión. El texto legal no lo ha revisado un abogado.
- **Fase 5** (asistente por lotes) y lo que dejó abierto la ronda anterior: `estado_desde`, el 429 en la web, los huecos de los guardrails y la reimportación de diccionarios.

## Gotchas de esta sesión
- **`psql` local:** se cuelga por GSSAPI. Hay que usar `PGGSSENCMODE=disable PGPASSWORD=tukit psql -h 127.0.0.1 -U tukit -d <base>`.
- **Permisos de lectura:** están bloqueados `.env` y `.ejecucion/*.log`. Para ver por qué un servicio no arranca, levántalo en primer plano con un puerto aparte, por ejemplo `make api-comercio PUERTO_COMERCIO=8094`.
- **Tests:** se corren por servicio (`.venv/bin/python -m pytest servicios/<svc>/tests -q`). Juntos chocan sus `conftest`.
