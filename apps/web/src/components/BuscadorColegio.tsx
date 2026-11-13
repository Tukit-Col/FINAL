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

// -------------------------------------------------------- Buscador de colegio
//
// Un ÚNICO buscador por hijo que mezcla dos fuentes que el padre no distingue:
// los colegios aliados de Tukit y el directorio de Bogotá. La búsqueda del
// directorio es del lado del cliente sobre el JSON ya cargado; no pega a ningún
// servicio (decisión: directorio buscable, no sembrado). La lógica (mezcla,
// reconducción por DANE, tope) es la pura de `@tukit/contrato`, la misma que usa
// "Subir lista" en el admin.

// El directorio se carga UNA vez y se comparte entre todos los hijos: es el
// mismo JSON estático. Se memoiza en un módulo para no re-descargar 300 KB por
// cada `<BuscadorColegio>` que se monte.
let directorioPromesa: Promise<EntradaDirectorio[]> | null = null;
function cargarDirectorio(): Promise<EntradaDirectorio[]> {
  if (!directorioPromesa) {
    directorioPromesa = fetch("/directorio-colegios.json")
      .then((r) => (r.ok ? (r.json() as Promise<EntradaDirectorio[]>) : []))
      .catch(() => []);
  }
  return directorioPromesa;
}

// La leyenda que el aliado muestra bajo su nombre, igual en la lista y en la
// tarjeta del elegido: cuántos grados tiene ya con lista verificada.
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
  // Eligió una fila que resultó ser un aliado (por su nombre Tukit o por casar el
  // DANE del directorio con el de un aliado): viaja el `colegio_id` real, así el
  // backend NO lo re-deriva ni lo da de alta de nuevo (evita el duplicado).
  onElegirAliado: (colegioId: string) => void;
  // Eligió una entrada del directorio que NO es aliado: viaja el DANE (que deriva
  // el id) y el nombre; nacerá como colegio nuevo cuando se apruebe su lista.
  onElegirDirectorio: (entrada: { dane: string; nombre: string }) => void;
  // No estaba en ninguna fuente y lo escribió a mano: solo el nombre.
  onEscribir: (nombre: string) => void;
  // Deshace la elección para volver a buscar.
  onCambiar: () => void;
  // Solo colegios aliados (con `colegio_id`): sin directorio ni 'usar tal cual'.
  // Para pantallas que guardan por id (cuenta), donde un colegio sin alta no sirve.
  soloAliados?: boolean;
  autoFocus?: boolean;
}) {
  const [directorio, setDirectorio] = useState<EntradaDirectorio[]>([]);
  const [busqueda, setBusqueda] = useState("");
  const idBuscador = useId();
  // Cargar el directorio al primer foco/tecleo, no al montar: pesa ~300 KB y no
  // hace falta hasta que el padre empieza a escribir.
  const asegurarCargado = useCallback(() => {
    if (directorio.length === 0) cargarDirectorio().then(setDirectorio);
  }, [directorio.length]);

  // Índices normalizados una sola vez (no por tecla); la búsqueda reconduce al
  // aliado la entrada del directorio que comparte su DANE (evita el duplicado).
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

  // Ya eligió (aliado, directorio o a mano): se muestra el elegido con opción de
  // cambiarlo, en vez de la lista, para que el paso quede claramente resuelto. El
  // aliado se resuelve desde `colegiosAliados` (ya cargado, sin esperar el JSON).
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
          {/* No está en ninguna fuente: se escribe a mano. El backend deriva el id
              del nombre normalizado, así que dos acudientes que escriban el mismo
              colegio convergen a la misma versión. */}
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
