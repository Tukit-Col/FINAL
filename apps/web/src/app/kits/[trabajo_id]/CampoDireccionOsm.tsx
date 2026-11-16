"use client";

// La dirección del checkout (ADR 0049): el
// acudiente busca su dirección en OpenStreetMap, elige un resultado y confirma
// el punto en un mapa moviendo el pin. Sin resultados, o si el servicio falla,
// el campo sigue siendo texto libre: el mapa jamás bloquea el pago.
//
// La búsqueda sale con el botón Buscar, con Enter o tras una pausa larga al
// escribir (nunca por tecla: la política del Nominatim público no admite el
// autocompletado, ver `lib/direccion-osm.ts`). Se cancela la anterior si el
// acudiente lanza otra o edita el texto.
// La entrega es solo en Bogotá: el servidor limita siempre la búsqueda a Bogotá.
//
// Combobox ARIA como el buscador de colegio de `/empezar`: el foco
// se queda en el campo, las flechas mueven la opción activa
// (`aria-activedescendant`), Enter elige y Escape cierra la lista.

import { useEffect, useId, useRef, useState } from "react";
import { MapPin, Pencil, Search } from "lucide-react";
import { direccionDesdeNominatim, type DireccionDerivada } from "@tukit/contrato";
import { MINIMO_CARACTERES, type Candidato } from "@/lib/direccion-osm";
import MapaConfirmacionCarga from "./MapaConfirmacionCarga";
import styles from "./Kits.module.css";

export interface LugarElegido extends DireccionDerivada {
  direccion: string;
  latitud?: number;
  longitud?: number;
}

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

// Pausa al escribir antes de buscar sola. Larga a propósito: Nominatim no admite
// autocompletado por tecla, y el servidor ya limita a 1 petición por segundo.
const PAUSA_BUSQUEDA_MS = 1200;
const MINIMO_AUTOMATICA = 8;

export default function CampoDireccionOsm({ valor, latitud, longitud, onEscribir, onElegir, onMoverPin }: Props) {
  const idBase = useId();
  const idLista = `${idBase}-lista`;
  const idEstado = `${idBase}-estado`;
  const [candidatos, setCandidatos] = useState<Candidato[]>([]);
  const [abierta, setAbierta] = useState(false);
  const [activa, setActiva] = useState(0);
  const [estado, setEstado] = useState<Estado>({ tipo: "reposo" });
  // El resultado elegido: se muestra como tarjeta de confirmación hasta "Editar".
  const [elegido, setElegido] = useState<Candidato | null>(null);
  const control = useRef<AbortController | null>(null);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => () => control.current?.abort(), []);

  const confirmada = latitud !== null && longitud !== null;
  const puedeBuscar = valor.trim().length >= MINIMO_CARACTERES && estado.tipo !== "buscando";

  const pausa = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (pausa.current) clearTimeout(pausa.current);
  }, []);

  async function buscar(texto: string = valor) {
    if (texto.trim().length < MINIMO_CARACTERES) return;
    control.current?.abort();
    const actual = new AbortController();
    control.current = actual;
    setEstado({ tipo: "buscando" });
    setCandidatos([]);
    try {
      const respuesta = await fetch(`/api/direccion/buscar?q=${encodeURIComponent(texto.trim())}`, {
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
    setElegido(candidato);
    onElegir({
      direccion: candidato.direccion,
      latitud: candidato.latitud,
      longitud: candidato.longitud,
      ...direccionDesdeNominatim(candidato.componentes),
    });
  }

  function escribir(texto: string) {
    // Editar descarta la búsqueda en curso y la lista: ya no corresponden.
    control.current?.abort();
    if (pausa.current) clearTimeout(pausa.current);
    setElegido(null);
    onEscribir(texto);
    setCandidatos([]);
    setAbierta(false);
    setEstado({ tipo: "reposo" });
    // Búsqueda por pausa: solo si hay una dirección con cuerpo y todavía no se
    // confirmó un punto. Las teclas intermedias no consultan nada.
    if (texto.trim().length >= MINIMO_AUTOMATICA && !confirmada) {
      pausa.current = setTimeout(() => void buscar(texto), PAUSA_BUSQUEDA_MS);
    }
  }

  // "Editar": vuelve al campo con el texto actual para corregirlo (descarta el pin
  // igual que escribir a mano) y deja el foco listo.
  function editar() {
    setElegido(null);
    onEscribir(valor);
    requestAnimationFrame(() => campo.current?.focus());
  }

  const tarjeta = elegido !== null && confirmada;
  const visible = !tarjeta && abierta && candidatos.length > 0;
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
          ? `No encontramos esa dirección en Bogotá. Revisa el texto o déjala escrita como está y sigue.`
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
      {tarjeta && elegido && (
        <div className={styles.tarjetaDireccion}>
          <MapPin size={20} aria-hidden="true" className={styles.tarjetaDireccionIcono} />
          <div className={styles.tarjetaDireccionTexto}>
            <p className={styles.tarjetaDireccionLinea}>{valor}</p>
            {elegido.secundario && <p className={styles.tarjetaDireccionZona}>{elegido.secundario}</p>}
            {elegido.confirmarNumero && (
              <p className={styles.tarjetaDireccionAviso}>
                {elegido.cruceCon
                  ? `El pin quedó en el cruce con la ${elegido.cruceCon}. Muévelo hasta tu puerta.`
                  : elegido.numeroDelPadre
                  ? "Confirma el número: el mapa solo encontró la calle, el número es el que escribiste."
                  : "Confirma el número: el mapa solo encontró la calle. Toca Editar para añadirlo."}
              </p>
            )}
          </div>
          <button type="button" className={styles.botonEditarDireccion} onClick={editar}>
            <Pencil size={16} aria-hidden="true" />
            Editar
          </button>
        </div>
      )}
      {/* La lista cuelga de ESTE ancla (campo + botón) y no de todo el bloque: el
          bloque también lleva el aviso y el mapa, y con el pin ya puesto la lista
          caería debajo del mapa, lejos del campo. */}
      <div className={styles.anclaListaDireccion} hidden={tarjeta}>
        <div className={styles.filaBuscarDireccion}>
          <input
            id={`${idBase}-campo`}
            ref={campo}
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
                <span className={styles.sugerenciaPrincipal}>{c.completa}</span>
                {c.confirmarNumero && (
                  <span className={styles.sugerenciaSecundaria}>
                    {c.cruceCon
                      ? `Ubicada en el cruce con la ${c.cruceCon}. Ajusta el pin.`
                      : c.numeroDelPadre
                        ? "Número escrito por ti. Confirma el número."
                        : "Confirma el número."}
                  </span>
                )}
              </li>
            ))}
          </ul>
          <p className={styles.atribucionOsm}>© OpenStreetMap</p>
        </div>
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
