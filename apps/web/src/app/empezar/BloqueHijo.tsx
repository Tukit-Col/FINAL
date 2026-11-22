import { Check } from "lucide-react";
import {
  EXTENSIONES_ACEPTADAS,
  GRADOS_CANONICOS,
  formatearTamano,
  type Colegio,
} from "@tukit/contrato";
import BuscadorColegio from "@/components/BuscadorColegio";
import type { HijoFormulario, Modo } from "@/lib/formulario-empezar";
import SelectorPersonaje from "./SelectorPersonaje";
import styles from "./Empezar.module.css";

export default function BloqueHijo({
  hijo,
  indice,
  totalHijos,
  modo,
  colegio,
  colegiosAliados,
  surtidos,
  hayError,
  onCambiar,
  onQuitar,
  onElegirArchivo,
}: {
  hijo: HijoFormulario;
  indice: number;
  totalHijos: number;
  modo: Modo;
  colegio: Colegio | undefined;
  colegiosAliados: Colegio[];
  surtidos: string[];
  hayError: boolean;
  onCambiar: (cambio: Partial<HijoFormulario>) => void;
  onQuitar: () => void;
  onElegirArchivo: (elegido: File | undefined) => void;
}) {
  return (
    <fieldset className={styles.hijo}>
      <legend className={styles.leyenda}>
        Hijo {indice + 1}
        {totalHijos > 1 && (
          <button type="button" className={styles.quitar} onClick={onQuitar}>
            Quitar
          </button>
        )}
      </legend>

      <BuscadorColegio
        colegiosAliados={colegiosAliados}
        colegioId={hijo.colegioId}
        colegioDane={hijo.colegioDane}
        colegioNombre={hijo.colegioNombre}
        onElegirAliado={(colegioId) =>
          onCambiar({ colegioId, colegioDane: "", colegioNombre: "", grado: "" })
        }
        onElegirDirectorio={({ dane, nombre }) =>
          onCambiar({ colegioId: "", colegioDane: dane, colegioNombre: nombre, grado: "" })
        }
        onEscribir={(nombre) =>
          onCambiar({ colegioId: "", colegioDane: "", colegioNombre: nombre, grado: "" })
        }
        onCambiar={() => onCambiar({ colegioId: "", colegioDane: "", colegioNombre: "", grado: "" })}
      />

      {(hijo.colegioId || hijo.colegioNombre) &&
        (modo === "nuevo" || (modo === "autenticado" && !hijo.precargado)) && (
          <label className={styles.campo}>
            <span>Apodo de tu hijo (opcional)</span>
            <input
              type="text"
              value={hijo.apodo}
              onChange={(e) => onCambiar({ apodo: e.target.value })}
              placeholder="Escribe el apodo de tu hijo para personalizar tu kit"
              autoComplete="off"
            />
          </label>
        )}
      {modo === "autenticado" && hijo.precargado && hijo.apodo && (
        <p className={styles.apodoPrecargado}>Apodo: {hijo.apodo}</p>
      )}

      {(colegio || hijo.colegioNombre) && (
        <div className={styles.gradoBloque}>
          <span className={styles.campoRotulo}>Grado</span>
          <div className={styles.gradoChips} role="radiogroup" aria-label="Elige el grado">
            {GRADOS_CANONICOS.map((g) => {
              const activo = hijo.grado === g;
              const oficial = Boolean(hijo.colegioId);
              const verificado = oficial && (colegio?.grados.includes(g) ?? false);
              const clase = activo
                ? styles.chipGradoActivo
                : verificado
                  ? styles.chipGradoVerificado
                  : "";
              return (
                <button
                  key={g}
                  type="button"
                  role="radio"
                  aria-checked={activo}
                  aria-label={
                    oficial
                      ? `${g}, ${verificado ? "con lista verificada" : "sin lista verificada"}`
                      : g
                  }
                  title={
                    oficial
                      ? verificado
                        ? "Tiene lista verificada del colegio"
                        : "Sin lista verificada todavía"
                      : undefined
                  }
                  className={`${styles.chipGrado} ${clase}`}
                  onClick={() => onCambiar({ grado: g })}
                >
                  {g}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {colegio && hijo.grado !== "" && !colegio.grados.includes(hijo.grado) && (
        <div className={styles.zonaListaGrado}>
          <span className={styles.campoRotulo}>Subir lista de grado ({hijo.grado})</span>
          <p className={styles.reglaArchivo}>
            Este grado todavía no tiene lista verificada del colegio.
            Adjunta tu lista y la revisamos para armar el kit.
          </p>
          <input
            id={`lista-grado-${hijo.referencia}`}
            type="file"
            className={styles.inputArchivo}
            accept={EXTENSIONES_ACEPTADAS.join(",")}
            onChange={(e) => {
              onElegirArchivo(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <label htmlFor={`lista-grado-${hijo.referencia}`} className={styles.soltar}>
            <strong>Haz clic para elegir el archivo</strong>
            <span>PDF, JPG, PNG o WEBP · hasta 10 MB</span>
          </label>
          {hijo.archivo && (
            <p className={styles.archivoElegido}>
              {hijo.archivo.name} · {formatearTamano(hijo.archivo.size)}
            </p>
          )}
          {hijo.errorArchivo && (
            <p className={styles.errorCampo} role="alert">
              {hijo.errorArchivo}
            </p>
          )}
        </div>
      )}

      {!hijo.colegioId && hijo.colegioNombre && (
        <div className={styles.zonaArchivo}>
          <p className={styles.reglaArchivo}>
            Sube solo las páginas del grado de tu hijo. Si mandas el PDF
            completo del colegio con los trece grados no lo procesamos, porque
            un kit armado con los útiles de otro grado es peor que no tener
            kit.
          </p>
          <input
            id={`archivo-${hijo.referencia}`}
            type="file"
            className={styles.inputArchivo}
            accept={EXTENSIONES_ACEPTADAS.join(",")}
            onChange={(e) => {
              onElegirArchivo(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <label htmlFor={`archivo-${hijo.referencia}`} className={styles.soltar}>
            <strong>Haz clic para elegir el archivo</strong>
            <span>PDF, JPG, PNG o WEBP · hasta 10 MB</span>
          </label>

          {hijo.archivo && (
            <p className={styles.archivoElegido}>
              {hijo.archivo.name} · {formatearTamano(hijo.archivo.size)}
            </p>
          )}
          {hijo.errorArchivo && (
            <p className={styles.errorCampo} role="alert">
              {hijo.errorArchivo}
            </p>
          )}

          {hijo.colegioNombre && hijo.grado && !hayError && (
            <p className={styles.sugerenciaOk} role="status">
              <Check size={16} strokeWidth={3} aria-hidden="true" />
              Con esto revisamos tu lista, armamos tu kit y dejamos {hijo.colegioNombre} ·{" "}
              {hijo.grado} verificado para los demás.
            </p>
          )}
        </div>
      )}

      <SelectorPersonaje
        etiquetaHijo={`Hijo ${indice + 1}`}
        valor={hijo.personajes}
        onChange={(personajes) => onCambiar({ personajes })}
        surtidos={surtidos}
      />
    </fieldset>
  );
}
