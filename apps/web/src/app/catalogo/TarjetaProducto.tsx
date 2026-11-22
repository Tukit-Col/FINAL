import {
  ETIQUETA_NIVEL,
  formatearPesos,
  precioMasBarato,
  type OfertaCatalogo,
  type ProductoCatalogo,
} from "@tukit/contrato";
import estilos from "./Catalogo.module.css";

const UMBRAL_SIN_REVISAR = 0.4;

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
  const notaPrecio =
    barato === null
      ? "ninguna tienda reporta precio"
      : conPrecio > 1
        ? `el más barato de ${conPrecio} tiendas`
        : "una sola tienda lo vende";

  return (
    <article className={estilos.producto}>
      {producto.imagen_url ? (
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
