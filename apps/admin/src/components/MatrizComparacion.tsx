"use client";

// La matriz de comparacion (AD-04, rediseño §7): una fila por concepto, tres
// columnas —Ahorrador / Fan / Premium— y en cada celda el producto que el
// optimizador eligio para ESE kit, con su `nivel` (economico/confiable/
// premium). Asi "notas adhesivas" es UNA fila y se ve de un vistazo como sube
// de economico a premium entre kits, que es justo lo que la consola de pestañas
// escondia.
//
// La decision sigue siendo por item, no por kit: el backend valida contra una
// sola RESOLUCION por `item_crudo_id` (= `item_id`), compartida entre los tres
// kits. Por eso la celda solo MUESTRA; al hacer clic se despliega el editor de
// esa linea (`LineaRevision`, reutilizado tal cual) para actuar. El item_id es
// el mismo en las tres columnas, asi que la fila los une sin tocar el backend.

import { useState } from "react";
import type { ClaseLinea, Kit, LineaKit, PerfilKit } from "@tukit/contrato";
import { agruparPorClase, formatearPesos, ORDEN_SECCIONES, TITULO_CLASE } from "@tukit/contrato";
import { tituloClaseAdmin } from "@/lib/consola";
import { esPendiente } from "@/lib/formato";
import LineaRevision from "./LineaRevision";
import styles from "./Revision.module.css";

interface Props {
  trabajoId: string;
  kits: Kit[];
  recomendado: PerfilKit | undefined;
}

// El orden de las columnas es el del precio creciente, que es como el acudiente
// las lee y como `KIT.total_cop` las ordena en el backend.
const ORDEN_PERFIL: PerfilKit[] = ["Ahorrador", "Fan", "Premium"];

interface Fila {
  itemId: string;
  clase: ClaseLinea;
  descripcion: string;
  hijo: string | undefined;
  concepto: string | null | undefined;
  // La linea de cada kit para este item. Puede faltar en algun kit (un item
  // que un perfil no incluye), por eso es un mapa parcial.
  porPerfil: Map<PerfilKit, LineaKit>;
}

function nivelDe(linea: LineaKit | undefined): string | null {
  return linea?.producto_elegido?.nivel ?? null;
}

export default function MatrizComparacion({ trabajoId, kits, recomendado }: Props) {
  // (itemId, perfil) de la celda abierta. Una sola a la vez: desplegar todas
  // seria volver al muro de HTML que el `<details>` de `LineaRevision` evita.
  const [abierta, setAbierta] = useState<{ itemId: string; perfil: PerfilKit } | null>(null);

  const perfiles = ORDEN_PERFIL.filter((p) => kits.some((k) => k.perfil === p));

  // Se arma una fila por item_id conservando el orden y la clase de la seccion.
  // La clase se toma de la primera linea que aparezca: es la misma en los tres
  // kits (el estado de resolucion es del item, no del kit).
  const filasPorItem = new Map<string, Fila>();
  for (const kit of kits) {
    for (const linea of kit.lineas) {
      let fila = filasPorItem.get(linea.item_id);
      if (!fila) {
        fila = {
          itemId: linea.item_id,
          clase: "comprable", // se corrige abajo con agruparPorClase
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

  // La clase de cada item la decide el clasificador del contrato, igual que la
  // consola vieja, para no desincronizar sus palabras. Se clasifica una linea
  // representativa (la del perfil recomendado o la primera que haya).
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

  // Secciones en el orden que duele primero, vacias fuera.
  const secciones = ORDEN_SECCIONES.map((clase) => ({
    clase,
    filas: [...filasPorItem.values()].filter((f) => f.clase === clase),
  })).filter((s) => s.filas.length > 0);

  function alternar(itemId: string, perfil: PerfilKit): void {
    setAbierta((previa) =>
      previa && previa.itemId === itemId && previa.perfil === perfil
        ? null
        : { itemId, perfil },
    );
  }

  return (
    <div className={styles.matriz}>
      <div className={styles.matrizCabecera} style={{ ["--columnas" as string]: perfiles.length }}>
        <span className={styles.matrizEsquina}>Concepto</span>
        {perfiles.map((perfil) => {
          const kit = kits.find((k) => k.perfil === perfil);
          return (
            <span
              key={perfil}
              className={`${styles.matrizColTitulo} ${perfil === recomendado ? styles.matrizColReco : ""}`}
            >
              <span className={styles.perfilNombre}>
                {perfil}
                {perfil === recomendado ? <span className={styles.recomendado}>recomendado</span> : null}
              </span>
              {kit ? <span className={`${styles.perfilTotal} cifra`}>{formatearPesos(kit.total)}</span> : null}
            </span>
          );
        })}
      </div>

      {secciones.map(({ clase, filas }) => (
        <section key={clase} className={styles.matrizSeccion}>
          <h3 className={`${styles.matrizSeccionTitulo} ${esPendiente(clase) ? styles.seccionPendiente : ""}`}>
            {tituloClaseAdmin(clase, TITULO_CLASE)}
            <span className={styles.conteo}>{filas.length}</span>
          </h3>

          {filas.map((fila) => {
            const celdaAbierta = abierta && abierta.itemId === fila.itemId ? abierta : null;
            const lineaAbierta = celdaAbierta ? fila.porPerfil.get(celdaAbierta.perfil) : undefined;
            return (
              <div key={fila.itemId} className={styles.matrizFilaBloque}>
                <div
                  className={styles.matrizFila}
                  style={{ ["--columnas" as string]: perfiles.length }}
                >
                  <div className={styles.matrizConcepto}>
                    <span className={styles.matrizDescripcion}>{fila.descripcion}</span>
                    <span className={styles.matrizMetaConcepto}>
                      {fila.concepto ? <code>{fila.concepto}</code> : null}
                      {fila.hijo ? <span className={styles.hijo}>{fila.hijo}</span> : null}
                    </span>
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
                        disabled={!linea}
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
                              <span className={styles.celdaNombre}>{producto.nombre}</span>
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
                              {formatearPesos(linea?.subtotal_linea ?? null)}
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

                {celdaAbierta && lineaAbierta ? (
                  <div className={styles.matrizDetalle}>
                    <p className={styles.matrizDetalleNota}>
                      Editando <strong>{celdaAbierta.perfil}</strong>. Cambiar de producto se guarda
                      solo en este kit y recalcula su total; confirmar el elegido vale para el
                      concepto en los tres.
                    </p>
                    <LineaRevision
                      key={`${fila.itemId}-${celdaAbierta.perfil}`}
                      trabajoId={trabajoId}
                      linea={lineaAbierta}
                      clase={fila.clase}
                      perfil={celdaAbierta.perfil}
                    />
                  </div>
                ) : null}
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
