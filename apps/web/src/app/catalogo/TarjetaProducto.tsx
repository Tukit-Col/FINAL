import {
  ETIQUETA_NIVEL,
  formatearPesos,
  precioMasBarato,
  type OfertaCatalogo,
  type ProductoCatalogo,
} from "@tukit/contrato";
import estilos from "./Catalogo.module.css";

// El mismo umbral con el que el resumen cuenta los `productos_sin_revisar`. Si
// las dos cifras no salieran del mismo numero, la pantalla se contradiria con
// su propio encabezado y no habria forma de saber cual de las dos miente.
const UMBRAL_SIN_REVISAR = 0.5;

// Los tres estados de `disponible` son tres, no dos. `null` es el caso normal
// del canal mayorista, que no publica stock; leerlo como "agotado" borraria de
// la comparacion a una tienda entera.
const ESTADO_STOCK = {
  hay: { texto: "en stock", titulo: "La tienda reporta unidades disponibles.", clase: estilos.stockHay },
  agotado: { texto: "agotado", titulo: "La tienda reporta que no le quedan unidades.", clase: estilos.stockAgotado },
  sinDato: {
    texto: "stock sin dato",
    titulo: "Esta tienda no reporta stock. No quiere decir que esté agotado.",
    clase: estilos.stockSinDato,
  },
} as const;

function estadoDe(disponible: boolean | null): (typeof ESTADO_STOCK)[keyof typeof ESTADO_STOCK] {
  if (disponible === true) return ESTADO_STOCK.hay;
  if (disponible === false) return ESTADO_STOCK.agotado;
  return ESTADO_STOCK.sinDato;
}

// `visto_en` llega en ISO con el desplazamiento de Bogota. Se recorta en vez de
// pasarlo por `Date`, porque formatear con la zona del navegador haria que el
// servidor y el cliente pintaran dias distintos y React lo reportaria como una
// discrepancia de hidratacion.
function fechaCorta(iso: string): string {
  const [anio, mes, dia] = iso.slice(0, 10).split("-");
  return dia && mes && anio ? `${dia}/${mes}/${anio}` : iso;
}

function porPrecio(a: OfertaCatalogo, b: OfertaCatalogo): number {
  if (a.precio === null) return b.precio === null ? 0 : 1;
  if (b.precio === null) return -1;
  return a.precio - b.precio;
}

interface Props {
  producto: ProductoCatalogo;
}

export default function TarjetaProducto({ producto }: Props) {
  const barato = precioMasBarato(producto);
  const ofertas = [...producto.ofertas].sort(porPrecio);
  const enlace = ofertas.find((oferta) => oferta.url)?.url ?? null;
  const conPrecio = ofertas.filter((oferta) => oferta.precio !== null).length;
  // `precio: null` es "no se conoce el precio", que no es lo mismo que cero ni
  // que gratis, asi que la nota lo dice con palabras en vez de mostrar un $ 0.
  const notaPrecio =
    barato === null
      ? "ninguna tienda reporta precio"
      : conPrecio > 1
        ? `el más barato de ${conPrecio} tiendas`
        : "una sola tienda lo vende";

  return (
    <article className={estilos.producto}>
      {producto.imagen_url ? (
        // Las fotos son de las tiendas y sus dominios no estan declarados en
        // `next.config.ts`; `next/image` los rechazaria en tiempo de peticion.
        // eslint-disable-next-line @next/next/no-img-element
        <img className={estilos.foto} src={producto.imagen_url} alt="" loading="lazy" />
      ) : (
        <div className={estilos.sinFoto}>sin foto</div>
      )}

      <p className={estilos.nombreProducto}>
        {enlace ? (
          <a className={estilos.enlaceNombre} href={enlace} target="_blank" rel="noopener">
            {producto.nombre}
          </a>
        ) : (
          producto.nombre
        )}
      </p>

      {producto.marca && <p className={estilos.marcaProducto}>{producto.marca}</p>}

      {/* Nivel y personaje van en dos etiquetas separadas y con colores de
          familias distintas: un cuaderno de Spiderman tiene personaje Y
          ADEMAS nivel de calidad. Pintarlos juntos haria del personaje un
          cuarto nivel y dejaria al optimizador sin con que comparar. */}
      <div className={estilos.etiquetasProducto}>
        <span className={estilos.chipNivel} data-nivel={producto.nivel}>
          {ETIQUETA_NIVEL[producto.nivel]}
        </span>
        {producto.personaje && <span className={estilos.chipPersonaje}>{producto.personaje}</span>}
        {producto.es_propio && <span className={estilos.chipPropio}>marca propia</span>}
        {producto.quality_score < UMBRAL_SIN_REVISAR && (
          <span
            className={estilos.chipSinRevisar}
            title="Lo sugirió la búsqueda y nadie lo confirmó todavía."
          >
            sin revisar
          </span>
        )}
      </div>

      <div className={estilos.precios}>
        <p className={estilos.precioDestacado}>
          <span className={`${barato === null ? estilos.precioSinDato : estilos.precioValor} cifra`}>
            {formatearPesos(barato)}
          </span>
          <span className={estilos.precioNota}>{notaPrecio}</span>
        </p>

        {/* Todas las ofertas, y no solo la ganadora: comparar el precio entre
            tiendas es el nucleo de la propuesta, y el modelo de datos se
            rediseno justamente para poder expresarlo. */}
        <ul className={estilos.ofertas}>
          {ofertas.map((oferta) => {
            const estado = estadoDe(oferta.disponible);
            const esBarata = barato !== null && oferta.precio === barato;
            return (
              <li
                key={`${oferta.tienda}-${oferta.url ?? "sin-url"}`}
                className={`${estilos.oferta} ${esBarata ? estilos.ofertaBarata : ""}`}
              >
                <span className={estilos.tienda}>{oferta.tienda_nombre}</span>
                <span className={estilos.stock} title={estado.titulo}>
                  <span className={`${estilos.stockPunto} ${estado.clase}`} aria-hidden="true" />
                  {estado.texto}
                </span>
                {/* Con una sola tienda el precio de la fila seria el mismo de
                    arriba, y repetirlo solo gasta el ancho que necesita el
                    nombre de la tienda. */}
                {ofertas.length > 1 && (
                  <span
                    className={`${estilos.precioTienda} cifra`}
                    title={oferta.visto_en ? `Precio visto el ${fechaCorta(oferta.visto_en)}` : undefined}
                  >
                    {formatearPesos(oferta.precio)}
                  </span>
                )}
                {oferta.url && (
                  <a
                    className={estilos.enlaceTienda}
                    href={oferta.url}
                    target="_blank"
                    rel="noopener"
                    aria-label={`Ver ${producto.nombre} en ${oferta.tienda_nombre}`}
                  >
                    ver
                  </a>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </article>
  );
}
