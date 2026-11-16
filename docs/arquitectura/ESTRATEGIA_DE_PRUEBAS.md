# Estrategia de pruebas

## Dónde va cada prueba

- Python: `servicios/<servicio>/tests/`, `libs/py/tukit_comun/tests/`, `ensayos/` y `arquitectura/`.
- TypeScript: `apps/web/test`, `apps/admin/test` y `libs/ts/tukit-contrato/test`.
- Un archivo por módulo o por comportamiento (`test_checkout_pago.py`, `test_limite_ip_cliente.py`),
  nunca por el cambio que lo originó (`*_resiliente`, `*_cola`, `*_lote`).
- Los nombres de archivo de prueba son únicos en todo el repo: pytest los importa por nombre base
  y un duplicado rompe la recolección.
- Ayudas compartidas dentro de un servicio: `_ayudas_<servicio>.py` o `conftest.py`. Una prueba
  no importa de otra.

## Cómo se nombran

Una prueba nombra un comportamiento ("una orden idéntica reutiliza el pendiente"), no una historia
("ya no", "como siempre", "nuevo"). Si el nombre solo tiene sentido para quien hizo el cambio, está mal.

## Qué se inyecta y qué no

Los dobles entran por la frontera pública (parámetro, `app.state`, `usar_llamador`). Parchear con
`monkeypatch.setattr` un `_privado` se acepta solo cuando no hay costura razonable, y queda comentado.
Las constantes de negocio se importan del código o se comparan con `approx`; los literales que son contrato
(plazos, topes de la web) llevan comentario.

## Cómo correrlas

| Nivel | Comando |
| --- | --- |
| Fronteras entre servicios | `make fronteras` |
| Toda la suite Python | `make prueba` |
| Un servicio | `.venv/bin/python -m pytest servicios/<servicio>` |
| TypeScript | `npm test` (contrato, web y admin), más `npm run typecheck` y `npm run lint` |
| Colas y Redis | `make prueba-colas`, `make prueba-redis` |

Corre solo las pruebas de lo que cambió; la suite completa, una vez antes de integrar.
