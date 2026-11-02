"use client";

// La dirección del checkout cuando NO hay llave de Google (ADR 0049): el
// acudiente busca su dirección en OpenStreetMap, elige un resultado y confirma
// el punto en un mapa moviendo el pin. Sin resultados, o si el servicio falla,
// el campo sigue siendo texto libre: el mapa jamás bloquea el pago.
//
// La búsqueda es EXPLÍCITA (botón Buscar o Enter), nunca por tecla: la política
// del Nominatim público prohíbe el autocompletado (ver `lib/direccion-osm.ts`).
// Por eso tampoco hay espera entre teclas ni turnos; solo se cancela la búsqueda
// anterior si el acudiente lanza otra o edita el texto.
//
// Combobox ARIA como el de Google y el buscador de colegio de `/empezar`: el foco
// se queda en el campo, las flechas mueven la opción activa
// (`aria-activedescendant`), Enter elige y Escape cierra la lista.

import { useEffect, useId, useRef, useState } from "react";
import { Search } from "lucide-react";
import { direccionDesdeNominatim } from "@tukit/contrato";
import { MINIMO_CARACTERES, type Candidato } from "@/lib/direccion-osm";
import type { LugarElegido } from "./CampoDireccion";
import MapaConfirmacionCarga from "./MapaConfirmacionCarga";
import styles from "./Kits.module.css";

type Estado =
  | { tipo: "reposo" }
  | { tipo: "buscando" }
  | { tipo: "resultados"; cantidad: number }
  | { tipo: "vacio" }
  | { tipo: "fallo"; mensaje: string };

interface Props {
  valor: string;
  // El punto confirmado hasta ahora (o `null` si la dirección está sin confirmar).
  latitud: number | null;
  longitud: number | null;
  // Texto escrito a mano: quien lo recibe descarta el pin anterior.
  onEscribir: (texto: string) => void;
  onElegir: (lugar: LugarElegido) => void;
  // El acudiente movió el pin; el texto de la dirección no cambia.
  onMoverPin: (latitud: number, longitud: number) => void;
}

