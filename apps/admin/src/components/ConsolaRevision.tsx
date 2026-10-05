"use client";

// El cuerpo de la revision (AD-04, rediseño §7). Antes eran pestañas: un kit a
// la vez, y para comparar económico→premium había que ir y volver. Ahora es una
// MATRIZ: una fila por concepto, tres columnas (Ahorrador/Fan/Premium), y el
// cambio de nivel entre kits se ve de un vistazo. La decisión sigue siendo por
// item (una RESOLUCION por `item_crudo_id`, compartida entre kits), así que
// editar una celda vale para los tres.
//
// El admin SI ve los kits antes de publicar —esa es su tarea— mientras que el
// §4 se los oculta al acudiente hasta que alguien los apruebe.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCheck } from "lucide-react";
import type { LineaKit, TrabajoAdmin } from "@tukit/contrato";
import { agruparPorClase, formatearPesos } from "@tukit/contrato";
import { FalloApi, validarLinea } from "@/lib/api-navegador";
import MatrizComparacion from "./MatrizComparacion";
import PersonajeFan from "./PersonajeFan";
import styles from "./Revision.module.css";

interface Props {
  trabajo: TrabajoAdmin;
  // Franquicias del catálogo para el interruptor de personaje del kit Fan.
  personajes: string[];
}

// Las líneas que se pueden validar en lote: las de la clase que el sistema dejó
// ambigua (`pendiente_revision`) con un producto ya elegido. Confirmar el
// elegido no pide decidir nada, así que es lo único seguro de hacer a varias a
// la vez. Se toman del kit recomendado —da igual cuál, el item_id es el mismo—.
function pendientesConElegido(lineas: LineaKit[]): LineaKit[] {
  const grupos = agruparPorClase(lineas);
  return (grupos.get("pendiente_revision") ?? []).filter(
    (l) => l.producto_elegido !== null && l.producto_elegido !== undefined,
  );
}

export default function ConsolaRevision({ trabajo, personajes }: Props) {
  const router = useRouter();
  const [enLote, setEnLote] = useState(false);
  const [avisoLote, setAvisoLote] = useState<string | null>(null);
  const [errorLote, setErrorLote] = useState<string | null>(null);

  if (trabajo.kits.length === 0) {
    return (
      <p className={styles.vacio}>
        Este trabajo todavía no tiene kits armados. Vuelve cuando el pipeline termine.
      </p>
    );
  }

  // Un kit de referencia para lo que es común a los tres: consolidaciones y las
  // líneas por confirmar en lote (item_id compartido). El recomendado si existe.
  const kitRef =
    trabajo.kits.find((k) => k.perfil === trabajo.recomendado?.perfil) ?? trabajo.kits[0]!;
  const masivas = pendientesConElegido(kitRef.lineas);
  // Las vistas previas de onboarding y los canónicos de una lista aprobada se
  // arman sin acudiente ni preferencias: `recomendar` les pone la razón por
  // omisión ("Elegiste precio…"), que aquí sería falsa.
  const sinAcudiente =
    trabajo.origen === "preview_onboarding" || trabajo.origen === "canonico_lista";

  async function validarPendientes(): Promise<void> {
    if (masivas.length === 0) return;
    setEnLote(true);
    setAvisoLote(null);
    setErrorLote(null);
    let hechas = 0;
    try {
      // En secuencia y no en paralelo: el backend recalcula el estado del
      // trabajo en cada validación y una ráfaga simultánea pelearía por ese
      // recálculo. Si una falla, se sabe cuántas se alcanzaron a guardar.
      for (const linea of masivas) {
        // Sin sku: "confirmo el que el sistema eligió".
        await validarLinea(trabajo.trabajo_id, linea.item_id, {});
        hechas += 1;
      }
      setAvisoLote(`${hechas} línea(s) validadas con el producto que eligió el sistema.`);
      router.refresh();
    } catch (causa) {
      setErrorLote(
        `Se validaron ${hechas} de ${masivas.length}. ${
          causa instanceof FalloApi ? causa.message : "No pudimos validar el resto."
        }`,
      );
      router.refresh();
    } finally {
      setEnLote(false);
    }
  }

  return (
    <section className={styles.consola}>
      {sinAcudiente ? (
        <p className={styles.razonRecomendacion}>
          <strong>Kits del grado, sin acudiente.</strong> Salen de la lista del colegio y nadie
          declaró preferencias, así que no se marca ninguno: a cada acudiente se le marca el
          suyo cuando pide su kit.
        </p>
      ) : trabajo.recomendado ? (
        <p className={styles.razonRecomendacion}>
          <strong>Se le va a marcar {trabajo.recomendado.perfil}:</strong>{" "}
          {trabajo.recomendado.razon}{" "}
          {/* `null` es "no declaró presupuesto": solo `false` es pasarse. */}
          {trabajo.recomendado.dentro_de_presupuesto === false
            ? "Ojo: queda fuera del presupuesto declarado."
            : ""}
        </p>
      ) : null}

      {masivas.length > 0 ? (
        <div className={styles.barraLote}>
          <span className={styles.loteConteo}>
            {masivas.length} línea(s) con un producto elegido por el sistema, sin confirmar.
          </span>
          <div className={styles.loteBotones}>
            <button
              type="button"
              className={styles.principal}
              disabled={enLote}
              onClick={() => void validarPendientes()}
            >
              <CheckCheck size={15} strokeWidth={2.6} aria-hidden="true" />
              {enLote ? "Validando…" : `Confirmar las ${masivas.length} elegidas`}
            </button>
          </div>
          {avisoLote ? <p className={styles.exito}>{avisoLote}</p> : null}
          {errorLote ? <p className={styles.error}>{errorLote}</p> : null}
        </div>
      ) : null}

      {kitRef.consolidaciones.length > 0 ? (
        <details className={styles.consolidaciones}>
          <summary>
            {kitRef.consolidaciones.length} consolidaciones entre hermanos
            <span className="cifra">
              {formatearPesos(kitRef.consolidaciones.reduce((t, c) => t + c.ahorro, 0))} de ahorro
            </span>
          </summary>
          <ul>
            {kitRef.consolidaciones.map((consolidacion) => (
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

      {(() => {
        // El personaje es una preferencia del acudiente (ADR 0030): una lista que
        // subio el colegio, o el canonico que sale de ella, no tiene a quien
        // preguntarle, asi que aqui no se elige. Un Fan viejo de antes de esa
        // regla se ve, pero no se toca.
        const fan = trabajo.kits.find((k) => k.perfil === "Fan");
        return fan && !sinAcudiente && personajes.length > 0 ? (
          <PersonajeFan trabajoId={trabajo.trabajo_id} fan={fan} personajes={personajes} />
        ) : null;
      })()}

      <MatrizComparacion
        trabajoId={trabajo.trabajo_id}
        kits={trabajo.kits}
        recomendado={trabajo.recomendado?.perfil}
        sinRotuloRecomendado={sinAcudiente}
      />
    </section>
  );
}
