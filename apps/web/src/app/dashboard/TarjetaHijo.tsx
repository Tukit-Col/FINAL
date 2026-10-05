"use client";

// La tarjeta de un hijo en "Perfiles de hijos", con sus dos acciones:
// - Cambiar colegio: colegio y grado nuevos. Identidad retira la matrícula vieja
//   y crea la nueva con el mismo apodo, todo o nada (un grado inválido no toca
//   nada).
// - Quitar: pide confirmación en la misma tarjeta. No borra datos: cierra el
//   vínculo con la cuenta y retira la matrícula (ADR 0031). Las solicitudes y
//   pedidos que ya existen siguen ahí.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import { FalloApi, cambiarHijo, quitarHijo } from "@/lib/api-navegador";
import styles from "./Dashboard.module.css";

interface Props {
  matriculaId: string;
  titulo: string;
  colegioId: string;
  colegioNombre: string;
  grado: string;
  colegios: { colegio_id: string; nombre: string }[];
  grados: readonly string[];
}

export default function TarjetaHijo({
  matriculaId,
  titulo,
  colegioId,
  colegioNombre,
  grado,
  colegios,
  grados,
}: Props) {
  const router = useRouter();
  const [modo, setModo] = useState<"ver" | "editar" | "quitar">("ver");
  const [colegioNuevo, setColegioNuevo] = useState(colegioId);
  const [gradoNuevo, setGradoNuevo] = useState(grado);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ejecutar(accion: () => Promise<void>, fallo: string) {
    setOcupado(true);
    setError(null);
    try {
      await accion();
      setModo("ver");
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloApi ? causa.message : fallo);
    } finally {
      setOcupado(false);
    }
  }

  const sinCambios = colegioNuevo === colegioId && gradoNuevo === grado;

  return (
    <li className={styles.hijoCard}>
      <span className={styles.hijoApodo}>{titulo}</span>

      {modo === "editar" ? (
        <form
          className={styles.hijoForm}
          onSubmit={(e) => {
            e.preventDefault();
            void ejecutar(
              () => cambiarHijo(matriculaId, { colegio_id: colegioNuevo, grado: gradoNuevo }),
              "No pudimos cambiar el colegio.",
            );
          }}
        >
          <label className={styles.hijoCampo}>
            Colegio
            <select value={colegioNuevo} onChange={(e) => setColegioNuevo(e.target.value)}>
              {colegios.map((c) => (
                <option key={c.colegio_id} value={c.colegio_id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.hijoCampo}>
            Grado
            <select value={gradoNuevo} onChange={(e) => setGradoNuevo(e.target.value)}>
              {grados.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
          <div className={styles.hijoAcciones}>
            <button type="submit" className={styles.btnPagar} disabled={ocupado || sinCambios}>
              {ocupado ? "Guardando…" : "Guardar"}
            </button>
            <button
              type="button"
              className={styles.btnCancelar}
              disabled={ocupado}
              onClick={() => {
                setModo("ver");
                setColegioNuevo(colegioId);
                setGradoNuevo(grado);
                setError(null);
              }}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <>
          <span className={styles.hijoMeta}>{colegioNombre}</span>
          <span className={styles.hijoMeta}>{grado}</span>
        </>
      )}

      {modo === "quitar" && (
        <div className={styles.confirmacion} role="alertdialog" aria-label={`Quitar a ${titulo}`}>
          <p>
            ¿Quitar a <strong>{titulo}</strong> de tu cuenta? Sus solicitudes y pedidos no se
            borran.
          </p>
          <div className={styles.hijoAcciones}>
            <button
              type="button"
              className={styles.btnPeligro}
              disabled={ocupado}
              onClick={() => void ejecutar(() => quitarHijo(matriculaId), "No pudimos quitarlo.")}
            >
              {ocupado ? "Quitando…" : "Sí, quitar"}
            </button>
            <button
              type="button"
              className={styles.btnCancelar}
              disabled={ocupado}
              onClick={() => setModo("ver")}
            >
              No
            </button>
          </div>
        </div>
      )}

      {modo === "ver" && (
        <div className={styles.accionesDiscretas}>
          <button type="button" className={styles.accionDiscreta} onClick={() => setModo("editar")}>
            <Pencil size={13} aria-hidden /> Cambiar colegio
          </button>
          <button
            type="button"
            className={`${styles.accionDiscreta} ${styles.accionDiscretaPeligro}`}
            onClick={() => setModo("quitar")}
          >
            <Trash2 size={13} aria-hidden /> Quitar
          </button>
        </div>
      )}

      {error && (
        <span className={styles.errorPedido} role="alert">
          {error}
        </span>
      )}
    </li>
  );
}
