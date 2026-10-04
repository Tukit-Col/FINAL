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
//
// Una fila que no tiene producto en NINGUN kit (un hueco, un uniforme, lo que
// se consigue por su cuenta) no se pinta como tres celdas vacias: lo pendiente
// sale arriba como aviso de ancho completo con su razon, y lo que ni se busca
// en el catalogo baja al final como fichas compactas agrupadas por motivo.

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
  // Kits sin acudiente (vista previa, canónicos): el recomendado sigue sirviendo
  // de columna de referencia, pero no se rotula, porque nadie lo eligió.
  sinRotuloRecomendado?: boolean;
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

export default function MatrizComparacion({
  trabajoId,
  kits,
  recomendado,
  sinRotuloRecomendado = false,
}: Props) {
  const rotulado = sinRotuloRecomendado ? undefined : recomendado;
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

  // Secciones en el orden que duele primero, vacias fuera. Cada una cae en uno
  // de tres bloques segun si alguna de sus filas tiene producto en algun kit.
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

  // Con un solo hijo (o la referencia "preview" del revisor) la insignia del
  // hijo se repite en cada renglon sin decir nada: solo sale si hay varios.
  const hijos = new Set([...filasPorItem.values()].map((f) => f.hijo).filter(Boolean));
  const mostrarHijo = hijos.size > 1;

  function alternar(itemId: string, perfil: PerfilKit): void {
    setAbierta((previa) =>
      previa && previa.itemId === itemId && previa.perfil === perfil
        ? null
        : { itemId, perfil },
    );
  }

  // Una fila sin producto se edita desde la linea del perfil recomendado: la
  // resolucion es del item, asi que cualquiera de los tres sirve.
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

        {celdaAbierta
          ? detalle(
              fila,
              `Editando ${celdaAbierta.perfil}. Cambiar de producto se guarda solo en este kit y recalcula su total; confirmar el elegido vale para el concepto en los tres.`,
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
            <p>Sin producto en ningún kit. Lo que decidas aquí vale para los tres.</p>
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
                    <button
                      type="button"
                      className={activa ? styles.avisoBotonActivo : styles.avisoBoton}
                      aria-expanded={activa}
                      disabled={!perfil}
                      onClick={() => perfil && alternar(fila.itemId, perfil)}
                    >
                      {activa ? "Cerrar" : "Resolver"}
                    </button>
                  </div>
                  {detalle(fila, "Resolver este renglón lo deja igual en los tres kits.")}
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
              pasen. Pulsa uno si hay que corregirlo.
            </p>
          </header>
          <div className={styles.fueraGrupos}>
            {seccionesFuera.map(({ clase, filas }) => {
              // Si todas las fichas del grupo comparten la razon (lo comun:
              // "los uniformes todavia no los surtimos") se dice una vez arriba.
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
                          disabled={!perfil}
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
