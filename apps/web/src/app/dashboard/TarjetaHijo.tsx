"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import type { Colegio } from "@tukit/contrato";
import { FalloApi, cambiarHijo, quitarHijo } from "@/lib/api-navegador";
import { gradosParaCambio } from "@/lib/grados-cambio-colegio";
import BuscadorColegio from "@/components/BuscadorColegio";
import styles from "./Dashboard.module.css";

interface Props {
  matriculaId: string;
  titulo: string;
  colegioId: string;
  colegioNombre: string;
  grado: string;
  colegios: Colegio[];
  grados: readonly string[];
  estado?: { texto: string } | null;
  claseEstado?: string;
  modoInicial?: "ver" | "editar" | "quitar";
}

export default function TarjetaHijo({
  matriculaId,
  titulo,
  colegioId,
  colegioNombre,
  grado,
  colegios,
  grados,
  estado = null,
  claseEstado = "",
  modoInicial = "ver",
}: Props) {
  const router = useRouter();
  const [modo, setModo] = useState<"ver" | "editar" | "quitar">(modoInicial);
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

  const panelRef = useRef<HTMLDivElement>(null);
  const botonEditarRef = useRef<HTMLButtonElement>(null);
  const botonQuitarRef = useRef<HTMLButtonElement>(null);
  const primerRender = useRef(true);
  const aliados = useMemo(
    () => colegios.filter((c) => c.es_partner ?? c.grados.length > 0),
    [colegios],
  );

  useEffect(() => {
    if (primerRender.current) {
      primerRender.current = false;
      return;
    }
    if (modo === "ver") return;
    const raiz = panelRef.current;
    (modo === "quitar"
      ? raiz?.querySelector<HTMLElement>("button:last-of-type")
      : raiz?.querySelector<HTMLElement>("input, button")
    )?.focus();
  }, [modo]);

  function cerrar(devolverA: "editar" | "quitar") {
    setModo("ver");
    setColegioNuevo(colegioId);
    setGradoNuevo(grado);
    setError(null);
    requestAnimationFrame(() =>
      (devolverA === "editar" ? botonEditarRef : botonQuitarRef).current?.focus(),
    );
  }

  const sinCambios = colegioNuevo === colegioId && gradoNuevo === grado;
  const colegioElegido = aliados.find((c) => c.colegio_id === colegioNuevo);
  const ofertaGrados = gradosParaCambio(colegioElegido?.grados ?? [], grados, grado);
  const cambioDeColegio = colegioNuevo !== "" && colegioNuevo !== colegioId;

  return (
    <li className={`${styles.hijoCard} ${modo === "editar" ? styles.hijoCardAncha : ""}`}>
      <div className={styles.hijoCabecera}>
        <span className={styles.hijoAvatar} aria-hidden="true">
          {titulo.trim().charAt(0).toUpperCase()}
        </span>
        <span className={styles.hijoApodo}>{titulo}</span>
        {estado && modo === "ver" && (
          <span className={`${styles.badge} ${claseEstado} ${styles.hijoChip}`}>
            <span className={styles.badgeDot} />
            {estado.texto}
          </span>
        )}
      </div>

      {modo === "editar" ? (
        <form
          className={styles.hijoForm}
          aria-label={`Cambiar el colegio de ${titulo}`}
          onKeyDown={(e) => {
            if (e.key === "Escape" && !ocupado) cerrar("editar");
          }}
          onSubmit={(e) => {
            e.preventDefault();
            if (sinCambios || !colegioNuevo || !gradoNuevo) return;
            void ejecutar(
              () => cambiarHijo(matriculaId, { colegio_id: colegioNuevo, grado: gradoNuevo }),
              "No pudimos cambiar el colegio.",
            );
          }}
        >
          <div ref={panelRef} className={styles.hijoBuscador}>
            <BuscadorColegio
              soloAliados
              autoFocus={colegioNuevo === ""}
              colegiosAliados={aliados}
              colegioId={colegioNuevo}
              colegioDane=""
              colegioNombre={colegioNuevo === colegioId ? colegioNombre : ""}
              onElegirAliado={(id) => {
                setColegioNuevo(id);
                const c = aliados.find((x) => x.colegio_id === id);
                setGradoNuevo(gradosParaCambio(c?.grados ?? [], grados, grado).seleccionado);
              }}
              onElegirDirectorio={() => {}}
              onEscribir={() => {}}
              onCambiar={() => {
                setColegioNuevo("");
                setGradoNuevo(grado);
              }}
            />
          </div>
          {colegioNuevo !== "" && ofertaGrados.sinVerificados && cambioDeColegio ? (
            <p className={styles.hijosError} role="status">
              Este colegio aún no tiene grados con lista verificada.{" "}
              <a href="/empezar">Sube la lista del colegio</a> y la revisamos.
            </p>
          ) : (
            <>
              {cambioDeColegio && ofertaGrados.gradoPerdido && (
                <p className={styles.hijosError} role="status">
                  Este colegio no tiene verificado {grado}. Elige uno de los grados verificados.
                </p>
              )}
              <label className={styles.hijoCampo}>
                Grado
                <select
                  value={gradoNuevo}
                  onChange={(e) => setGradoNuevo(e.target.value)}
                  required
                >
                  {gradoNuevo === "" && (
                    <option value="" disabled>
                      Elige un grado verificado
                    </option>
                  )}
                  {(cambioDeColegio ? ofertaGrados.opciones : grados).map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <div className={styles.hijoAcciones}>
            <button
              type="submit"
              className={styles.btnPagar}
              disabled={ocupado || sinCambios || !colegioNuevo || !gradoNuevo}
            >
              {ocupado ? "Guardando…" : "Guardar"}
            </button>
            <button
              type="button"
              className={styles.btnCancelar}
              disabled={ocupado}
              onClick={() => cerrar("editar")}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <>
          <span className={styles.hijoColegio}>{colegioNombre}</span>
          <span className={styles.hijoGrado}>{grado}</span>
        </>
      )}

      {modo === "quitar" && (
        <div
          ref={panelRef}
          className={styles.confirmacion}
          role="alertdialog"
          aria-label={`Quitar a ${titulo}`}
          onKeyDown={(e) => {
            if (e.key === "Escape" && !ocupado) cerrar("quitar");
          }}
        >
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
              onClick={() => cerrar("quitar")}
            >
              No
            </button>
          </div>
        </div>
      )}

      {modo === "ver" && (
        <div className={styles.accionesDiscretas}>
          <button
            ref={botonEditarRef}
            type="button"
            className={styles.accionDiscreta}
            onClick={() => setModo("editar")}
          >
            <Pencil size={13} aria-hidden /> Cambiar colegio
          </button>
          <button
            ref={botonQuitarRef}
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
