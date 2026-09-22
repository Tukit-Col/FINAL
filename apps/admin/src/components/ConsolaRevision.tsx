"use client";

// El cuerpo de la revision: elegir cual de los tres kits se mira y recorrer
// sus lineas (AD-03, AD-04).
//
// El admin SI ve los kits antes de publicar —esa es su tarea— mientras que el
// §4 se los oculta al acudiente hasta que alguien los apruebe.

import { useState } from "react";
import type { ClaseLinea, PerfilKit, TrabajoAdmin } from "@tukit/contrato";
import {
  agruparPorClase,
  formatearPesos,
  ORDEN_SECCIONES,
  TITULO_CLASE,
} from "@tukit/contrato";
import { esPendiente, porcentaje } from "@/lib/formato";
import LineaRevision from "./LineaRevision";
import styles from "./Revision.module.css";

interface Props {
  trabajo: TrabajoAdmin;
}

// Que hay que hacer con cada seccion, dicho para quien revisa. El titulo de
// arriba sigue siendo el `TITULO_CLASE` del contrato —el mismo que lee el
// acudiente— para que admin y soporte usen las mismas palabras cuando hablan
// del mismo renglon.
const QUE_HACER: Record<ClaseLinea, string> = {
  hueco: "Se entendió qué pide y el catálogo no lo tiene. Da de alta un producto (AD-07) o déjala marcada con su motivo.",
  sin_match: "No se entendió el renglón. Decide qué es, o márcalo sin coincidencia diciendo por qué.",
  pendiente_revision: "Hay candidatos y ninguno domina. La persona que decide eres tú.",
  licencia_digital: "Pago externo: no entra al carrito. Solo hay que verificar el enlace.",
  informativa: "La vende el colegio o la editorial. Se muestra y no se cobra (§5.1.1).",
  diferido: "El colegio la va a pedir durante el año. Queda pendiente y reabre el trabajo.",
  no_comprar: "El colegio indica usar el que ya hay en casa. Cantidad cero.",
  fuera_de_alcance: "Uniformes: declarados fuera del alcance de la v1.",
  comprable: "Ya resueltas y dentro del total. Van plegadas; se abren si hay que cambiar algo.",
};

export default function ConsolaRevision({ trabajo }: Props) {
  const [perfil, setPerfil] = useState<PerfilKit>(trabajo.recomendado?.perfil ?? "Ahorrador");
  const kit = trabajo.kits.find((k) => k.perfil === perfil) ?? trabajo.kits[0];

  if (!kit) {
    return (
      <p className={styles.vacio}>
        Este trabajo todavía no tiene kits armados. Vuelve cuando el pipeline termine.
      </p>
    );
  }

  const grupos = agruparPorClase(kit.lineas);
  // `ORDEN_SECCIONES` ya pone primero lo que duele y deja lo comprable al
  // final, que es exactamente el orden que necesita quien revisa. Reordenar
  // aqui seria empezar a desincronizar las dos apps.
  const secciones = ORDEN_SECCIONES.map((clase) => ({
    clase,
    lineas: grupos.get(clase) ?? [],
  })).filter((seccion) => seccion.lineas.length > 0);

  return (
    <section className={styles.consola}>
      <div className={styles.selector} role="group" aria-label="Perfil del kit que se revisa">
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
          <strong>Se le va a marcar {trabajo.recomendado.perfil}:</strong>{" "}
          {trabajo.recomendado.razon}{" "}
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
            <p>{QUE_HACER[clase]}</p>
          </header>
          <div className={styles.lineas}>
            {lineas.map((linea) => (
              <LineaRevision
                key={linea.item_id}
                trabajoId={trabajo.trabajo_id}
                linea={linea}
                clase={clase}
              />
            ))}
          </div>
        </section>
      ))}
    </section>
  );
}
