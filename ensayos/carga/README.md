# Ensayo de carga de solo lectura

`carga.py` mide cuánto aguanta el backend local cuando varios acudientes solo leen.
Resultados de la corrida del 2026-11-02: `resultados/carga_2026-11-02.json`.

## Qué mide y qué no

Lee cuatro endpoints públicos, en rotación y sin pausa entre peticiones:

| Endpoint | Servicio |
|---|---|
| `GET /v1/grados-canonicos` | inteligencia |
| `GET /v1/catalogo/productos?limite=5` | catalogo |
| `GET /v1/catalogo/tiendas` | catalogo |
| `GET /v1/trabajos/{id}` (un trabajo publicado, anónimo) | inteligencia |

No escribe en la base, no usa POST y solo acepta hosts locales (el túnel de
Cloudflare lo usan los participantes del OE5 y el script se niega a tocarlo).

**No cubre todo DP-02.** El criterio de aceptación del SRS habla de un perfil de pico
con carga de lista, generación de kits y checkout, contra el entorno de evaluación con la
pasarela simulada. Este ensayo solo cubre la parte de lectura y un máximo de 20
concurrentes, no los 50 del requisito. Generar kits y pagar escriben en la base, y el
día del OE5 no se hacen. Sirve como línea base de lectura, no como la prueba de aceptación.

## Dos modos, y por qué

- **`capacidad`** va directo a los puertos de los servicios (8012 y 8013). El gateway
  limita a 1.200 peticiones por IP cada 60 s (`servicios/gateway/tukit_gateway/limite.py`),
  unas 20 por segundo. Medir por la puerta mediría el limitador, no al backend.
- **`limite`** va una sola vez por la puerta (8010), 5 usuarios y 15 s, para mostrar que
  el limitador responde 429. Manda `X-Forwarded-For: 203.0.113.77` (rango de documentación,
  RFC 5737). `127.0.0.1` es proxy de confianza del gateway, así que el cupo que se gasta
  es el de esa IP inventada y no el de `127.0.0.1`, que usa la web local.

Un 429 no se cuenta como error: se reporta aparte. Su latencia tampoco entra a los
percentiles, porque responde en microsegundos y haría ver el p50 mejor de lo que es.
Los percentiles son por rango más cercano, sin interpolar. Cada nivel descarta los 3 s
iniciales (conexiones nuevas, cachés frías) y mide 30 s.

## Cómo correrlo

```
# un trabajo publicado y anónimo
psql postgresql://tukit:tukit@127.0.0.1:5432/tukit_inteligencia -Atc \
  "select id from trabajo_pipeline where estado='publicado' and usuario_id is null limit 1"

uv run python ensayos/carga/carga.py --trabajo-id <uuid> --duracion 30 \
  --salida ensayos/carga/resultados/carga_2026-11-02.json
```

`--modo capacidad|limite|todo` y `--niveles 1,5,10,20` ajustan la corrida. Las pruebas
del resumen están en `test_carga.py`.

## Umbrales y de dónde salen

El SRS v6 (`DP-02`, §3.9; texto de reemplazo en `Arquitectura/ENMIENDA_SRS.md`, E-04.a)
fija para el criterio de aceptación:

- 50 usuarios concurrentes activos sobre el perfil de pico diario.
- p95 de las transacciones dentro de los objetivos de §2.4.3.
- Tasa de error menor al 1 %.
- Sin degradación medible del p95 entre el 10 % y el 100 % de la carga objetivo.

`DP-05` (1.000 concurrentes) es un escenario de crecimiento, "no requiere demostración
empírica en v1". Este ensayo no lo intenta.

Sobre el p95: §2.4.3 solo fija un número, `p95 ≤ 8 s` para generar los tres kits.
No hay un umbral de p95 para lecturas, y no se inventó uno. Los percentiles de abajo
se reportan sin veredicto contra un umbral que el SRS no tiene. Lo único que se
compara con el SRS es la tasa de error (< 1 %) y la forma de la curva de p95.

`ENTREGA_FINAL/v_final/ENMIENDA_SRS_v7.md` no menciona DP-02 ni DP-05 (solo DP-03 y
DP-04), así que la fuente de los umbrales es el SRS v6.

## Resultados (2026-11-02)

Máquina: Apple M4, 10 núcleos lógicos, 32 GB, macOS (Darwin 27.0.0). Generador de
carga, servicios, Postgres y el resto del stack comparten esa máquina, y el stack
estaba arriba para el OE5.

Capacidad, directo a los servicios, 30 s por nivel, 4 endpoints en rotación:

| Usuarios | Peticiones/s | p50 ms | p95 ms | p99 ms | Error |
|---|---|---|---|---|---|
| 1 | 170,7 | 3,98 | 14,44 | 17,08 | 0 % |
| 5 | 888,8 | 4,99 | 9,60 | 11,63 | 0 % |
| 10 | 962,1 | 8,96 | 22,48 | 33,08 | 0 % |
| 20 | 890,9 | 18,89 | 48,74 | 71,32 | 0 % |

Lectura honesta:

- Error 0 % en los cuatro niveles, por debajo del 1 % del SRS.
- El rendimiento deja de crecer entre 5 y 10 usuarios (unas 900 a 960 peticiones/s) y
  desde ahí la latencia sube casi en proporción a los usuarios: es saturación, no
  escalado. Con el generador en la misma máquina no se puede separar cuánto es
  techo del backend y cuánto es el propio generador.
- El p95 pasa de 9,6 ms (5 usuarios) a 48,7 ms (20). El requisito de "sin degradación
  medible del p95 entre el 10 % y el 100 % de la carga" no se cumple en esta forma de medir,
  que además no llega a 50 usuarios. Es un hallazgo a tener presente, no un resultado verde.
- El nivel de 1 usuario tiene un p95 más alto que el de 5. Con una sola conexión y
  muestras de pocos milisegundos pesan los picos aislados; no se interpretó más.
- Latencias por endpoint en el JSON (`por_endpoint`): el listado de productos es el más
  lento (p50 de 8 a 27 ms según el nivel).

Límite de tasa, por la puerta, 5 usuarios, 15 s, una IP simulada:

| 2xx | 429 | Otros errores |
|---|---|---|
| 1.200 | 30.257 | 0 |

Las 1.200 respuestas 2xx son exactamente el cupo por IP del nivel general (1.200 cada
60 s). Los 429 son el limitador funcionando, no fallas del backend.
