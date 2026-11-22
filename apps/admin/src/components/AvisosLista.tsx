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