export default function CampoDireccionOsm({ valor, latitud, longitud, onEscribir, onElegir, onMoverPin }: Props) {
  const idBase = useId();
  const idLista = `${idBase}-lista`;
  const idEstado = `${idBase}-estado`;
  const [candidatos, setCandidatos] = useState<Candidato[]>([]);
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const [estado, setEstado] = useState<Estado>({ tipo: "reposo" });
  const control = useRef<AbortController | null>(null);

  useEffect(() => () => control.current?.abort(), []);

  const confirmada = latitud !== null && longitud !== null;
  const puedeBuscar = valor.trim().length >= MINIMO_CARACTERES && estado.tipo !== "buscando";

  async function buscar() {
    if (!puedeBuscar) return;
    control.current?.abort();
    const actual = new AbortController();
    control.current = actual;
    setEstado({ tipo: "buscando" });
    setCandidatos([]);
    try {
      const respuesta = await fetch(`/api/direccion/buscar?q=${encodeURIComponent(valor.trim())}`, {
        signal: actual.signal,
      });
      const cuerpo = (await respuesta.json().catch(() => null)) as {
        candidatos?: Candidato[];
        mensaje?: string;
      } | null;
      if (actual.signal.aborted) return;
      if (!respuesta.ok || !cuerpo?.candidatos) {
        setEstado({
          tipo: "fallo",
          mensaje: cuerpo?.mensaje ?? "No pudimos consultar el mapa ahora.",
        });
        return;
      }
      setCandidatos(cuerpo.candidatos);
      setActiva(0);
      setAbierta(cuerpo.candidatos.length > 0);
      setEstado(
        cuerpo.candidatos.length > 0 ? { tipo: "resultados", cantidad: cuerpo.candidatos.length } : { tipo: "vacio" },
      );
    } catch {
      if (!actual.signal.aborted) {
        setEstado({ tipo: "fallo", mensaje: "No pudimos consultar el mapa ahora." });
      }
    }
  }

  function elegir(candidato: Candidato) {
    setAbierta(false);
    setCandidatos([]);
    setEstado({ tipo: "reposo" });
    onElegir({
      direccion: candidato.direccion,
      google_place_id: null,
      latitud: candidato.latitud,
      longitud: candidato.longitud,
      ...direccionDesdeNominatim(candidato.componentes),
    });
  }

  function escribir(texto: string) {
    // Editar descarta la búsqueda en curso y la lista: ya no corresponden.
    control.current?.abort();
    onEscribir(texto);
    setCandidatos([]);
    setAbierta(false);
    setEstado({ tipo: "reposo" });
  }

  const visible = abierta && candidatos.length > 0;
  const indiceActivo = Math.min(activa, Math.max(candidatos.length - 1, 0));

  function teclear(evento: React.KeyboardEvent<HTMLInputElement>) {
    if (visible) {
      if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
        evento.preventDefault();
        const paso = evento.key === "ArrowDown" ? 1 : -1;
        setActiva((indiceActivo + paso + candidatos.length) % candidatos.length);
      } else if (evento.key === "Enter") {
        // Enter con la lista abierta elige; nunca manda el pago a medias.
        evento.preventDefault();
        elegir(candidatos[indiceActivo]);
      } else if (evento.key === "Escape") {
        evento.preventDefault();
        setAbierta(false);
      }
      return;
    }
    // Con la dirección ya confirmada, Enter es enviar el formulario como siempre;
    // sin confirmar, Enter busca.
    if (evento.key === "Enter" && !confirmada && puedeBuscar) {
      evento.preventDefault();
      void buscar();
    }
  }

  const mensaje =
    estado.tipo === "buscando"
      ? "Buscando…"
      : estado.tipo === "resultados"
        ? `${estado.cantidad} ${estado.cantidad === 1 ? "resultado" : "resultados"}. Elige el tuyo con las flechas o toca uno.`
        : estado.tipo === "vacio"
          ? "No encontramos esa dirección. Revisa el texto o déjala escrita como está y sigue."
          : estado.tipo === "fallo"
            ? `${estado.mensaje} Puedes dejar la dirección escrita y seguir con el pago.`
            : confirmada
              ? "Ubicación confirmada en el mapa."
              : "";

  return (
    <div className={styles.campoDireccion}>
      {/* Rótulo explícito y no envolvente: la lista de resultados no puede
          formar parte del nombre accesible del campo. */}
      <label htmlFor={`${idBase}-campo`}>Dirección</label>
      <div className={styles.filaBuscarDireccion}>
        <input
          id={`${idBase}-campo`}
          value={valor}
          required
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Ej.: Calle 72 # 10-34, Bogotá"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={visible}
          aria-controls={idLista}
          aria-describedby={idEstado}
          aria-activedescendant={visible ? `${idLista}-${indiceActivo}` : undefined}
          onBlur={() => setAbierta(false)}
          onChange={(e) => escribir(e.target.value)}
          onKeyDown={teclear}
        />
        <button
          type="button"
          className={styles.botonBuscarDireccion}
          disabled={!puedeBuscar}
          onClick={() => void buscar()}
        >
          <Search size={18} aria-hidden="true" />
          Buscar
        </button>
      </div>
      <div className={styles.sugerenciasDireccion} hidden={!visible}>
        <ul id={idLista} role="listbox" aria-label="Direcciones encontradas">
          {candidatos.map((c, i) => (
            <li
              key={c.id}
              id={`${idLista}-${i}`}
              role="option"
              aria-selected={i === indiceActivo}
              className={`${styles.sugerenciaDireccion} ${i === indiceActivo ? styles.sugerenciaActiva : ""}`}
              // `mousedown` y no `click`: el `blur` del campo cerraría la lista
              // antes de que el clic llegue a la opción.
              onMouseDown={(e) => {
                e.preventDefault();
                elegir(c);
              }}
              onMouseEnter={() => setActiva(i)}
            >
              <span className={styles.sugerenciaPrincipal}>{c.principal}</span>
              {c.secundario && <span className={styles.sugerenciaSecundaria}>{c.secundario}</span>}
            </li>
          ))}
        </ul>
        <p className={styles.atribucionOsm}>© OpenStreetMap</p>
      </div>
      <p id={idEstado} role="status" aria-live="polite" className={styles.estadoDireccion}>
        {mensaje}
      </p>
      {confirmada && (
        <MapaConfirmacionCarga latitud={latitud} longitud={longitud} onMover={onMoverPin} />
      )}
    </div>
  );
}
