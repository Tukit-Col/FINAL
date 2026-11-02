# Contraste: app en `feature/colas-rabbitmq` frente a la doc final (28 de octubre de 2026)

**Doc:** `Tukit_revision (1) 2.zip` (salida/ENTREGA_FINAL, versión del 13-oct, la que tiene Gordis).
**App:** `validacion/oe5` = `origin/feature/colas-rabbitmq` (2c251fb, 26-oct) más 4 commits de esta revisión. Base local recreada desde cero, Redis 8.10 y RabbitMQ 4.4 activos, `WOMPI_MODO=falso`.

La doc no se toca aquí. Abajo va lo que conviene corregir en ella.

## Lo que la app hace distinto de lo que dice la doc
| Tema | Dice la doc | Hace la app (verificado hoy) | Qué ajustar en la doc |
|---|---|---|---|
| Cambiar un producto del kit | El acudiente ve alternativas pero no puede cambiarlas; la variante existe solo en una rama del 4-oct (`desarrolloSolucion.tex`, `resultados.tex`) | "Cambiar por otra opción" funciona: elegí una Biblia alternativa y el total subió $29.777 exactos ($840.336 → $870.113); el pedido se cobró con ese total | Pasar UI-03 (cambio de ítem) a implementado y quitar la frase de la rama no integrada |
| Número de kits | Tres kits: Ahorrador, Fan, Premium (UI-02, QA-U5) | Hasta cuatro: Ahorrador, Fan, A tu Medida, Premium | Decir "tres perfiles más «A tu Medida»" o ajustar UI-02 y QA-U5 |
| Redis | "Reservado para caché y límite de tasa en producción"; no verificado en el despliegue, la puerta no limita la tasa (SAD ~921, PEN-50) | Activo: caché de lecturas y límite de tasa en la puerta (30 por token y 60 por IP cada 10 min en `/v1/sesiones`). `make prueba-redis`: 11 de 11 | Cerrar PEN-50 y describir el límite |
| RabbitMQ | "El envío ocurre solo si el broker está configurado" (SAD ~918) | Broker activo con 4 colas y sus consumidores (`identidad.colegios`, `inteligencia.listas`, `inteligencia.trabajos`, `operacion.avisos`) y 3 publicadores. `make prueba-colas`: 6 de 6 | Pasar de "opcional" a "en uso", con fallback a sondeo de bandejas si no responde |
| Resiliencia del broker | Sin medir (ATAM, PEN-63) | Reinicié RabbitMQ con todo corriendo: los 4 consumidores se reconectaron solos, las colas quedaron en 0 y los 14 procesos siguieron vivos | Evidencia parcial para el escenario de resiliencia; falta medir el tiempo de recuperación |
| Lista en PDF | Mediana de 312,46 s por documento frente al tope de 300 s de la puerta (PEN-40) | La subida responde 202 en unos 5 s y la percepción corre diferida. Un PDF de 12 grados se rechaza en 55 s con `lista_de_varios_grados`, nombrando los grados y pidiendo solo las páginas del hijo. Una página sola (Primero, Bahía Solano) dio 34 renglones | Actualizar PEN-40: la espera ya no bloquea la petición. Agregar el rechazo de listas de varios grados |
| Seguimiento del pedido | Estados de entrega, rutas fuera de alcance (PEN-27) | `/pedidos/[id]` muestra una línea de 5 pasos: creado, pago confirmado, en preparación, despachado, en reparto. Transportadora y guía siguen vacías | Decir que el seguimiento es visible y que el avance es manual (admin) |
| Cierre de sesión | Solo en el cliente (PEN-15) | En el código, cerrar sesión revoca el token (commit `fd01e78`). **No lo probé en vivo** | Verificar y cerrar PEN-15 |
| Revisión humana | "Lo está revisando una persona" cuando la lista espera revisión | Todo kit «A tu Medida» (opción por defecto "Un punto medio") pasa por la cola. Solo "económico" y "estirarse" con kit canónico saltan directo. Al aprobar una lista subida, el kit del acudiente se arma y publica solo | Explicar qué caminos esperan a una persona |

## Lo que sigue igual que en la doc (no se evalúa con padres)
- Panel de privacidad y supresión de datos: no existe (SRS 3.14, PEN-08).
- Portal del colegio: aviso "en construcción".
- WhatsApp: solo el enlace `wa.me`. Correo: sin SMTP, el aviso se imprime en la consola del repartidor (`kits_publicados` y `pedido_pagado` quedaron `enviada` en `notificacion`).
- Pago real: Wompi sandbox no se probó; se usa la pasarela simulada.
- Pesos por omisión del recomendador distintos del SRS (PEN-29): no revisado hoy.

## Arreglos de esta revisión (rama `validacion/oe5`, commits locales)
| Commit | Qué |
|---|---|
| `d1d3660` | **Bug:** en una base desde cero (migrar, sembrar, curaduría) `sembrar_acceso` fallaba por la FK del colegio piloto y no creaba ni operador ni admin: la cola quedaba sin quien aprobara y `make humo` daba 401 |
| `58b9742` | **Seguridad:** con el id de un kit ajeno se podía armar orden y pago a nombre de otro acudiente. Ahora 403 `solicitud_ajena`. Probado en vivo y con prueba nueva |
| `0e3063b` | **Seguridad:** las subidas se cortan por tamaño (413) y tipo (415) antes de leerlas; la sugerencia entra al límite estricto de la puerta |
| `300583d` | **Textos:** la portada decía que el pago estaba "Próximamente" y la ayuda, que el botón de pagar estaba apagado |

## Riesgos de seguridad que quedan abiertos (para la memoria y PENDIENTES)
- **Cuenta de invitado.** Quien paga sin cuenta queda como `sin-credencial`, y el primero que se registre con ese correo le pone clave y ve sus pedidos. Cerrarlo exige verificar el correo, y no hay recuperación de contraseña (PEN-20). En las sesiones se neutraliza porque cada acudiente se registra antes de pagar.
- `GET /v1/trabajos/{id}` no revisa dueño: con el id se ve el kit (no los datos del acudiente).
- `/api/casos` permite abrir un caso con el correo de otro.
- Los errores del backend llegan al navegador con detalle interno (URLs de la puerta).
- Los datos personales del acudiente se guardan en claro (PEN-05): no revisado hoy.

## Pruebas corridas hoy
- Suite completa: 75 de fronteras (1 omitida) y 2.272 de servicios, 0 fallos. Web: 60 de 60 más 2 nuevas. Puerta: 71 de 71.
- `make humo`: 20 comprobaciones con datos reales. `make prueba-colas` 6/6, `make prueba-redis` 11/11.
- E2E por las dos vías de UI-01 (colegio y grado; PDF), en la build de producción, hasta pedido pagado y aviso enviado.
- Puertos: los 6 servicios, Postgres, Redis, RabbitMQ (con su consola) y la web escuchan solo en 127.0.0.1.
