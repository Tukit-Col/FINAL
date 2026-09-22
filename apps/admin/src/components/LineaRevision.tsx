"use client";

// Una linea del kit, con todo lo que hace falta para decidirla (AD-04, AD-05,
// AD-07).
//
// Es un `<details>` y no una tarjeta siempre abierta porque una lista de
// sexto trae cincuenta y cinco renglones y el admin solo tiene que tocar los
// pendientes: lo resuelto se deja plegado y a un clic, no escondido.

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ClaseLinea, LineaKit, ProductoKit } from "@tukit/contrato";
import { formatearPesos, razonDeNoCobrar } from "@tukit/contrato";
import {
  FalloApi,
  marcarNoDisponible,
  marcarSinCoincidencia,
  validarLinea,
} from "@/lib/api-navegador";
import { esPendiente, porcentaje, TITULO_MODO, TITULO_TIPO } from "@/lib/formato";
import AltaProducto from "./AltaProducto";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  linea: LineaKit;
  clase: ClaseLinea;
}

/** Sin `sku` la validacion se lee como "confirmo el que el sistema eligio". */
const CONFIRMAR_EL_ELEGIDO = "";

function precioMasBajo(producto: ProductoKit): number | null {
  const precios = producto.ofertas.map((o) => o.precio);
  return precios.length === 0 ? null : Math.min(...precios);
}

