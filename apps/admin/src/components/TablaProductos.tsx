// Tabla paginada de productos del catálogo (P4c). Es presentación pura: recibe
// la página ya resuelta y avisa hacia arriba cuándo se elige una fila o se
// cambia de página. La búsqueda/filtrado la maneja `GestorCatalogo`.

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
            Mostrando {desde}–{hasta}
          </span>
        )}
      </div>

      {productos.length === 0 ? (
        <p className={styles.vacioTabla}>
          {cargando ? "Buscando…" : "Ningún producto coincide con estos filtros."}
        </p>
      ) : (
        <table className={styles.tabla}>
          <thead>
            <tr>
              <th aria-label="Imagen" />
              <th>Producto</th>
              <th>Marca</th>
              <th>Nivel</th>
              <th>Personaje</th>
              <th>Concepto</th>
              <th style={{ textAlign: "right" }}>Desde</th>
              <th style={{ textAlign: "center" }}>Tiendas</th>
            </tr>
          </thead>
          <tbody>
            {productos.map((p) => (
              <tr
                key={p.sku}
                className={p.sku === skuActivo ? styles.filaActiva : undefined}
                onClick={() => onElegir(p)}
              >
                <td className={styles.celdaImagen}>
                  {p.imagen_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img className={styles.miniatura} src={p.imagen_url} alt="" />
                  ) : (
                    <span className={styles.miniaturaVacia}>
                      <ImageOff size={16} aria-hidden="true" />
                    </span>
                  )}
                </td>
                <td className={styles.celdaNombre}>
                  <div className={styles.nombreProducto}>{p.nombre}</div>
                  <div className={styles.skuMono}>{p.sku}</div>
                </td>
                <td>{p.marca ?? <span className={styles.sinDato}>—</span>}</td>
                <td>
                  <span className={`${styles.nivelPildora} ${styles[`nivel_${p.nivel}`]}`}>
                    {ETIQUETA_NIVEL[p.nivel]}
                  </span>
                </td>
                <td>
                  {p.personaje ? (
                    <span className={styles.personajePildora}>{p.personaje}</span>
                  ) : (
                    <span className={styles.sinDato}>—</span>
                  )}
                </td>
                <td>{p.concepto.nombre}</td>
                <td className={styles.celdaPrecio}>
                  {p.precio_desde !== null ? (
                    formatearPesos(p.precio_desde)
                  ) : (
                    <span className={styles.sinDato}>sin precio</span>
                  )}
                </td>
                <td className={styles.celdaTiendas}>{p.tiendas}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
