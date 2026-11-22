"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeftRight, Check, RotateCcw, X } from "lucide-react";
import {
  cambiarProductoDeKit,
  descartarLineaDeKit,
  FalloApi,
  opcionesDeLinea,
} from "@/lib/api-navegador";
import { idAnclaLinea, pistaDeTienda } from "@/lib/kit-vista";
import {
  ETIQUETA_NIVEL,
  estadoDePrecio,
  etiquetaEmpaque,
  formatearPesos,
  razonDeNoCobrar,
  type ClaseLinea,
  type LineaKit,
  type OpcionDeLinea,
  type ProductoKit,
} from "@tukit/contrato";
import styles from "./Kits.module.css";

export default function LineaDeKit({
  linea,
  clase,
  nombreHijo,
  trabajoId,
  perfil,
}: {
  linea: LineaKit;
  clase: ClaseLinea;
  nombreHijo?: string;
  trabajoId: string;
  perfil: string;
}) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [quitando, setQuitando] = useState(false);
  const [errorDescarte, setErrorDescarte] = useState<string | null>(null);
  const producto = linea.producto_elegido;
  const [skuVisto, setSkuVisto] = useState(producto?.sku);
  const [huboCambio, setHuboCambio] = useState(false);
  if (producto?.sku !== skuVisto) {
    setSkuVisto(producto?.sku);
    setHuboCambio(true);
  }
  const razon = razonDeNoCobrar(linea);
  const pista = producto ? pistaDeTienda(producto.ofertas ?? []) : null;
  const precio = estadoDePrecio(linea);
  const descartado = linea.descartado === true;
  const sePuedeTocar = clase === "comprable" && Boolean(producto);

  async function descartar(quitar: boolean) {
    setQuitando(true);
    setErrorDescarte(null);
    try {
      await descartarLineaDeKit(trabajoId, perfil, linea.item_id, quitar);
      setAbierto(false);
      router.refresh();
    } catch (causa) {
      setErrorDescarte(
        causa instanceof FalloApi ? causa.message : "No pudimos hacer el cambio. Intenta de nuevo.",
      );
    } finally {
      setQuitando(false);
    }
  }

  return (
    <li
      id={idAnclaLinea(linea.item_id)}
      data-linea={linea.item_id}
      className={`${styles.linea} ${descartado ? styles.lineaDescartada : ""}`}
    >
      <div
        key={producto?.sku ?? "sin-producto"}
        className={`${styles.lineaPrincipal} ${huboCambio ? styles.productoNuevo : ""}`}
      >
        {producto ? (
          <Foto producto={producto} />
        ) : (
          <span className={styles.sinFoto} aria-hidden="true" />
        )}

        <div className={styles.lineaTexto}>
          <p className={styles.descripcion}>{linea.descripcion}</p>

          <p className={styles.meta}>
            {nombreHijo && <span className={styles.hijo}>{nombreHijo}</span>}
            {typeof linea.cantidad_pedida === "number" && (
              <span>
                pide {linea.cantidad_pedida}
                {linea.unidad_base && linea.unidad_base !== "unidad"
                  ? ` ${linea.unidad_base}`
                  : ""}
              </span>
            )}
            {typeof linea.unidades_por_empaque === "number" &&
              linea.unidades_por_empaque > 1 && (
                <span>empaque de {linea.unidades_por_empaque}</span>
              )}
            {typeof linea.unidades_a_comprar === "number" &&
              linea.unidades_a_comprar > 0 &&
              !descartado && (
                <span className={styles.compramos}>compramos {linea.unidades_a_comprar}</span>
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
              {linea.cambiado_por_acudiente && !descartado && (
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

          {descartado ? (
            <p className={styles.razonNoCobro}>
              Lo quitaste de tu kit porque ya lo tienes. No se cobra y no entra en el total.
            </p>
          ) : (
            razon && <p className={styles.razonNoCobro}>{razon}</p>
          )}

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
          {precio.tipo === "precio" ? (
            <span className={`${styles.subtotal} cifra`}>{formatearPesos(precio.valor)}</span>
          ) : precio.tipo === "descartado" ? (
            <span className={styles.noCobrado}>
              Quitado
              {precio.ahorro ? ` · ahorras ${formatearPesos(precio.ahorro)}` : ""}
            </span>
          ) : (
            <span className={styles.noCobrado}>{precio.titulo}</span>
          )}
          {pista && !descartado && <span className={styles.tienda}>{pista}</span>}
        </div>
      </div>

      {sePuedeTocar && (
        <div className={styles.alternativas}>
          <div className={styles.accionesLinea}>
            {!descartado && (
              <button
                type="button"
                className={styles.botonCambiar}
                aria-expanded={abierto}
                onClick={() => setAbierto((a) => !a)}
              >
                <ArrowLeftRight size={14} aria-hidden="true" strokeWidth={2.4} />
                {abierto ? "Cerrar opciones" : "Cambiar por otra opción"}
              </button>
            )}
            {descartado ? (
              <button
                type="button"
                className={styles.botonCambiar}
                disabled={quitando}
                onClick={() => void descartar(false)}
              >
                <RotateCcw size={14} aria-hidden="true" strokeWidth={2.4} />
                {quitando ? "Volviendo a ponerlo…" : "Volver a ponerlo en mi kit"}
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.botonCambiar} ${styles.botonQuitar}`}
                disabled={quitando}
                onClick={() => void descartar(true)}
              >
                <X size={14} aria-hidden="true" strokeWidth={2.4} />
                {quitando ? "Quitando…" : "No lo necesito / ya lo tengo"}
              </button>
            )}
          </div>
          {errorDescarte && (
            <p className={styles.errorCambio} role="alert">
              {errorDescarte}
            </p>
          )}
          {abierto && !descartado && producto && (
            <CarruselDeOpciones
              linea={linea}
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

function CarruselDeOpciones({
  linea,
  trabajoId,
  perfil,
  onListo,
}: {
  linea: LineaKit;
  trabajoId: string;
  perfil: string;
  onListo: () => void;
}) {
  const router = useRouter();
  const [opciones, setOpciones] = useState<OpcionDeLinea[] | null>(null);
  const [guardando, setGuardando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pista = useRef<HTMLUListElement>(null);

  useEffect(() => {
    let vivo = true;
    opcionesDeLinea(trabajoId, perfil, linea.item_id)
      .then((r) => {
        if (vivo) setOpciones(r.opciones);
      })
      .catch((causa) => {
        if (!vivo) return;
        setOpciones(opcionesDeRespaldo(linea));
        setError(
          causa instanceof FalloApi
            ? causa.message
            : "No pudimos traer más opciones. Te mostramos las que ya tenemos.",
        );
      });
    return () => {
      vivo = false;
    };
  }, [trabajoId, perfil, linea]);

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

  const [hayIzq, setHayIzq] = useState(false);
  const [hayDer, setHayDer] = useState(false);

  const medirBordes = useCallback(() => {
    const el = pista.current;
    if (!el) return;
    setHayIzq(el.scrollLeft > 2);
    setHayDer(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    const el = pista.current;
    if (!el) return;
    medirBordes();
    const observador = new ResizeObserver(medirBordes);
    observador.observe(el);
    return () => observador.disconnect();
  }, [opciones, medirBordes]);

  function mover(direccion: 1 | -1) {
    const el = pista.current;
    if (el) el.scrollBy({ left: direccion * (el.clientWidth * 0.8), behavior: "smooth" });
  }

  return (
    <div className={styles.panelCambio}>
      <p className={styles.tituloCambio}>
        Otras opciones para «{linea.descripcion}». El precio es lo que costaría este renglón.
      </p>
      {opciones === null ? (
        <div className={styles.esqueletoOpciones} role="status">
          <span className={styles.visualmenteOculto}>Buscando opciones…</span>
          <span className={styles.esqueletoTarjeta} aria-hidden="true" />
          <span className={styles.esqueletoTarjeta} aria-hidden="true" />
          <span className={styles.esqueletoTarjeta} aria-hidden="true" />
        </div>
      ) : opciones.length <= 1 ? (
        <p className={styles.notaCambio}>Por ahora no tenemos otra opción para este renglón.</p>
      ) : (
        <div
          className={`${styles.carruselMarco} ${hayIzq ? styles.hayIzq : ""} ${
            hayDer ? styles.hayDer : ""
          }`}
        >
          {hayIzq && (
            <button
              type="button"
              className={`${styles.flechaCarrusel} ${styles.flechaIzq}`}
              onClick={() => mover(-1)}
              aria-label="Ver opciones anteriores"
            >
              ‹
            </button>
          )}
          <ul
            ref={pista}
            onScroll={medirBordes}
            className={styles.carrusel}
            tabIndex={0}
            aria-label="Opciones del mismo tipo de producto"
          >
            {opciones.map((opcion) => (
              <li
                key={opcion.sku}
                className={`${styles.tarjetaOpcion} ${opcion.en_kit ? styles.opcionEnKit : ""}`}
              >
                <FotoOpcion url={opcion.imagen_url} />
                <span className={`${styles.nivel} ${styles[opcion.nivel]}`}>
                  {ETIQUETA_NIVEL[opcion.nivel]}
                </span>
                <span className={styles.opcionNombre}>{opcion.nombre}</span>
                {opcion.marca && <span className={styles.marca}>{opcion.marca}</span>}
                {opcion.personaje && <span className={styles.personaje}>{opcion.personaje}</span>}
                <span className={`${styles.opcionPrecioGrande} cifra`}>
                  {formatearPesos(opcion.subtotal)}
                </span>
                <span className={styles.opcionEmpaque}>
                  {etiquetaEmpaque(opcion.unidades_por_empaque, opcion.unidades_a_comprar)}
                  {opcion.unidades_por_empaque > 1 || opcion.unidades_a_comprar > 1
                    ? ` · ${formatearPesos(opcion.precio)} c/u`
                    : ""}
                </span>
                {!opcion.en_kit && opcion.diferencia !== null && opcion.diferencia !== 0 && (
                  <span
                    className={`${styles.diferencia} ${
                      opcion.diferencia > 0 ? styles.masCaro : styles.masBarato
                    } cifra`}
                    title="Diferencia con lo que tienes hoy en el kit"
                  >
                    {opcion.diferencia > 0 ? "+" : "−"}
                    {formatearPesos(Math.abs(opcion.diferencia))} en tu total
                  </span>
                )}
                {opcion.sugerido && <span className={styles.sugeridaTukit}>Sugerido por Tukit</span>}
                {opcion.en_kit ? (
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
              </li>
            ))}
          </ul>
          {hayDer && (
            <button
              type="button"
              className={`${styles.flechaCarrusel} ${styles.flechaDer}`}
              onClick={() => mover(1)}
              aria-label="Ver más opciones"
            >
              ›
            </button>
          )}
        </div>
      )}
      {opciones !== null && opciones.length > 1 && (
        <p className={styles.pistaCarrusel}>
          {opciones.length} opciones
          {(hayIzq || hayDer) && " · desliza para ver más"}
        </p>
      )}
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

function opcionesDeRespaldo(linea: LineaKit): OpcionDeLinea[] {
  const actual = linea.producto_elegido;
  if (!actual) return [];
  const precioActual = actual.ofertas[0]?.precio ?? null;
  const salida: OpcionDeLinea[] = [];
  for (const p of [actual, ...(linea.alternativas ?? [])]) {
    const precio = p.ofertas[0]?.precio;
    if (precio === undefined) continue;
    const enKit = p.sku === actual.sku;
    salida.push({
        sku: p.sku,
        nombre: p.nombre,
        marca: p.marca,
        nivel: p.nivel,
        personaje: p.personaje,
        imagen_url: p.imagen_url,
        precio,
        unidades_por_empaque: 1,
        unidades_a_comprar: 1,
        subtotal: precio,
        diferencia: precioActual === null || enKit ? 0 : precio - precioActual,
        en_kit: enKit,
        sugerido: linea.cambiado_por_acudiente ? p.sku === linea.sku_sugerido : enKit,
    });
  }
  return salida;
}

function FotoOpcion({ url }: { url: string | null }) {
  if (!url) {
    return (
      <span className={styles.fotoOpcion} aria-hidden="true">
        sin foto
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img className={styles.fotoOpcion} src={url} alt="" loading="lazy" />;
}

function Foto({ producto }: { producto: ProductoKit }) {
  if (!producto.imagen_url) {
    return (
      <span className={styles.sinFoto} aria-hidden="true">
        sin foto
      </span>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img className={styles.foto} src={producto.imagen_url} alt="" loading="lazy" />
  );
}