export default function LineaRevision({ trabajoId, linea, clase }: Props) {
  const router = useRouter();
  const pendiente = esPendiente(clase);

  const elegido = linea.producto_elegido ?? null;
  const alternativas = linea.alternativas ?? [];
  const hayQueElegir = elegido !== null || alternativas.length > 0;

  const [seleccion, setSeleccion] = useState<string>(CONFIRMAR_EL_ELEGIDO);
  const [nota, setNota] = useState("");
  const [motivo, setMotivo] = useState("");
  const [panel, setPanel] = useState<"ninguno" | "sin_coincidencia" | "alta">("ninguno");
  const [skuAApagar, setSkuAApagar] = useState<string | null>(null);
  const [motivoApagado, setMotivoApagado] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  async function ejecutar(operacion: () => Promise<unknown>, exito: string): Promise<void> {
    setError(null);
    setAviso(null);
    setEnviando(true);
    try {
      await operacion();
      setAviso(exito);
      // El estado de la linea lo recalcula el servidor a partir de lo que
      // acabamos de guardar: refrescar es la unica forma de que la pantalla
      // muestre el estado de verdad y no el que creemos que quedo.
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : "No pudimos guardar el cambio.");
    } finally {
      setEnviando(false);
    }
  }

  function alValidar(): void {
    const sku = seleccion === CONFIRMAR_EL_ELEGIDO ? undefined : seleccion;
    void ejecutar(
      () =>
        validarLinea(trabajoId, linea.item_id, {
          ...(sku ? { sku } : {}),
          ...(nota.trim() ? { nota: nota.trim() } : {}),
        }),
      sku ? "Línea validada con la alternativa que elegiste." : "Línea validada.",
    );
  }

  function alMarcarSinCoincidencia(): void {
    if (!motivo.trim()) {
      setError("Escribe el motivo: una marca sin motivo no se puede revisar después.");
      return;
    }
    void ejecutar(
      () => marcarSinCoincidencia(trabajoId, linea.item_id, { motivo: motivo.trim() }),
      "Línea marcada sin coincidencia.",
    );
  }

  function alApagarProducto(sku: string): void {
    if (!motivoApagado.trim()) {
      setError("Escribe por qué no está disponible.");
      return;
    }
    void ejecutar(async () => {
      await marcarNoDisponible(sku, { motivo: motivoApagado.trim() });
      setSkuAApagar(null);
      setMotivoApagado("");
    }, "Producto marcado como no disponible en todo el catálogo.");
  }

  const razon = razonDeNoCobrar(linea);

  function tarjetaProducto(producto: ProductoKit, papel: "elegido" | "alternativa") {
    const precio = precioMasBajo(producto);
    return (
      <li key={producto.sku} className={styles.producto}>
        <label className={styles.productoCabecera}>
          {hayQueElegir && (
            <input
              type="radio"
              name={`producto-${linea.item_id}`}
              checked={
                papel === "elegido"
                  ? seleccion === CONFIRMAR_EL_ELEGIDO || seleccion === producto.sku
                  : seleccion === producto.sku
              }
              onChange={() =>
                setSeleccion(papel === "elegido" ? CONFIRMAR_EL_ELEGIDO : producto.sku)
              }
            />
          )}
          {/* next/image exigiria declarar cada dominio en `images.remotePatterns`,
              y las imagenes vienen de las tiendas: el dominio cambia con el
              catalogo, no con el codigo. */}
          {producto.imagen_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={producto.imagen_url} alt="" className={styles.miniatura} />
          ) : (
            <span className={styles.miniaturaVacia} aria-hidden="true" />
          )}
          <span className={styles.productoTexto}>
            <span className={styles.productoNombre}>{producto.nombre}</span>
            <span className={styles.productoMeta}>
              <code>{producto.sku}</code>
              {producto.marca ? <span>{producto.marca}</span> : null}
              <span className={`${styles.nivel} ${styles[`nivel_${producto.nivel}`]}`}>
                {producto.nivel}
              </span>
              {producto.personaje ? (
                <span className={styles.personaje}>{producto.personaje}</span>
              ) : null}
              <span
                className={producto.confianza < 0.6 ? styles.confianzaBaja : styles.confianza}
                title="Confianza del emparejamiento"
              >
                confianza {porcentaje(producto.confianza)}
              </span>
              {papel === "elegido" ? (
                <span className={styles.insignia}>elegido por el sistema</span>
              ) : null}
            </span>
          </span>
          <span className={`${styles.productoPrecio} cifra`}>{formatearPesos(precio)}</span>
        </label>

        <ul className={styles.ofertas}>
          {producto.ofertas.length === 0 ? (
            <li className={styles.sinOferta}>Sin oferta vigente: no entra al total (§8).</li>
          ) : (
            producto.ofertas.map((oferta) => (
              <li key={`${producto.sku}-${oferta.tienda}`}>
                <span className={styles.tienda}>{oferta.tienda}</span>
                <span className="cifra">{formatearPesos(oferta.precio)}</span>
                {oferta.vigente_hasta ? (
                  <span className={styles.vigencia}>hasta {oferta.vigente_hasta.slice(0, 10)}</span>
                ) : null}
              </li>
            ))
          )}
        </ul>

        {skuAApagar === producto.sku ? (
          <div className={styles.formularioEnLinea}>
            <label htmlFor={`no-disp-${linea.item_id}-${producto.sku}`}>
              Motivo por el que no está disponible (obligatorio)
            </label>
            <textarea
              id={`no-disp-${linea.item_id}-${producto.sku}`}
              rows={2}
              value={motivoApagado}
              onChange={(evento) => setMotivoApagado(evento.target.value)}
              placeholder="Agotado en las dos tiendas desde el lunes."
            />
            <p className={styles.advertencia}>
              Apaga la oferta en el catálogo, o sea para todos los trabajos en cola, no solo
              para este.
            </p>
            <div className={styles.botonera}>
              <button
                type="button"
                className={styles.peligro}
                disabled={enviando}
                onClick={() => alApagarProducto(producto.sku)}
              >
                Marcar no disponible
              </button>
              <button
                type="button"
                className={styles.plano}
                onClick={() => {
                  setSkuAApagar(null);
                  setMotivoApagado("");
                }}
              >
                Cancelar
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className={styles.enlaceAccion}
            onClick={() => {
              setSkuAApagar(producto.sku);
              setMotivoApagado("");
            }}
          >
            No está disponible (AD-05)
          </button>
        )}
      </li>
    );
  }

  return (
    <details className={`${styles.linea} ${pendiente ? styles.lineaPendiente : ""}`} open={pendiente}>
      <summary className={styles.resumenLinea}>
        <code className={styles.itemId}>{linea.item_id}</code>
        <span className={styles.descripcion}>{linea.descripcion}</span>
        <span className={styles.etiquetas}>
          <span className={styles.etiqueta}>{TITULO_TIPO[linea.tipo]}</span>
          {linea.estado_resolucion ? (
            <span
              className={`${styles.etiqueta} ${
                styles[`resolucion_${linea.estado_resolucion}`] ?? ""
              }`}
            >
              {linea.estado_resolucion}
            </span>
          ) : null}
          {linea.hijo ? <span className={styles.hijo}>{linea.hijo}</span> : null}
        </span>
        <span className={`${styles.subtotal} cifra`}>{formatearPesos(linea.subtotal_linea)}</span>
      </summary>

      <div className={styles.cuerpoLinea}>
        {razon ? <p className={styles.razon}>{razon}</p> : null}

        <dl className={styles.datos}>
          <div>
            <dt>Pedido en la lista</dt>
            <dd className="cifra">
              {linea.cantidad_pedida ?? "—"} {linea.unidad_base ?? ""}
            </dd>
          </div>
          <div>
            <dt>Unidades por empaque</dt>
            <dd className="cifra">{linea.unidades_por_empaque ?? "—"}</dd>
          </div>
          <div>
            <dt>Unidades a comprar</dt>
            <dd className="cifra">{linea.unidades_a_comprar ?? "—"}</dd>
          </div>
          {linea.modo_adquisicion ? (
            <div>
              <dt>Modo de adquisición</dt>
              <dd>{TITULO_MODO[linea.modo_adquisicion]}</dd>
            </div>
          ) : null}
          {linea.concepto ? (
            <div>
              <dt>Concepto</dt>
              <dd>
                <code>{linea.concepto}</code>
              </dd>
            </div>
          ) : null}
          {linea.edicion ? (
            <div>
              <dt>Edición</dt>
              <dd>
                {linea.edicion.titulo}
                {linea.edicion.editorial ? ` · ${linea.edicion.editorial}` : ""}
                {linea.edicion.isbn13 ? ` · ISBN ${linea.edicion.isbn13}` : ""}
              </dd>
            </div>
          ) : null}
        </dl>

        {linea.atributo_faltante ? (
          <p className={styles.detalle}>
            Atributo que falta en el catálogo:{" "}
            {Object.entries(linea.atributo_faltante)
              .map(([clave, valor]) => `${clave} = ${valor}`)
              .join(" · ")}
          </p>
        ) : null}

        {linea.no_consolidable ? (
          <p className={styles.detalle}>
            No consolidable entre hermanos.{" "}
            {linea.motivo_no_consolidable ?? "Dos ediciones del mismo título no son sustituibles."}
          </p>
        ) : null}

        {linea.url_externa ? (
          <p className={styles.detalle}>
            Pago externo:{" "}
            <a href={linea.url_externa} target="_blank" rel="noreferrer">
              {linea.url_externa}
            </a>
          </p>
        ) : null}

        {linea.sustitutos && linea.sustitutos.length > 0 ? (
          <div className={styles.sustitutos}>
            <h4>Sustitutos del grafo</h4>
            <ul>
              {linea.sustitutos.map((sustituto) => (
                <li key={sustituto.concepto}>
                  <code>{sustituto.concepto}</code> {sustituto.nombre}
                  <span className={styles.grado}>grado {sustituto.grado}</span>
                  <span className={styles.motivoSustituto}>{sustituto.motivo}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {elegido || alternativas.length > 0 ? (
          <ul className={styles.productos}>
            {elegido ? tarjetaProducto(elegido, "elegido") : null}
            {alternativas.map((alternativa) => tarjetaProducto(alternativa, "alternativa"))}
          </ul>
        ) : (
          <p className={styles.detalle}>
            No hay producto que confirmar. Lo que resuelve esta línea es dar de alta uno a
            mano (AD-07) o dejarla marcada sin coincidencia con el motivo.
          </p>
        )}

        {/* ------------------------------------------------ acciones AD-04 */}
        <div className={styles.acciones}>
          {hayQueElegir ? (
            <>
              <input
                className={styles.notaCorta}
                type="text"
                value={nota}
                onChange={(evento) => setNota(evento.target.value)}
                placeholder="Nota de la validación (opcional)"
                aria-label="Nota de la validación"
              />
              <button
                type="button"
                className={styles.principal}
                disabled={enviando}
                onClick={alValidar}
              >
                {seleccion === CONFIRMAR_EL_ELEGIDO
                  ? "Validar el elegido"
                  : "Validar con la alternativa"}
              </button>
            </>
          ) : null}
          <button
            type="button"
            className={styles.secundario}
            onClick={() => setPanel(panel === "sin_coincidencia" ? "ninguno" : "sin_coincidencia")}
          >
            Sin coincidencia
          </button>
          <button
            type="button"
            className={styles.secundario}
            onClick={() => setPanel(panel === "alta" ? "ninguno" : "alta")}
          >
            Dar de alta un producto
          </button>
        </div>

        {panel === "sin_coincidencia" ? (
          <div className={styles.formularioEnLinea}>
            <label htmlFor={`motivo-${linea.item_id}`}>
              Motivo de la marca sin coincidencia (obligatorio)
            </label>
            <textarea
              id={`motivo-${linea.item_id}`}
              rows={2}
              value={motivo}
              onChange={(evento) => setMotivo(evento.target.value)}
              placeholder="El renglón pide una marca que no distribuimos y no hay equivalente."
            />
            <div className={styles.botonera}>
              <button
                type="button"
                className={styles.principal}
                disabled={enviando}
                onClick={alMarcarSinCoincidencia}
              >
                Marcar sin coincidencia
              </button>
              <button type="button" className={styles.plano} onClick={() => setPanel("ninguno")}>
                Cancelar
              </button>
            </div>
          </div>
        ) : null}

        {panel === "alta" ? (
          <AltaProducto
            trabajoId={trabajoId}
            linea={linea}
            alTerminar={(sku) => {
              setPanel("ninguno");
              setAviso(`Producto ${sku} dado de alta y asignado a la línea.`);
            }}
          />
        ) : null}

        {error ? <p className={styles.error}>{error}</p> : null}
        {aviso ? <p className={styles.exito}>{aviso}</p> : null}
      </div>
    </details>
  );
}
