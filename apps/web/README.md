# apps/web — la aplicacion del acudiente

Next.js 16 (App Router, CSS Modules).

## Levantarla

Desde la raiz del monorepo:

```bash
npm install
npm run dev:web        # http://localhost:3000
npm run dev:admin      # el back-office, aparte, en http://localhost:3001
```

## El origen de datos

Toda la app lee los datos a traves de `origenDeDatos()`, en
`libs/ts/tukit-contrato/src/servidor.ts`, y siempre habla con el backend real a traves
del gateway. Solo hay que decirle donde esta:

```bash
TUKIT_API_URL=http://localhost:8010 npm run dev:web
```

`TUKIT_API_URL` es obligatoria: si falta, la app falla de entrada a proposito, para no
apuntar a un puerto equivocado sin avisar. En local el gateway es `:8010` (`make arriba`).
Copia `.env.ejemplo` a `.env.local` para fijarla.

## La UI no tapa los huecos del catalogo

La pantalla de kits muestra huecos de catalogo y lineas que no se pueden cobrar, porque el
catalogo real los tiene: hay conceptos sin ni un producto, y las listas traen licencias
digitales, textos de edicion exclusiva y uniformes. Taparlos haria que la UI se viera mejor de
lo que el sistema esta.

## Pantallas

| Ruta | Que es |
|---|---|
| `/` | Portada |
| `/empezar` | Las dos entradas: colegio y grado, o archivo. Contacto y preferencias |
| `/esperando/[trabajo_id]` | La espera: las etapas del pipeline y la pausa humana |
| `/kits/[trabajo_id]` | Los kits (Ahorrador y Premium; Fan y A tu Medida si se pidieron), con uno marcado. Cada producto se puede cambiar por una de sus alternativas |
| `/catalogo` | Que hay hoy: conceptos, productos por nivel, personaje y precio por tienda |
| `/dashboard` | Cuenta del acudiente: hijos, solicitudes y pedidos. Un hijo se cambia de colegio o se quita; una solicitud se cancela si el kit no se compro; un pedido pendiente se paga o se cancela ahi mismo |
| `/pago/resultado` | La vuelta del pago: confirma con el servidor y muestra aprobado, rechazado o "estamos confirmando" |
| `/pago/simulado` | La pasarela simulada para `WOMPI_MODO=falso`: aprueba sola (`?resultado=rechazado` fuerza el rechazo), sin red |

## Lo que no esta

El pago en produccion. Hay pago con Wompi, pero solo en modo de pruebas: el widget se abre con
llaves `pub_test_` y Comercio no arranca con otras.

El seguimiento del envio: el pedido sabe si esta pagado, en preparacion o entregado, pero
nadie llena transportadora, guia ni fecha estimada.

## El pago, en dos lugares

- `src/lib/wompi.ts` abre el widget de Wompi siempre con `bootstrapTransport: "postmessage"`.
  Por omision el widget mete su configuracion en la URL del iframe, y el CDN de Wompi responde
  403 si ahi va un retorno a `localhost`.
- `src/lib/pagar-pedido.ts` tiene las reglas de "Mis pedidos": quien puede pagar o cancelar,
  cuando vence un pedido, que color lleva cada estado y si una solicitud ya se compro. Comercio
  aplica las mismas y es quien manda; aqui se repiten para pintar el boton correcto.

## Pruebas

```bash
npm test --workspace @tukit/web   # node --test, sin dependencias
```

Usa el runner nativo de Node sobre TypeScript, como `libs/ts/tukit-contrato`. Prueba funciones
puras de `src/lib`; los componentes no tienen pruebas. `tsconfig.json` deja `test/` fuera del
chequeo de tipos porque las pruebas importan con extension `.ts`.
