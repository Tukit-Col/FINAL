"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftRight, Check } from "lucide-react";
import { cambiarProductoDeKit, FalloApi } from "@/lib/api-navegador";
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
export default function LineaDeKit({
  linea,
  clase,
  trabajoId,
  perfil,
}: {
  linea: LineaKit;
  clase: ClaseLinea;
  trabajoId: string;
  perfil: string;
}) {
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
              {linea.cambiado_por_acudiente && (
                <span className={styles.cambiadoPorTi}>Lo elegiste tú</span>
              )}
            </p>
          )}

          {linea.edicion?.titulo && (
            <p className={styles.edicion}>
              Edición exigida: <strong>{linea.edicion.titulo}</strong>
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
              Instrucción del colegio: <q>{linea.instruccion_colegio}</q>
            </p>
          )}

          {linea.sustitutos && linea.sustitutos.length > 0 && (
            <div className={styles.sustitutos}>
              <span>Lo que sí tenemos y podría servirte:</span>
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
          {/* Las ofertas por tienda son opcionales: el backend las omite en la
              línea del kit (el producto ya trae su `precio`). Se pinta la pista
              de tienda solo cuando existe, en vez de asumir que siempre viene. */}
          {producto && (producto.ofertas?.length ?? 0) > 0 && (
            <span className={styles.tienda}>
              en {producto.ofertas![0]?.tienda}
              {producto.ofertas!.length > 1 && ` · ${producto.ofertas!.length} tiendas`}
            </span>
          )}
        </div>
      </div>

      {producto && alternativas.length > 0 && (
        <div className={styles.alternativas}>
          <button
            type="button"
            className={styles.botonCambiar}
            aria-expanded={abierto}
            onClick={() => setAbierto((a) => !a)}
          >
            <ArrowLeftRight size={14} aria-hidden="true" strokeWidth={2.4} />
            {abierto
              ? "Cerrar"
              : `Cambiar por otra opción · ${alternativas.length} ${
                  alternativas.length === 1 ? "disponible" : "disponibles"
                }`}
          </button>
          {abierto && (
            <OpcionesDeCambio
              linea={linea}
              producto={producto}
              alternativas={alternativas}
              trabajoId={trabajoId}
              perfil={perfil}
              onListo={() => setAbierto(false)}
            />
          )}
        </div>
      )}
    </li>
  );
}

/**
 * Las opciones para cambiar el producto de un renglón: la que está en el kit y
 * las alternativas que una persona revisó, como tarjetas para elegir. Elegir
 * una la guarda en el trabajo del acudiente y recalcula el total en el
 * servidor (`router.refresh()` trae el kit nuevo). La sugerida por Tukit queda
 * siempre a la vista para volver a ella.
 */
function OpcionesDeCambio({
  linea,
  producto,
  alternativas,
  trabajoId,
  perfil,
  onListo,
}: {
  linea: LineaKit;
  producto: ProductoKit;
  alternativas: ProductoKit[];
  trabajoId: string;
  perfil: string;
  onListo: () => void;
}) {
  const router = useRouter();
  const [guardando, setGuardando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const precioActual = producto.ofertas[0]?.precio ?? null;

  async function elegir(sku: string) {
    setGuardando(sku);
    setError(null);
    try {
      await cambiarProductoDeKit(trabajoId, perfil, linea.item_id, sku);
      router.refresh();
      onListo();
    } catch (causa) {
      setError(
        causa instanceof FalloApi ? causa.message : "No pudimos cambiar el producto. Intenta de nuevo.",
      );
    } finally {
      setGuardando(null);
    }
  }

  const opciones = [producto, ...alternativas];
  return (
    <div className={styles.panelCambio}>
      <p className={styles.tituloCambio}>Elige el que prefieras para «{linea.descripcion}»</p>
      <ul className={styles.opcionesCambio}>
        {opciones.map((opcion) => {
          const enKit = opcion.sku === producto.sku;
          const sugerido = linea.cambiado_por_acudiente
            ? opcion.sku === linea.sku_sugerido
            : enKit;
          const precio = opcion.ofertas[0]?.precio ?? null;
          const diferencia =
            precio !== null && precioActual !== null && !enKit ? precio - precioActual : null;
          return (
            <li
              key={opcion.sku}
              className={`${styles.opcionCambio} ${enKit ? styles.opcionEnKit : ""}`}
            >
              <div className={styles.opcionCabecera}>
                <Foto producto={opcion} />
                <div className={styles.opcionTexto}>
                  <span className={`${styles.nivel} ${styles[opcion.nivel]}`}>
                    {ETIQUETA_NIVEL[opcion.nivel]}
                  </span>
                  <span className={styles.opcionNombre}>{opcion.nombre}</span>
                  {opcion.marca && <span className={styles.marca}>{opcion.marca}</span>}
                </div>
              </div>
              <div className={styles.opcionPie}>
                <span className={styles.opcionPrecio}>
                  <span className="cifra">{formatearPesos(precio)}</span>
                  {diferencia !== null && diferencia !== 0 && (
                    <span
                      className={`${styles.diferencia} ${
                        diferencia > 0 ? styles.masCaro : styles.masBarato
                      } cifra`}
                      title="Diferencia de precio con el producto que tienes en el kit"
                    >
                      {diferencia > 0 ? "+" : "−"}
                      {formatearPesos(Math.abs(diferencia))}
                    </span>
                  )}
                </span>
                {enKit ? (
                  <span className={styles.enTuKit}>
                    <Check size={14} aria-hidden="true" strokeWidth={3} />
                    En tu kit
                  </span>
                ) : (
                  <button
                    type="button"
                    className={styles.botonElegir}
                    disabled={guardando !== null}
                    onClick={() => void elegir(opcion.sku)}
                  >
                    {guardando === opcion.sku ? "Cambiando…" : "Elegir"}
                  </button>
                )}
              </div>
              {sugerido && <span className={styles.sugeridaTukit}>Sugerido por Tukit</span>}
            </li>
          );
        })}
      </ul>
      {error && (
        <p className={styles.errorCambio} role="alert">
          {error}
        </p>
      )}
      <p className={styles.notaCambio}>
        El total del kit se actualiza al elegir. Solo cambia este kit ({perfil}).
      </p>
    </div>
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
