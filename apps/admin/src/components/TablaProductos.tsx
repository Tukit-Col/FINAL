// Rejilla paginada de productos del catálogo (P4c). Es presentación pura:
// recibe la página ya resuelta y avisa hacia arriba cuándo se elige una ficha o
// se cambia de página. La búsqueda/filtrado la maneja `GestorCatalogo`.
//
// Se muestra como REJILLA DE TARJETAS (como el gestor del MS), no como tabla:
// cada producto es una ficha con foto grande, pastilla de nivel, nombre, precio
// y metadatos. Cada tarjeta es un <button> real, así funciona con teclado.

import { ImageOff } from "lucide-react";
import { ETIQUETA_NIVEL, formatearPesos } from "@tukit/contrato";
import type { ProductoCatalogoDetalle } from "@tukit/contrato";
import styles from "./CatalogoSpa.module.css";

interface Props {
  productos: ProductoCatalogoDetalle[];
  total: number;
  pagina: number;
  porPagina: number;
  cargando: boolean;
  skuActivo: string | null;
  onElegir: (producto: ProductoCatalogoDetalle) => void;
  onPagina: (pagina: number) => void;
}

export default function TablaProductos({
  productos,
  total,
  pagina,
  porPagina,
  cargando,
  skuActivo,
  onElegir,
  onPagina,
}: Props) {
  const desde = total === 0 ? 0 : (pagina - 1) * porPagina + 1;
  const hasta = Math.min(pagina * porPagina, total);
  const ultimaPagina = Math.max(1, Math.ceil(total / porPagina));

  return (
    <div className={styles.tablaEnvoltura}>
      <div className={styles.tablaCabecera}>
        <span className={styles.conteo}>
          {total} {total === 1 ? "producto" : "productos"}
        </span>
        {total > 0 && (
          <span>
            Mostrando {desde}–{hasta} de {total}
          </span>
        )}
      </div>

      {productos.length === 0 ? (
        <p className={styles.vacioTabla}>
          {cargando ? "Buscando…" : "Ningún producto coincide con estos filtros."}
        </p>
      ) : (
        <div className={styles.rejillaProductos}>
          {productos.map((p) => (
            <button
              key={p.sku}
              type="button"
              className={`${styles.tarjeta} ${p.sku === skuActivo ? styles.tarjetaActiva : ""}`}
              aria-pressed={p.sku === skuActivo}
              onClick={() => onElegir(p)}
            >
              {p.imagen_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img className={styles.tarjetaFoto} src={p.imagen_url} alt="" />
              ) : (
                <span className={styles.tarjetaFotoVacia}>
                  <ImageOff size={28} aria-hidden="true" />
                </span>
              )}

              <div className={styles.tarjetaPildoras}>
                <span className={`${styles.nivelPildora} ${styles[`nivel_${p.nivel}`]}`}>
                  {ETIQUETA_NIVEL[p.nivel]}
                </span>
                {p.personaje && (
                  <span className={styles.personajePildora}>{p.personaje}</span>
                )}
              </div>

              <div className={styles.tarjetaNombre}>{p.nombre}</div>
              <div className={styles.skuMono}>{p.sku}</div>

              <div className={styles.tarjetaPie}>
                <span className={styles.tarjetaPrecio}>
                  {p.precio_desde !== null ? (
                    formatearPesos(p.precio_desde)
                  ) : (
                    <span className={styles.sinDato}>sin precio</span>
                  )}
                </span>
                <span className={styles.tarjetaMeta}>
                  {p.marca ? <span>{p.marca}</span> : null}
                  <span className={styles.tarjetaTiendas}>
                    {p.concepto.nombre} · {p.tiendas}{" "}
                    {p.tiendas === 1 ? "tienda" : "tiendas"}
                  </span>
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {ultimaPagina > 1 && (
        <div className={styles.paginacion}>
          <button
            type="button"
            className={styles.secundario}
            disabled={pagina <= 1 || cargando}
            onClick={() => onPagina(pagina - 1)}
          >
            Anterior
          </button>
          <span className={styles.paginaActual}>
            Página {pagina} de {ultimaPagina}
          </span>
          <button
            type="button"
            className={styles.secundario}
            disabled={pagina >= ultimaPagina || cargando}
            onClick={() => onPagina(pagina + 1)}
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
