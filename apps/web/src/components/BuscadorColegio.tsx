"use client";

import { useCallback, useId, useMemo, useState } from "react";
import { Search, School, Pencil } from "lucide-react";
import {
  buscarColegios,
  imagenesPorDane,
  logoDeColegio,
  normalizarBusqueda,
  prepararBusqueda,
  type Colegio,
  type EntradaDirectorio,
} from "@tukit/contrato";
import LogoColegio from "@/components/LogoColegio";
import styles from "@/app/empezar/Empezar.module.css";

let directorioPromesa: Promise<EntradaDirectorio[]> | null = null;
function cargarDirectorio(): Promise<EntradaDirectorio[]> {
  if (!directorioPromesa) {
    directorioPromesa = fetch("/directorio-colegios.json")
      .then((r) => (r.ok ? (r.json() as Promise<EntradaDirectorio[]>) : []))
      .catch(() => []);
  }
  return directorioPromesa;
}

function metaAliado(c: Colegio): string {
  return c.grados.length === 0
    ? "Sin lista verificada · sube el archivo"
    : `${c.grados.length} ${c.grados.length === 1 ? "grado verificado" : "grados verificados"}`;
}

export default function BuscadorColegio({
  colegiosAliados,
  colegioId,
  colegioDane,
  colegioNombre,
  onElegirAliado,
  onElegirDirectorio,
  onEscribir,
  onCambiar,
  soloAliados = false,
  autoFocus = false,
}: {
  colegiosAliados: Colegio[];
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  onElegirAliado: (colegioId: string) => void;
  onElegirDirectorio: (entrada: { dane: string; nombre: string }) => void;
  onEscribir: (nombre: string) => void;
  onCambiar: () => void;
  soloAliados?: boolean;
  autoFocus?: boolean;
}) {
  const [directorio, setDirectorio] = useState<EntradaDirectorio[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const idBuscador = useId();
  const asegurarCargado = useCallback(() => {
    if (directorio.length === 0) cargarDirectorio().then(setDirectorio);
  }, [directorio.length]);

  const preparada = useMemo(
    () => prepararBusqueda(colegiosAliados, directorio),
    [colegiosAliados, directorio],
  );
  const imagenes = useMemo(() => imagenesPorDane(directorio), [directorio]);

  const qn = normalizarBusqueda(busqueda.trim());
  const resultados = useMemo(() => {
    const { colegios, directorio: dir } = buscarColegios(preparada, busqueda);
    return { aliados: colegios, directorio: dir };
  }, [preparada, busqueda]);

  if (colegioId || colegioNombre) {
    const aliado = colegioId ? colegiosAliados.find((c) => c.colegio_id === colegioId) : undefined;
    const nombre = aliado?.nombre ?? colegioNombre;
    return (
      <div className={styles.colegioBloque}>
        <span className={styles.campoRotulo}>Busca el colegio de tu hijo</span>
        <div className={`${styles.tarjetaColegio} ${styles.colegioActivo}`}>
          <span className={styles.logoColegio} aria-hidden="true">
            <LogoColegio
              src={
                aliado
                  ? logoDeColegio(aliado, imagenes)
                  : (colegioDane && imagenes.get(colegioDane)) || null
              }
              nombre={nombre}
              claseIniciales={styles.logoIniciales}
            />
          </span>
          <span className={styles.colegioTexto}>
            <span className={styles.colegioNombre}>{nombre}</span>
            <span className={styles.colegioMeta}>
              {aliado
                ? metaAliado(aliado)
                : colegioDane
                  ? `Directorio de Bogotá · DANE ${colegioDane}`
                  : "Escrito a mano · lo verificamos nosotros"}
            </span>
          </span>
          <button
            type="button"
            className={styles.cambiarColegio}
            onClick={() => {
              onCambiar();
              setBusqueda("");
            }}
          >
            Cambiar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.colegioBloque}>
      <label htmlFor={idBuscador} className={`${styles.campoRotulo} ${styles.rotuloColegio}`}>
        Busca el colegio de tu hijo
      </label>
      <div className={`${styles.buscador} ${styles.buscadorPrincipal}`}>
        <Search size={20} strokeWidth={2.4} aria-hidden="true" />
        <input
          id={idBuscador}
          aria-describedby={`${idBuscador}-ayuda`}
          type="text"
          value={busqueda}
          onFocus={asegurarCargado}
          onChange={(e) => {
            asegurarCargado();
            setBusqueda(e.target.value);
          }}
          placeholder="Ej. Gimnasio Los Cerros o Chía"
          autoComplete="off"
          autoFocus={autoFocus}
        />
      </div>
      <p id={`${idBuscador}-ayuda`} className={styles.ayudaColegio}>
        Escribe el nombre o el municipio.
      </p>
      {qn.length >= 3 && (
        <div className={styles.listaColegios} role="listbox" aria-label="Colegios">
          {resultados.aliados.map(({ colegio, etiqueta }) => (
            <button
              key={`aliado-${colegio.colegio_id}`}
              type="button"
              role="option"
              aria-selected="false"
              className={styles.tarjetaColegio}
              onClick={() => onElegirAliado(colegio.colegio_id)}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                <LogoColegio
                  src={logoDeColegio(colegio, imagenes)}
                  nombre={colegio.nombre}
                  claseIniciales={styles.logoIniciales}
                />
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{etiqueta}</span>
                <span className={styles.colegioMeta}>{metaAliado(colegio)}</span>
              </span>
            </button>
          ))}
          {!soloAliados && resultados.directorio.map((e) => (
            <button
              key={`dir-${e.dane}`}
              type="button"
              role="option"
              aria-selected="false"
              className={styles.tarjetaColegio}
              onClick={() => onElegirDirectorio({ dane: e.dane, nombre: e.nombre })}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                <LogoColegio
                  src={e.imageURL}
                  nombre={e.nombre}
                  claseIniciales={styles.logoIniciales}
                />
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{e.nombre}</span>
                <span className={styles.colegioMeta}>{e.localidad}</span>
              </span>
            </button>
          ))}
          {resultados.aliados.length === 0 && (soloAliados || resultados.directorio.length === 0) && (
            <p className={styles.sinColegios} role="status">
              <School size={18} strokeWidth={2} aria-hidden="true" />
              No encontramos “{busqueda.trim()}”. Revisa la ortografía{soloAliados ? "." : " o úsalo tal cual."}
            </p>
          )}
          {!soloAliados && (
          <button
            type="button"
            className={styles.escribirColegio}
            onClick={() => onEscribir(busqueda.trim())}
          >
            <Pencil size={15} strokeWidth={2.4} aria-hidden="true" />
            No lo encuentro: usar “{busqueda.trim()}” tal cual
          </button>
          )}
        </div>
      )}
      {qn.length > 0 && qn.length < 3 && (
        <p className={styles.sinColegios}>
          <School size={18} strokeWidth={2} aria-hidden="true" />
          Escribe al menos tres letras del nombre.
        </p>
      )}
    </div>
  );
}
