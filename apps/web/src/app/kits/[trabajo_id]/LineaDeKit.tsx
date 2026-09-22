"use client";

import { useState } from "react";
import {
  ETIQUETA_NIVEL,
  formatearPesos,
  razonDeNoCobrar,
  type ClaseLinea,
  type LineaKit,
  type ProductoKit,
} from "@tukit/contrato";
import styles from "./Kits.module.css";

/**
 * Un renglon del kit.
 *
 * El contrato las modela todas con la misma forma, pero en pantalla no se
 * parecen: una tiene precio y foto, otra tiene un link de pago externo, otra
 * es una disculpa con alternativas. Lo que si comparten es que TODAS se
 * muestran. Ocultar la que no se puede vender deja al acudiente con un hueco
 * que descubre tarde, que es justo el dolor que vino a evitar.
 */
export default function LineaDeKit({ linea, clase }: { linea: LineaKit; clase: ClaseLinea }) {
  const [abierto, setAbierto] = useState(false);
  const producto = linea.producto_elegido;
  const razon = razonDeNoCobrar(linea);
  const alternativas = linea.alternativas ?? [];

  return (
    <li className={styles.linea}>
      <div className={styles.lineaPrincipal}>
        {producto ? (
          <Foto producto={producto} />
        ) : (
          <span className={styles.sinFoto} aria-hidden="true" />
        )}

        <div className={styles.lineaTexto}>
          <p className={styles.descripcion}>{linea.descripcion}</p>

          <p className={styles.meta}>
            {linea.hijo && <span className={styles.hijo}>{linea.hijo}</span>}
            {typeof linea.cantidad_pedida === "number" && (
              <span>
                pide {linea.cantidad_pedida}
                {linea.unidad_base && linea.unidad_base !== "unidad"
                  ? ` ${linea.unidad_base}`
                  : ""}
              </span>
            )}
            {/* Los tres numeros del §5 separados, que es todo el arreglo de
                unidades: doce lapices no son doce cajas. */}
            {typeof linea.unidades_por_empaque === "number" &&
              linea.unidades_por_empaque > 1 && (
                <span>empaque de {linea.unidades_por_empaque}</span>
              )}
            {typeof linea.unidades_a_comprar === "number" && linea.unidades_a_comprar > 0 && (
              <span className={styles.compramos}>
                compramos {linea.unidades_a_comprar}
              </span>
            )}
          </p>

          {producto && (
            <p className={styles.producto}>
              <strong>{producto.nombre}</strong>
              {producto.marca && <span className={styles.marca}>{producto.marca}</span>}
              <span className={`${styles.nivel} ${styles[producto.nivel]}`}>
                {ETIQUETA_NIVEL[producto.nivel]}
              </span>
              {producto.personaje && (
                <span className={styles.personaje}>{producto.personaje}</span>
              )}
            </p>
          )}

          {linea.edicion?.titulo && (
            <p className={styles.edicion}>
              Edicion exigida: <strong>{linea.edicion.titulo}</strong>
              {linea.edicion.editorial && ` · ${linea.edicion.editorial}`}
              {linea.no_consolidable && (
                <em title={linea.motivo_no_consolidable ?? undefined}>
                  {" "}
                  · no se junta con la de tu otro hijo
                </em>
              )}
            </p>
          )}

          {razon && <p className={styles.razonNoCobro}>{razon}</p>}

          {linea.url_externa && (
            <a
              className={styles.enlacePago}
              href={linea.url_externa}
              target="_blank"
              rel="noopener noreferrer"
            >
              Ir a pagarlo con el proveedor →
            </a>
          )}

          {linea.instruccion_colegio && clase === "informativa" && (
            <p className={styles.instruccion}>
              Instruccion del colegio: <q>{linea.instruccion_colegio}</q>
            </p>
          )}

          {linea.sustitutos && linea.sustitutos.length > 0 && (
            <div className={styles.sustitutos}>
              <span>Lo que si tenemos y podria servirte:</span>
              <ul>
                {linea.sustitutos.map((s) => (
                  <li key={s.concepto}>
                    <strong>{s.nombre}</strong> — {s.motivo}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className={styles.lineaPrecio}>
          {linea.subtotal_linea !== null ? (
            <span className={`${styles.subtotal} cifra`}>
              {formatearPesos(linea.subtotal_linea)}
            </span>
          ) : (
            <span className={styles.noCobrado}>No se cobra</span>
          )}
          {producto && producto.ofertas.length > 0 && (
            <span className={styles.tienda}>
              en {producto.ofertas[0]?.tienda}
              {producto.ofertas.length > 1 && ` · ${producto.ofertas.length} tiendas`}
            </span>
          )}
        </div>
      </div>

      {alternativas.length > 0 && (
        <div className={styles.alternativas}>
          <button
            type="button"
            className={styles.verAlternativas}
            aria-expanded={abierto}
            onClick={() => setAbierto((a) => !a)}
          >
            {abierto ? "Ocultar" : `Ver ${alternativas.length} opciones mas`}
          </button>
          {abierto && (
            <ul className={styles.listaAlternativas}>
              {alternativas.map((alternativa) => (
                <li key={alternativa.sku}>
                  <span className={`${styles.nivel} ${styles[alternativa.nivel]}`}>
                    {ETIQUETA_NIVEL[alternativa.nivel]}
                  </span>
                  <span className={styles.nombreAlternativa}>{alternativa.nombre}</span>
                  <span className="cifra">
                    {formatearPesos(alternativa.ofertas[0]?.precio ?? null)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function Foto({ producto }: { producto: ProductoKit }) {
  if (!producto.imagen_url) {
    return (
      <span className={styles.sinFoto} aria-hidden="true">
        sin foto
      </span>
    );
  }
  // Las fotos son de las tiendas y se sirven desde su origen, igual que en el
  // volcado de catalogo del backend. Se usa `img` y no `next/image` para no
  // atar la pantalla a una lista cerrada de dominios que cambia cada vez que
  // se agrega una tienda.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img className={styles.foto} src={producto.imagen_url} alt="" loading="lazy" />
  );
}
