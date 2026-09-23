"use client";

// Vista previa de SOLO LECTURA de los tres kits que saldrían de una versión de
// lista (región 4 del revisor).
//
// Por qué no se reusa `ConsolaRevision` tal cual: esa consola —y su
// `LineaRevision`— cablean acciones que MUTAN (validar, marcar sin coincidencia,
// dar de alta, marcar no disponible, validar en lote), sin ninguna prop de solo
// lectura para apagarlas. `marcarNoDisponible` además muta el catálogo entero.
// Este trabajo de preview es desechable: exponer esas acciones sobre él (o sobre
// el catálogo) sería un efecto colateral no deseado. Así que se rearma la MISMA
// presentación —pestañas por perfil, recomendado, consolidaciones y secciones en
// el orden del contrato— reusando los helpers del contrato (`agruparPorClase`,
// `ORDEN_SECCIONES`, `TITULO_CLASE`, `formatearPesos`), pero sin ningún control
// que escriba. Publicar sigue siendo el botón "Aprobar y publicar" (`cerrarLista`)
// de la página de revisión, no aquí.

import { useState } from "react";
import type { LineaKit, PerfilKit, ProductoKit, TrabajoAdmin } from "@tukit/contrato";
import {
  agruparPorClase,
  formatearPesos,
  ORDEN_SECCIONES,
  razonDeNoCobrar,
  TITULO_CLASE,
} from "@tukit/contrato";
import { esPendiente, porcentaje, TITULO_MODO, TITULO_TIPO } from "@/lib/formato";
import styles from "@/components/Revision.module.css";

interface Props {
  trabajo: TrabajoAdmin;
}

function precioMasBajo(producto: ProductoKit): number | null {
  const precios = producto.ofertas.map((o) => o.precio);
  return precios.length === 0 ? null : Math.min(...precios);
}

function TarjetaProducto({
  producto,
  papel,
}: {
  producto: ProductoKit;
  papel: "elegido" | "alternativa";
}) {
  const precio = precioMasBajo(producto);
  return (
    <li className={styles.producto}>
      <div className={styles.productoCabecera}>
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
      </div>

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
    </li>
  );
}

function LineaPreview({ linea }: { linea: LineaKit }) {
  const elegido = linea.producto_elegido ?? null;
  const alternativas = linea.alternativas ?? [];
  const razon = razonDeNoCobrar(linea);

  return (
    <details className={styles.linea}>
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
        </dl>

        {linea.url_externa ? (
          <p className={styles.detalle}>
            Pago externo:{" "}
            <a href={linea.url_externa} target="_blank" rel="noreferrer">
              {linea.url_externa}
            </a>
          </p>
        ) : null}

        {elegido || alternativas.length > 0 ? (
          <ul className={styles.productos}>
            {elegido ? <TarjetaProducto producto={elegido} papel="elegido" /> : null}
            {alternativas.map((alternativa) => (
              <TarjetaProducto key={alternativa.sku} producto={alternativa} papel="alternativa" />
            ))}
          </ul>
        ) : (
          <p className={styles.detalle}>Sin producto emparejado en esta vista previa.</p>
        )}
      </div>
    </details>
  );
}

export default function KitsPreview({ trabajo }: Props) {
  const [perfil, setPerfil] = useState<PerfilKit>(trabajo.recomendado?.perfil ?? "Ahorrador");
  const kit = trabajo.kits.find((k) => k.perfil === perfil) ?? trabajo.kits[0];

  if (!kit) {
    return (
      <p className={styles.vacio}>
        Esta versión todavía no arma kits: no hay renglones resueltos que previsualizar.
      </p>
    );
  }

  const grupos = agruparPorClase(kit.lineas);
  const secciones = ORDEN_SECCIONES.map((clase) => ({
    clase,
    lineas: grupos.get(clase) ?? [],
  })).filter((seccion) => seccion.lineas.length > 0);

  return (
    <section className={styles.consola}>
      <div className={styles.selector} role="group" aria-label="Perfil del kit que se previsualiza">
        {trabajo.kits.map((candidato) => {
          const activo = candidato.perfil === perfil;
          const recomendado = trabajo.recomendado?.perfil === candidato.perfil;
          return (
            <button
              key={candidato.perfil}
              type="button"
              className={`${styles.pestana} ${activo ? styles.pestanaActiva : ""}`}
              aria-pressed={activo}
              onClick={() => setPerfil(candidato.perfil)}
            >
              <span className={styles.perfilNombre}>
                {candidato.perfil}
                {recomendado ? <span className={styles.recomendado}>recomendado</span> : null}
              </span>
              <span className={`${styles.perfilTotal} cifra`}>
                {formatearPesos(candidato.total)}
              </span>
              <span className={styles.perfilObjetivos}>
                fidelidad {porcentaje(candidato.objetivos.fidelidad)} · disponibilidad{" "}
                {porcentaje(candidato.objetivos.disponibilidad)}
              </span>
            </button>
          );
        })}
      </div>

      {trabajo.recomendado ? (
        <p className={styles.razonRecomendacion}>
          <strong>Se marcaría {trabajo.recomendado.perfil}:</strong> {trabajo.recomendado.razon}{" "}
          {trabajo.recomendado.dentro_de_presupuesto
            ? ""
            : "Ojo: queda fuera del presupuesto declarado."}
        </p>
      ) : null}

      {kit.consolidaciones.length > 0 ? (
        <details className={styles.consolidaciones}>
          <summary>
            {kit.consolidaciones.length} consolidaciones entre hermanos
            <span className="cifra">
              {formatearPesos(kit.consolidaciones.reduce((t, c) => t + c.ahorro, 0))} de ahorro
            </span>
          </summary>
          <ul>
            {kit.consolidaciones.map((consolidacion) => (
              <li key={consolidacion.concepto}>
                <code>{consolidacion.concepto}</code> · {consolidacion.hijos.join(" + ")} ·{" "}
                {consolidacion.unidades_a_comprar} u. · ahorra{" "}
                <span className="cifra">{formatearPesos(consolidacion.ahorro)}</span>
                <span className={styles.explicacion}>{consolidacion.explicacion}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {secciones.map(({ clase, lineas }) => (
        <section
          key={clase}
          className={`${styles.seccion} ${esPendiente(clase) ? styles.seccionPendiente : ""}`}
        >
          <header className={styles.seccionCabecera}>
            <h3>
              {TITULO_CLASE[clase]}
              <span className={styles.conteo}>{lineas.length}</span>
            </h3>
          </header>
          <div className={styles.lineas}>
            {lineas.map((linea) => (
              <LineaPreview key={linea.item_id} linea={linea} />
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}
