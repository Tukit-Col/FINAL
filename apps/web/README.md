# apps/web — la aplicacion del acudiente

Next.js 16 (App Router, CSS Modules). Viene de `tukit-mvp-front`, que se trajo
al monorepo con su historia: los tres commits del prototipo estan en este
repositorio bajo la referencia `mvp-front/main`.

## Levantarla

Desde la raiz del monorepo:

```bash
npm install
npm run dev:web        # http://localhost:3000
```

`apps/admin` corre aparte, en el 3001:

```bash
npm run dev:admin
```

## El origen de datos

Toda la app lee los datos a traves de `origenDeDatos()`, en
`libs/ts/tukit-contrato/src/servidor.ts`. Siempre habla con el backend real: los
7 microservicios a traves del gateway. Solo hay que decirle donde esta:

```bash
TUKIT_API_URL=http://localhost:8010 npm run dev:web
```

`TUKIT_API_URL` es obligatoria: si falta, la app falla de entrada a proposito
(no hay valor por defecto silencioso — apuntar a un puerto equivocado sin avisar
fue justo el bug que se arrastro). En local el gateway es `:8010` (`make
arriba`). Las pantallas no consultan la URL nunca: piden el origen y lo usan.

Copia `.env.ejemplo` a `.env.local` para fijarla.

## La UI no tapa los huecos del catalogo

La pantalla de kits muestra huecos de catalogo y lineas que no se pueden cobrar,
porque el catalogo real los tiene: hay conceptos sin ni un producto, y las
listas reales traen licencias digitales, textos de edicion exclusiva y
uniformes. Taparlos aqui haria que la UI se viera mejor de lo que el sistema
esta.

## Pantallas

| Ruta | Que es |
|---|---|
| `/` | Portada. Abre por el dolor declarado en la encuesta, no por el precio |
| `/empezar` | Las dos entradas del §2: colegio y grado, o archivo. Contacto y preferencias |
| `/esperando/[trabajo_id]` | La espera honesta: las cuatro etapas y la pausa humana |
| `/kits/[trabajo_id]` | Los tres kits, con uno marcado y los otros dos a la vista |
| `/catalogo` | Que hay hoy: conceptos, productos por nivel, personaje y precio por tienda |
| `/dashboard` | Cuenta del acudiente: saludo (sesion de identidad) y pedidos reales (`/v1/comercio/mis-pedidos`) |

## Lo que NO esta

El pago (`comercio`, §9 del contrato). El boton existe y esta apagado con la
razon escrita al lado, porque un boton que no hace nada es peor que uno
apagado que dice por que.
