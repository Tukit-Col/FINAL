"use client";

// Una linea del kit, con todo lo que hace falta para decidirla (AD-02, AD-05,
// AD-07).
//
// Es un `<details>` y no una tarjeta siempre abierta porque una lista de
// sexto trae cincuenta y cinco renglones y el admin solo tiene que tocar los
// pendientes: lo resuelto se deja plegado y a un clic, no escondido.

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ClaseLinea, LineaKit, PerfilKit, ProductoKit } from "@tukit/contrato";
import { formatearPesos, razonDeNoCobrar } from "@tukit/contrato";
import {
  FalloApi,
  fijarProductoLinea,
  marcarNoDisponible,
  marcarSinCoincidencia,
  validarLinea,
} from "@/lib/api-navegador";
import { esPendiente, porcentaje, TITULO_MODO, TITULO_TIPO } from "@/lib/formato";
import AltaProducto from "./AltaProducto";
import BuscarEnCatalogo from "./BuscarEnCatalogo";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  linea: LineaKit;
  clase: ClaseLinea;
  // El perfil del kit al que pertenece esta linea. Cuando llega, cambiar de
  // producto (elegir una alternativa) se guarda POR NIVEL: escribe la LINEA de
  // ESTE kit y recalcula su subtotal, sin tocar los otros dos. Sin el, la
  // validacion es la de siempre (por item, los tres kits) —el caso de las
  // vistas que no son la matriz.
  perfil?: PerfilKit;
  // Selección para acciones masivas. Solo se pasa en las secciones donde tiene
  // sentido validar en lote (las que tienen un elegido por confirmar); si no
  // llega, la línea no muestra casilla y se comporta como siempre.
  seleccionable?: boolean;
  seleccionada?: boolean;
  onToggleSeleccion?: (itemId: string) => void;
}

/** Sin `sku` la validacion se lee como "confirmo el que el sistema eligio". */
const CONFIRMAR_EL_ELEGIDO = "";

function precioMasBajo(producto: ProductoKit): number | null {
  const precios = producto.ofertas.map((o) => o.precio);
  return precios.length === 0 ? null : Math.min(...precios);
}

