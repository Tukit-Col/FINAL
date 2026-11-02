# Runbook: dejar Tukit listo para una sesión con acudientes

Repo: `~/Documents/university/TUKIT/tukit`, rama `validacion/oe5`. Todo corre en el portátil; solo la web sale a internet, por el túnel.

## Arranque (una vez por jornada, unos 3 min)
```sh
cd ~/Documents/university/TUKIT/tukit
brew services start postgresql@16 redis rabbitmq     # ya quedan como servicio
nc -z 127.0.0.1 5672 && echo rabbit-ok               # esperar a que el puerto abra antes de arrancar
set -a; . ./.env; set +a                             # GEMINI_API_KEY y demás (el Makefile no lee .env)
export WOMPI_MODO=falso; unset TUKIT_AUTOPUBLICAR     # pago simulado; nunca autopublicar
make arriba                                          # debe decir "RabbitMQ responde" y "Redis responde"
make estado                                          # todos_arriba: true
```
Si `make arriba` dice que RabbitMQ no responde, el broker todavía estaba arrancando: `make abajo` y repetir.

## Web y admin
```sh
# Web del acudiente: build de producción, solo en localhost
cd apps/web && TUKIT_API_URL=http://127.0.0.1:8010 npm run build
TUKIT_API_URL=http://127.0.0.1:8010 npx next start -H 127.0.0.1 --port 3000

# Admin (cola de revisión), solo para la moderadora, nunca por el túnel
cd apps/admin && TUKIT_API_URL=http://127.0.0.1:8010 npm run dev          # http://localhost:3001/cola
```
- Entrar al admin con `operador@tukit.co`. La clave **ya no es `demo1234`**: está en el Llavero (`security find-generic-password -s tukit-staff-oe5 -w`).
- **No correr `make bd-reiniciar-datos`** durante las jornadas: vuelve a poner `demo1234` y borra las cuentas de prueba.

## Túnel (Cloudflare, sin cuenta)
```sh
caffeinate -dims &                                   # que el portátil no se duerma
cloudflared tunnel --url http://127.0.0.1:3000       # imprime https://<algo>.trycloudflare.com
```
- La URL cambia cada vez que se reinicia el túnel: se manda al acudiente justo antes de su sesión, por privado, nunca en el grupo.
- Con el túnel abierto, reiniciar el backend con `export TUKIT_WEB_URL=https://<algo>.trycloudflare.com` para que los enlaces de los avisos apunten bien.
- Al terminar la jornada: `Ctrl+C` en el túnel. Sin túnel, nada queda expuesto.

## Checklist de seguridad (verificado el 28-oct)
| Revisión | Estado |
|---|---|
| Solo la web sale por el túnel; gateway, servicios, Postgres, Redis y RabbitMQ en 127.0.0.1 | OK (`lsof -nP -iTCP -sTCP:LISTEN`) |
| Consola de RabbitMQ, distribución y epmd solo en localhost; plugins STOMP, MQTT y streams apagados | OK (`/opt/homebrew/etc/rabbitmq/rabbitmq.conf`) |
| `/api/*` de la web no es un proxy abierto; rutas internas y de admin dan 404 | OK |
| Pagar un kit ajeno → 403 `solicitud_ajena` | OK (arreglo `58b9742`) |
| Subidas con tope de 10 MB por archivo y solo PDF, JPG, PNG y WEBP | OK (arreglo `0e3063b`) |
| Cookie de sesión `httpOnly`, `Secure`, `SameSite=Lax` | OK |
| Límite de tasa con Redis en la puerta (login 30 por token y 60 por IP cada 10 min) | OK |
| Claves del staff rotadas | OK |
| Llaves en el bundle del navegador | OK: ninguna lectura en componentes de cliente, y `rg -l 'GEMINI\|WOMPI_LLAVE_PRIVADA\|TUKIT_LLAVE_CIFRADO' apps/web/.next/static` sale vacío (exit 1). Repetirlo después de cada `npm run build` |
| Cuenta de invitado (`sin-credencial`) tomable por quien se registre primero | ABIERTO; se neutraliza porque cada acudiente se registra en T1 |

## Si algo falla en plena sesión
- Un kit se queda en "Estamos armando tu kit": está en revisión. Aprobarlo en `/cola` (o el trabajo en `/trabajos/[id]`).
- La subida de PDF dice `lista_de_varios_grados`: es lo esperado con un PDF del colegio entero. Pedir la foto o la página del grado.
- Un proceso de fondo murió: `make estado`; si algo no está, `make abajo && make arriba` (las colas y bandejas no pierden mensajes).
- El túnel se cayó: volver a abrirlo y mandar la URL nueva.
