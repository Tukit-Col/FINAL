"use client";

import { useState } from "react";
import {
  NO_EXIGIR,
  exigidoDe,
  porAgregar,
  type FilaExigencia,
} from "@/lib/atributos-renglon";
import styles from "@/app/onboarding/Onboarding.module.css";

interface Props {
  itemId: string;
  filas: FilaExigencia[];
  onCambio: (filas: FilaExigencia[]) => void;
  discriminantes: readonly string[];
  porRevisar: readonly string[];
  sugerencias: Record<string, string[]>;
  conceptoCambiado: boolean;
  disabled: boolean;
}

export default function AtributosRenglon({
  itemId,
  filas,
  onCambio,
  discriminantes,
  porRevisar,
  sugerencias,
  conceptoCambiado,
  disabled,
}: Props) {
  const disponibles = porAgregar(filas, discriminantes);
  const [nueva, setNueva] = useState("");

  if (conceptoCambiado) {
    return (
      <div className={styles.campo}>
        <span>Atributos que se exigen</span>
        <p className={styles.atributosNota}>
          Cambiaste el concepto: guarda y vuelve a abrir el renglón para curar los atributos del
          concepto nuevo.
        </p>
      </div>
    );
  }

  if (discriminantes.length === 0 && filas.length === 0) {
    return (
      <div className={styles.campo}>
        <span>Atributos que se exigen</span>
        <p className={styles.atributosNota}>
          El concepto no filtra por atributos: sirve cualquiera de sus productos.
        </p>
      </div>
    );
  }

  function cambiar(clave: string, cambio: Partial<FilaExigencia>) {
    onCambio(filas.map((f) => (f.clave === clave ? { ...f, ...cambio } : f)));
  }

  function quitarCuraduria(fila: FilaExigencia) {
    if (fila.leido === null) onCambio(filas.filter((f) => f.clave !== fila.clave));
    else cambiar(fila.clave, { curado: null });
  }

  function agregar() {
    const clave = nueva || disponibles[0];
    if (!clave) return;
    onCambio([...filas, { clave, leido: null, curado: "", ajena: false, deducido: false }]);
    setNueva("");
  }

  const sinFila = porRevisar.filter((a) => !filas.some((f) => f.clave === a));

  return (
    <div className={styles.campo}>
      <span>Atributos que se exigen</span>
      {filas.length === 0 ? (
        <p className={styles.atributosNota}>
          El texto no dice nada de lo que filtra el concepto: sirve cualquiera de sus productos.
        </p>
      ) : (
        <ul className={styles.atributos}>
          {filas.map((fila) => {
            const exigido = exigidoDe(fila);
            const noExigir = fila.curado === NO_EXIGIR;
            const idSugerencias = `sug-${itemId}-${fila.clave}`;
            return (
              <li key={fila.clave} className={styles.atributo}>
                <div className={styles.atributoCabeza}>
                  <strong>{fila.clave}</strong>
                  <span className={styles.atributoOrigen}>
                    {fila.ajena
                      ? "curado, pero el concepto no filtra por él"
                      : fila.deducido
                        ? "deducido: más de uno"
                        : fila.leido !== null
                          ? `del texto: ${fila.leido}`
                          : "el texto no lo dice"}
                  </span>
                </div>
                {fila.deducido ? (
                  <p className={styles.atributosNota}>
                    El texto no dice cuántos (pide una caja, un kit o va en plural): se exige más de
                    uno. Si ningún juego cumple, vale la pieza suelta.
                  </p>
                ) : null}
                {fila.ajena ? null : (
                  <div className={styles.atributoControles}>
                    <input
                      aria-label={`Valor curado de ${fila.clave}`}
                      value={noExigir ? "" : (fila.curado ?? "")}
                      placeholder={fila.leido ?? "valor"}
                      onChange={(e) => cambiar(fila.clave, { curado: e.target.value })}
                      disabled={disabled || noExigir}
                      list={sugerencias[fila.clave]?.length ? idSugerencias : undefined}
                    />
                    {sugerencias[fila.clave]?.length ? (
                      <datalist id={idSugerencias}>
                        {sugerencias[fila.clave].map((v) => (
                          <option key={v} value={v} />
                        ))}
                      </datalist>
                    ) : null}
                    <label className={styles.atributoCheck}>
                      <input
                        type="checkbox"
                        checked={noExigir}
                        onChange={(e) =>
                          cambiar(fila.clave, { curado: e.target.checked ? NO_EXIGIR : null })
                        }
                        disabled={disabled}
                      />
                      No exigir
                    </label>
                  </div>
                )}
                <div className={styles.atributoPie}>
                  <span className={exigido === null ? styles.atributoNoSeExige : styles.atributoSeExige}>
                    {exigido === null
                      ? "No se exige"
                      : fila.deducido && fila.curado === null
                        ? "Se exige: más de uno"
                        : `Se exige: ${exigido}`}
                    {fila.curado !== null && !fila.ajena ? " · curado" : ""}
                  </span>
                  {fila.curado !== null ? (
                    <button
                      type="button"
                      className={styles.botonMini}
                      onClick={() => quitarCuraduria(fila)}
                      disabled={disabled}
                      title={
                        fila.ajena
                          ? "Quitar esta curaduría: no cambia lo que se exige"
                          : "Quitar la curaduría y exigir lo que dice el texto"
                      }
                    >
                      {fila.ajena ? "Quitar" : fila.leido !== null ? "Volver a lo leído" : "Quitar"}
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {sinFila.length > 0 ? (
        <p className={styles.atributosNota}>
          El texto nombra varios valores de {sinFila.join(", ")}: no se exige ninguno. Agrégalo si
          sabes cuál es.
        </p>
      ) : null}
      {disponibles.length > 0 ? (
        <span className={styles.conceptoFila}>
          <select
            aria-label="Atributo por agregar"
            value={nueva || disponibles[0]}
            onChange={(e) => setNueva(e.target.value)}
            disabled={disabled}
          >
            {disponibles.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <button type="button" className={styles.botonMini} onClick={agregar} disabled={disabled}>
            + Exigir atributo
          </button>
        </span>
      ) : null}
    </div>
  );
}