export default function LineaRevision({
  trabajoId,
  linea,
  clase,
  perfil,
  seleccionable = false,
  seleccionada = false,
  onToggleSeleccion,
}: Props) {
  const router = useRouter();
  const pendiente = esPendiente(clase);

  const elegido = linea.producto_elegido ?? null;
  const alternativas = linea.alternativas ?? [];
  const hayQueElegir = elegido !== null || alternativas.length > 0;

  // Lo pendiente nace abierto y lo resuelto cerrado. El cuerpo solo se pinta
  // cuando la linea esta abierta: una lista de sexto con dos hijos son ciento
  // diez renglones, y pintar los ciento diez paneles completos para que el
  // admin toque tres es medio mega de HTML que nadie lee.
  const [abierta, setAbierta] = useState(pendiente);
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
    // Cambiar de producto en la matriz es una decision POR KIT: escribe la
    // LINEA de este perfil y recalcula su subtotal. Confirmar el elegido (sin
    // sku) sigue siendo la validacion por item —marca el emparejamiento como
    // bueno en los tres kits, no cambia ningun producto—.
    if (sku && perfil) {
      void ejecutar(
        () => fijarProductoLinea(trabajoId, perfil, linea.item_id, sku),
        "Producto cambiado en este kit.",
      );
      return;
    }
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
    const marcado =
      papel === "elegido"
        ? seleccion === CONFIRMAR_EL_ELEGIDO || seleccion === producto.sku
        : seleccion === producto.sku;
    return (
      <li
        key={producto.sku}
        className={`${styles.producto} ${hayQueElegir && marcado ? styles.productoMarcado : ""}`}
      >
        {/* Toda la tarjeta es la opción: el radio queda oculto pero accesible
            (teclado y lector), y el anillo de la tarjeta dice cuál va. */}
        <label className={styles.productoCabecera}>
          {hayQueElegir && (
            <input
              type="radio"
              className={styles.radioOculto}
              name={`producto-${linea.item_id}`}
              checked={marcado}
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
            <span className={styles.productoPildoras}>
              <span className={`${styles.nivel} ${styles[`nivel_${producto.nivel}`]}`}>
                {producto.nivel}
              </span>
              {producto.personaje ? (
                <span className={styles.personaje}>{producto.personaje}</span>
              ) : null}
              {papel === "elegido" ? (
                <span className={styles.insignia}>Sugerido por el sistema</span>
              ) : null}
            </span>
            <span className={styles.productoNombre}>{producto.nombre}</span>
            <span className={styles.productoMeta}>
              <code>{producto.sku}</code>
              {producto.marca ? <span>{producto.marca}</span> : null}
              <span
                className={producto.confianza < 0.6 ? styles.confianzaBaja : styles.confianza}
                title="Confianza del emparejamiento"
              >
                confianza {porcentaje(producto.confianza)}
              </span>
            </span>
          </span>
          {hayQueElegir && marcado ? (
            <span className={styles.marcaElegida} aria-hidden="true">
              ✓
            </span>
          ) : null}
        </label>

        <div className={styles.productoPie}>
          <span className={`${styles.productoPrecio} cifra`}>{formatearPesos(precio)}</span>
          <ul className={styles.ofertas}>
            {producto.ofertas.length === 0 ? (
              <li className={styles.sinOferta}>Sin oferta vigente: no entra al total (§8)</li>
            ) : (
              producto.ofertas.map((oferta) => (
                <li
                  key={`${producto.sku}-${oferta.tienda}`}
                  title={
                    oferta.vigente_hasta
                      ? `Vigente hasta ${oferta.vigente_hasta.slice(0, 10)}`
                      : undefined
                  }
                >
                  <span className={styles.tienda}>{oferta.tienda}</span>
                  <span className="cifra">{formatearPesos(oferta.precio)}</span>
                </li>
              ))
            )}
          </ul>
        </div>

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
            title="AD-05: apaga el producto en todo el catálogo"
            onClick={() => {
              setSkuAApagar(producto.sku);
              setMotivoApagado("");
            }}
          >
            Marcar no disponible
          </button>
        )}
      </li>
    );
  }

  return (
    <details
      className={`${styles.linea} ${pendiente ? styles.lineaPendiente : ""}`}
      open={abierta}
      onToggle={(evento) => setAbierta(evento.currentTarget.open)}
    >
      <summary className={`${styles.resumenLinea} ${seleccionable ? styles.resumenConCasilla : ""}`}>
        {seleccionable ? (
          // La casilla no despliega la línea: es una acción aparte. Por eso
          // corta la propagación y el `preventDefault` del click en el summary.
          <input
            type="checkbox"
            className={styles.casilla}
            checked={seleccionada}
            aria-label={`Seleccionar ${linea.item_id} para acción masiva`}
            onClick={(evento) => evento.stopPropagation()}
            onChange={(evento) => {
              evento.stopPropagation();
              onToggleSeleccion?.(linea.item_id);
            }}
          />
        ) : null}
        <code className={styles.itemId} title={linea.item_id}>
          {linea.item_id.slice(0, 8)}
        </code>
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

      {abierta ? (
        <div className={styles.cuerpoLinea}>
          {razon ? <p className={styles.razon}>{razon}</p> : null}

          <dl className={styles.datos}>
            <div>
              <dt>Pide</dt>
              <dd className="cifra">
                {linea.cantidad_pedida ?? "—"} {linea.unidad_base ?? ""}
              </dd>
            </div>
            <div>
              <dt>Empaque</dt>
              <dd className="cifra">{linea.unidades_por_empaque ?? "—"}</dd>
            </div>
            <div>
              <dt>Compra</dt>
              <dd className="cifra">{linea.unidades_a_comprar ?? "—"}</dd>
            </div>
            {linea.modo_adquisicion ? (
              <div>
                <dt>Modo</dt>
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
            <ul className={styles.productos} aria-label="Opciones de producto">
              {elegido ? tarjetaProducto(elegido, "elegido") : null}
              {alternativas.map((alternativa) => tarjetaProducto(alternativa, "alternativa"))}
            </ul>
          ) : (
            <>
              <p className={styles.detalle}>
                No hay producto que confirmar. Búscalo en el catálogo; si no está, dalo de alta a
                mano (AD-07) o déjala sin coincidencia con el motivo.
              </p>
              {perfil ? (
                <BuscarEnCatalogo
                  concepto={linea.concepto ?? null}
                  textoInicial={linea.descripcion}
                  enviando={enviando}
                  onElegir={(sku) =>
                    void ejecutar(
                      () => fijarProductoLinea(trabajoId, perfil, linea.item_id, sku),
                      `Producto ${sku} puesto en este kit.`,
                    )
                  }
                />
              ) : null}
            </>
          )}

          {/* ------------------------------------------------ acciones AD-02 */}
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
                    ? "Confirmar el sugerido"
                    : perfil
                      ? `Usar este producto en ${perfil}`
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
      ) : null}
    </details>
  );
}
