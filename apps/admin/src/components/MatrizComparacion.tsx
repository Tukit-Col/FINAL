"use client";

import { useState } from "react";
import type { ClaseLinea, Kit, LineaKit, PerfilKit } from "@tukit/contrato";
import {
  agruparPorClase,
  formatearPesos,
  ORDEN_SECCIONES,
  razonDeNoCobrar,
  TITULO_CLASE,
} from "@tukit/contrato";
import { esPendiente } from "@/lib/formato";
import LineaRevision from "./LineaRevision";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  kits: Kit[];
  recomendado: PerfilKit | undefined;
  sinRotuloRecomendado?: boolean;
  soloLectura?: boolean;
}

const ORDEN_PERFIL: PerfilKit[] = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

interface Fila {
  itemId: string;
  clase: ClaseLinea;
  descripcion: string;
  hijo: string | undefined;
  concepto: string | null | undefined;
  porPerfil: Map<PerfilKit, LineaKit>;
}

function nivelDe(linea: LineaKit | undefined): string | null {
  return linea?.producto_elegido?.nivel ?? null;
}

export default function MatrizComparacion({
  trabajoId,
  kits,
  recomendado,
  sinRotuloRecomendado = false,
  soloLectura = false,
}: Props) {
  const rotulado = sinRotuloRecomendado ? undefined : recomendado;
  const [abierta, setAbierta] = useState<{ itemId: string; perfil: PerfilKit } | null>(null);

  const perfiles = ORDEN_PERFIL.filter((p) => kits.some((k) => k.perfil === p));

  const filasPorItem = new Map<string, Fila>();
  for (const kit of kits) {
    for (const linea of kit.lineas) {
      let fila = filasPorItem.get(linea.item_id);
      if (!fila) {
        fila = {
          itemId: linea.item_id,
          clase: "comprable",
          descripcion: linea.descripcion,
          hijo: linea.hijo,
          concepto: linea.concepto,
          porPerfil: new Map(),
        };
        filasPorItem.set(linea.item_id, fila);
      }
      fila.porPerfil.set(kit.perfil, linea);
    }
  }

  const perfilRef = recomendado ?? perfiles[0];
  const representativas: LineaKit[] = [];
  for (const fila of filasPorItem.values()) {
    const rep = (perfilRef && fila.porPerfil.get(perfilRef)) ?? [...fila.porPerfil.values()][0];
    if (rep) representativas.push(rep);
  }
  const claseDe = new Map<string, ClaseLinea>();
  for (const [clase, lineas] of agruparPorClase(representativas)) {
    for (const l of lineas) claseDe.set(l.item_id, clase);
  }
  for (const fila of filasPorItem.values()) {
    fila.clase = claseDe.get(fila.itemId) ?? "comprable";
  }

  const secciones = ORDEN_SECCIONES.map((clase) => ({
    clase,
    filas: [...filasPorItem.values()].filter((f) => f.clase === clase),
  })).filter((s) => s.filas.length > 0);

  const tieneProducto = (f: Fila): boolean =>
    [...f.porPerfil.values()].some((l) => Boolean(l.producto_elegido));
  const seccionesMatriz = secciones.filter((s) => s.filas.some(tieneProducto));
  const sinProducto = secciones.filter((s) => !s.filas.some(tieneProducto));
  const seccionesAviso = sinProducto.filter((s) => esPendiente(s.clase));
  const seccionesFuera = sinProducto.filter((s) => !esPendiente(s.clase));

  const hijos = new Set([...filasPorItem.values()].map((f) => f.hijo).filter(Boolean));
  const mostrarHijo = hijos.size > 1;

  function alternar(itemId: string, perfil: PerfilKit): void {
    if (soloLectura) return;
    setAbierta((previa) =>
      previa && previa.itemId === itemId && previa.perfil === perfil
        ? null
        : { itemId, perfil },
    );
  }

  function perfilDeFila(fila: Fila): PerfilKit | undefined {
    if (perfilRef && fila.porPerfil.has(perfilRef)) return perfilRef;
    return perfiles.find((p) => fila.porPerfil.has(p));
  }

  function razonDeFila(fila: Fila): string | null {
    const perfil = perfilDeFila(fila);
    const linea = perfil ? fila.porPerfil.get(perfil) : undefined;
    return linea ? razonDeNoCobrar(linea) : null;
  }

  function metaConcepto(fila: Fila) {
    if (!fila.concepto && !(mostrarHijo && fila.hijo)) return null;
    return (
      <span className={styles.matrizMetaConcepto}>
        {fila.concepto ? <code>{fila.concepto}</code> : null}
        {mostrarHijo && fila.hijo ? <span className={styles.hijo}>{fila.hijo}</span> : null}
      </span>
    );
  }

  function detalle(fila: Fila, nota: string) {
    const celdaAbierta = abierta && abierta.itemId === fila.itemId ? abierta : null;
    const lineaAbierta = celdaAbierta ? fila.porPerfil.get(celdaAbierta.perfil) : undefined;
    if (!celdaAbierta || !lineaAbierta) return null;
    return (
      <div className={styles.matrizDetalle}>
        <p className={styles.matrizDetalleNota}>{nota}</p>
        <LineaRevision
          key={`${fila.itemId}-${celdaAbierta.perfil}`}
          trabajoId={trabajoId}
          linea={lineaAbierta}
          clase={fila.clase}
          perfil={celdaAbierta.perfil}
        />
      </div>
    );
  }

  function filaMatriz(fila: Fila) {
    const celdaAbierta = abierta && abierta.itemId === fila.itemId ? abierta : null;
    return (
      <div key={fila.itemId} className={styles.matrizFilaBloque}>
        <div className={styles.matrizFila} style={{ ["--columnas" as string]: perfiles.length }}>
          <div className={styles.matrizConcepto}>
            <span className={styles.matrizDescripcion}>{fila.descripcion}</span>
            {metaConcepto(fila)}
          </div>

          {perfiles.map((perfil) => {
            const linea = fila.porPerfil.get(perfil);
            const producto = linea?.producto_elegido ?? null;
            const nivel = nivelDe(linea);
            const activa = celdaAbierta?.perfil === perfil;
            return (
              <button
                key={perfil}
                type="button"
                className={`${styles.celda} ${activa ? styles.celdaActiva : ""} ${!linea ? styles.celdaVacia : ""}`}
                aria-pressed={activa}
                disabled={soloLectura || !linea}
                onClick={() => linea && alternar(fila.itemId, perfil)}
              >
                {producto ? (
                  <>
                    {producto.imagen_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={producto.imagen_url} alt="" className={styles.celdaMini} />
                    ) : (
                      <span className={styles.celdaMiniVacia} aria-hidden="true" />
                    )}
                    <span className={styles.celdaTexto}>
                      <span className={styles.celdaNombre} title={producto.nombre}>
                        {producto.nombre}
                      </span>
                      <span className={styles.celdaBadges}>
                        {nivel ? (
                          <span className={`${styles.nivel} ${styles[`nivel_${nivel}`]}`}>{nivel}</span>
                        ) : null}
                        {producto.personaje ? (
                          <span className={styles.personaje}>{producto.personaje}</span>
                        ) : null}
                      </span>
                    </span>
                    <span className={`${styles.celdaPrecio} cifra`}>
                      {linea && linea.unidades_a_comprar === 0 && linea.subtotal_linea === 0
                        ? "Ya va arriba"
                        : formatearPesos(linea?.subtotal_linea ?? null)}
                    </span>
                  </>
                ) : (
                  <span className={styles.celdaSinProducto}>
                    {linea ? "Sin producto elegido" : "—"}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {celdaAbierta
          ? detalle(
              fila,
              `Editando ${celdaAbierta.perfil}. Cambiar de producto se guarda solo en este kit y recalcula su total; confirmar el elegido vale para el concepto en todos los kits.`,
            )
          : null}
      </div>
    );
  }

  return (
    <div className={styles.matriz}>
      {seccionesAviso.map(({ clase, filas }) => (
        <section key={clase} className={styles.avisoPanel}>
          <header className={styles.avisoCabecera}>
            <h3>
              {TITULO_CLASE[clase]}
              <span className={styles.conteo}>{filas.length}</span>
            </h3>
            <p>
              {soloLectura
                ? "Sin producto en ningún kit."
                : "Sin producto en ningún kit. Lo que decidas aquí vale para todos los kits."}
            </p>
          </header>
          <ul className={styles.avisoLista}>
            {filas.map((fila) => {
              const perfil = perfilDeFila(fila);
              const activa = abierta?.itemId === fila.itemId;
              return (
                <li key={fila.itemId} className={styles.avisoItem}>
                  <div className={styles.avisoFila}>
                    <div className={styles.avisoConcepto}>
                      <span className={styles.matrizDescripcion}>{fila.descripcion}</span>
                      {metaConcepto(fila)}
                    </div>
                    <p className={styles.avisoRazon}>{razonDeFila(fila)}</p>
                    {soloLectura ? null : (
                      <button
                        type="button"
                        className={activa ? styles.avisoBotonActivo : styles.avisoBoton}
                        aria-expanded={activa}
                        disabled={!perfil}
                        onClick={() => perfil && alternar(fila.itemId, perfil)}
                      >
                        {activa ? "Cerrar" : "Resolver"}
                      </button>
                    )}
                  </div>
                  {detalle(fila, "Resolver este renglón lo deja igual en todos los kits.")}
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <div className={styles.matrizCabecera} style={{ ["--columnas" as string]: perfiles.length }}>
        <span className={styles.matrizEsquina}>Concepto</span>
        {perfiles.map((perfil) => {
          const kit = kits.find((k) => k.perfil === perfil);
          return (
            <span
              key={perfil}
              className={`${styles.matrizColTitulo} ${perfil === rotulado ? styles.matrizColReco : ""}`}
            >
              <span className={styles.perfilNombre}>
                {perfil}
                {perfil === rotulado ? <span className={styles.recomendado}>recomendado</span> : null}
              </span>
              {kit ? <span className={`${styles.perfilTotal} cifra`}>{formatearPesos(kit.total)}</span> : null}
            </span>
          );
        })}
      </div>

      {seccionesMatriz.map(({ clase, filas }) => (
        <section key={clase} className={styles.matrizSeccion}>
          <h3 className={`${styles.matrizSeccionTitulo} ${esPendiente(clase) ? styles.seccionPendiente : ""}`}>
            {TITULO_CLASE[clase]}
            <span className={styles.conteo}>{filas.length}</span>
          </h3>
          {filas.map(filaMatriz)}
        </section>
      ))}

      {seccionesFuera.length > 0 ? (
        <section className={styles.fueraPanel}>
          <header className={styles.fueraCabecera}>
            <h3>No se buscan en el catálogo</h3>
            <p>
              No entran al total de ningún kit: el acudiente los ve como aviso para que no se le
              pasen.{soloLectura ? "" : " Pulsa uno si hay que corregirlo."}
            </p>
          </header>
          <div className={styles.fueraGrupos}>
            {seccionesFuera.map(({ clase, filas }) => {
              const razones = filas.map(razonDeFila);
              const razonComun = razones.every((r) => r === razones[0]) ? razones[0] : null;
              const abiertaAqui = filas.find((f) => f.itemId === abierta?.itemId);
              return (
                <div key={clase} className={styles.fueraGrupo}>
                  <h4 className={styles.fueraTitulo}>
                    {TITULO_CLASE[clase]}
                    <span className={styles.conteo}>{filas.length}</span>
                  </h4>
                  {razonComun ? <p className={styles.fueraRazon}>{razonComun}</p> : null}
                  <div className={styles.fichas}>
                    {filas.map((fila, i) => {
                      const perfil = perfilDeFila(fila);
                      const activa = abierta?.itemId === fila.itemId;
                      return (
                        <button
                          key={fila.itemId}
                          type="button"
                          className={`${styles.ficha} ${activa ? styles.fichaActiva : ""}`}
                          aria-pressed={activa}
                          disabled={soloLectura || !perfil}
                          onClick={() => perfil && alternar(fila.itemId, perfil)}
                        >
                          <span className={styles.fichaNombre}>{fila.descripcion}</span>
                          {!razonComun && razones[i] ? (
                            <span className={styles.fichaRazon}>{razones[i]}</span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                  {abiertaAqui ? detalle(abiertaAqui, "Este renglón no se cobra en ningún kit.") : null}
                </div>
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}
