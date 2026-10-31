// "Para revisar" — los avisos de la lista verificada de un grado.
//
// La revision automatica deja decisiones que solo una persona puede tomar: un
// renglon que parece repetir a otro, uno que nombra varios valores de un
// atributo (y por eso no se exigio ninguno) y uno que pide algo que ningun
// producto del catalogo cumple. Cada aviso trae su accion:
//
//  - Posible repetido: «Es el mismo: no comprar» publica una version nueva con
//    ese renglon como "no se compra" (los kits se rearman); «Son distintos» lo
//    descarta y no vuelve a salir.
//  - Revisar atributo: lleva a la linea; «Está bien así» lo descarta.
//  - Sin producto: «Agregar útil» abre el alta del catálogo con el concepto y
//    el texto ya puestos; «Ocultar» lo descarta.
//
// Cliente porque las acciones son interactivas; tras cada una se refresca la
// pagina (Server Component) para que los avisos y los kits salgan del backend.

"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { AvisoLista } from "@tukit/contrato";
import { descartarAviso, FalloListas, noComprarRepetido } from "@/lib/api-listas";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  versionId: string;
  avisos: AvisoLista[];
}

const TITULO: Record<AvisoLista["tipo"], string> = {
  posible_repetido: "Posible repetido",
  revisar_atributo: "Revisar atributo",
  sin_producto: "Sin producto",
};

function exigeComoTexto(exige: Record<string, unknown>): string {
  const partes = Object.entries(exige).map(([k, v]) => `${k} = ${String(v)}`);
  return partes.length ? partes.join(", ") : "el concepto no tiene productos";
}

/** El alta de un útil con el concepto y la búsqueda ya puestos. */
function enlaceAgregarUtil(aviso: AvisoLista): string {
  const parametros = new URLSearchParams({ pestana: "util", consulta: aviso.texto });
  if (aviso.concepto_codigo) parametros.set("concepto", aviso.concepto_codigo);
  return `/catalogo?${parametros.toString()}`;
}

export default function AvisosLista({ versionId, avisos }: Props) {
  const router = useRouter();
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function hacer(clave: string, accion: () => Promise<unknown>) {
    setOcupado(clave);
    setError(null);
    try {
      await accion();
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No pudimos guardar la decisión.");
    } finally {
      setOcupado(null);
    }
  }

  if (avisos.length === 0) return null;

  return (
    <section className={styles.avisos} aria-labelledby="titulo-avisos">
      <div className={styles.panelCabecera}>
        <h2 id="titulo-avisos">Para revisar</h2>
        <span className={styles.panelConteo}>
          <span className="cifra">{avisos.length}</span>
        </span>
      </div>
      {error ? <p className={styles.pistaError}>{error}</p> : null}
      <ul className={styles.listaAvisos}>
        {avisos.map((aviso) => {
          const llave = `${aviso.item_id}:${aviso.clave}`;
          const deshabilitado = ocupado !== null;
          return (
            <li key={llave} className={styles.aviso}>
              <span className={`${styles.avisoTipo} ${styles[`aviso_${aviso.tipo}`] ?? ""}`}>
                {TITULO[aviso.tipo]}
              </span>
              <div className={styles.avisoCuerpo}>
                <p className={styles.avisoTexto}>
                  <a href={`#renglon-${aviso.orden}`} className="cifra">
                    #{aviso.orden}
                  </a>{" "}
                  «{aviso.texto}»
                </p>
                <p className={styles.avisoDetalle}>
                  {aviso.tipo === "posible_repetido" && (
                    <>
                      Se parece a <a href={`#renglon-${aviso.repite_a}`}>#{aviso.repite_a}</a>
                      {aviso.texto_repetido ? ` «${aviso.texto_repetido}»` : ""}.
                    </>
                  )}
                  {aviso.tipo === "revisar_atributo" && (
                    <>
                      Nombra varios valores de <strong>{aviso.atributo}</strong>; no se exigió
                      ninguno. Si sabes cuál es, fíjalo con «Editar (nueva versión)» en
                      «Atributos que se exigen» del renglón.
                    </>
                  )}
                  {aviso.tipo === "sin_producto" && (
                    <>
                      Ningún producto de {aviso.concepto_nombre ?? "su concepto"} cumple:{" "}
                      {exigeComoTexto(aviso.exige)}. Si algo de eso no debería exigirse, se
                      cura con «Editar (nueva versión)» en «Atributos que se exigen».
                    </>
                  )}
                </p>
              </div>
              <div className={styles.avisoAcciones}>
                {aviso.tipo === "posible_repetido" && (
                  <>
                    <button
                      type="button"
                      className={styles.botonPrincipal}
                      disabled={deshabilitado}
                      onClick={() =>
                        hacer(llave, () =>
                          noComprarRepetido(versionId, aviso.item_id, aviso.repite_a),
                        )
                      }
                    >
                      {ocupado === llave ? "Publicando…" : "Es el mismo: no comprar"}
                    </button>
                    <button
                      type="button"
                      className={styles.botonSecundario}
                      disabled={deshabilitado}
                      onClick={() =>
                        hacer(llave, () => descartarAviso(versionId, aviso.item_id, aviso.clave))
                      }
                    >
                      Son distintos
                    </button>
                  </>
                )}
                {aviso.tipo === "revisar_atributo" && (
                  <>
                    <a className={styles.botonSecundario} href={`#renglon-${aviso.orden}`}>
                      Ir a la línea
                    </a>
                    <button
                      type="button"
                      className={styles.botonSecundario}
                      disabled={deshabilitado}
                      onClick={() =>
                        hacer(llave, () => descartarAviso(versionId, aviso.item_id, aviso.clave))
                      }
                    >
                      Está bien así
                    </button>
                  </>
                )}
                {aviso.tipo === "sin_producto" && (
                  <>
                    <Link className={styles.botonPrincipal} href={enlaceAgregarUtil(aviso)}>
                      Agregar útil
                    </Link>
                    <button
                      type="button"
                      className={styles.botonSecundario}
                      disabled={deshabilitado}
                      onClick={() =>
                        hacer(llave, () => descartarAviso(versionId, aviso.item_id, aviso.clave))
                      }
                    >
                      Ocultar
                    </button>
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
