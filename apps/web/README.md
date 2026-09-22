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

## La bandera

Toda la app lee los datos a traves de `origenDeDatos()`, en
`libs/ts/tukit-contrato/src/servidor.ts`. Una variable decide cual de las dos
implementaciones se usa:

```bash
TUKIT_ORIGEN_DATOS=simulado   # por defecto
TUKIT_ORIGEN_DATOS=api TUKIT_API_URL=http://localhost:8080 npm run dev:web
```

Las pantallas no consultan la bandera nunca: piden el origen y lo usan. El dia
que el backend responda no hay que tocar ninguna. La cinta de arriba de la
pantalla dice en cual de los dos modos esta, porque una pantalla que se ve
completa con datos simulados y no lo dice es la forma mas barata de creer que
algo esta listo cuando no lo esta.

Copia `.env.ejemplo` a `.env.local` para ajustar los tiempos del simulado.

## Los datos simulados no son inventados

Salen de los mismos ficheros que carga la base:

- `datos/catalogo/*.csv` — los 99 conceptos, 242 productos canonicos, 3 tiendas
  y sus precios vigentes del catalogo curado.
- `Arquitectura/Corpus_ItemLista_v2.csv` — las 4.719 lineas de lista de los 17
  colegios del corpus, con su `tipo_item` y su `modo_adquisicion`.

Los convierte a JSON `libs/ts/tukit-contrato/herramientas/generar_semillas.py`,
que se ejecuta a mano y cuya salida se versiona:

```bash
npm run semillas --workspace @tukit/contrato
```

Por eso la pantalla de kits muestra huecos de catalogo y lineas que no se
pueden cobrar: el catalogo real tiene 17 conceptos sin ni un producto, y las
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
| `/dashboard` | Pantalla de cuenta heredada del prototipo, todavia sobre `mock-data` |

## Lo que NO esta

El pago (`comercio`, §9 del contrato). El boton existe y esta apagado con la
razon escrita al lado, porque un boton que no hace nada es peor que uno
apagado que dice por que.
