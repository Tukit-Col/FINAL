"use client";

// Selector de personajes gamificado para el hijo.
//
// No es una pantalla suelta ni un mock: es la entrada REAL de la preferencia
// `personaje_por_hijo` del contrato. El formulario la sigue leyendo como una
// lista de nombres separados por comas (misma forma de antes), asi que este
// componente solo cambia COMO se elige, no QUE se guarda. El eje personaje es
// ortogonal al nivel de calidad —por eso usa `--color-personaje` y nunca se
// pinta como un cuarto nivel—, y elegir un personaje no promete que exista:
// el catalogo dira la verdad después. Aqui solo capturamos el gusto del niño.
//
// Motion de plastilina con rebote al elegir; con `prefers-reduced-motion` no
// anima (el helper del contrato lo resuelve) y el selector sigue funcionando.

import { useRef } from "react";
import { Check, Plus, Sparkles } from "lucide-react";
import { useGSAP, gsap, squish, prefiereMenosMovimiento } from "@tukit/contrato/motion";
import estilos from "./SelectorPersonaje.module.css";

// Personajes que los niños piden más, con un emoji de gancho visual. La lista
// es un atajo amable, no una promesa de catálogo: se puede escribir cualquier
// otro. Los nombres van en minúscula porque asi los normaliza el catálogo.
const SUGERIDOS: { nombre: string; emoji: string }[] = [
  { nombre: "spiderman", emoji: "🕷️" },
  { nombre: "frozen", emoji: "❄️" },
  { nombre: "barbie", emoji: "💗" },
  { nombre: "hot wheels", emoji: "🏎️" },
  { nombre: "minecraft", emoji: "⛏️" },
  { nombre: "stitch", emoji: "🩵" },
  { nombre: "harry potter", emoji: "⚡" },
  { nombre: "sonic", emoji: "💨" },
  { nombre: "kitty", emoji: "🎀" },
  { nombre: "dinosaurios", emoji: "🦕" },
  { nombre: "fútbol", emoji: "⚽" },
  { nombre: "unicornios", emoji: "🦄" },
];

interface Props {
  /** Valor actual: nombres separados por comas (lo que el formulario guarda). */
  valor: string;
  /** Devuelve el nuevo string separado por comas. */
  onChange: (valor: string) => void;
  /** Para etiquetar el hijo en la cabecera del selector. */
  etiquetaHijo: string;
}

// El estado vive en el string del formulario. Lo parseamos a un conjunto para
// pintar qué está activo, y lo volvemos a unir al cambiar: una sola fuente de
// verdad, sin duplicar estado que se pueda desincronizar.
function parsear(valor: string): string[] {
  return valor
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
}

export default function SelectorPersonaje({ valor, onChange, etiquetaHijo }: Props) {
  const rejilla = useRef<HTMLDivElement>(null);
  const elegidos = parsear(valor);
  const elegidosLower = elegidos.map((p) => p.toLowerCase());

  // Sugeridos que ya no están elegidos + los personajes libres que el acudiente
  // escribió y no están en la lista sugerida (para poder mostrarlos como chip).
  const libresElegidos = elegidos.filter(
    (p) => !SUGERIDOS.some((s) => s.nombre === p.toLowerCase()),
  );

  useGSAP(
    () => {
      if (prefiereMenosMovimiento() || !rejilla.current) return;
      gsap.from(rejilla.current.children, {
        opacity: 0,
        scale: 0.8,
        y: 10,
        duration: 0.4,
        ease: "back.out(1.6)",
        stagger: { each: 0.03, from: "center" },
      });
    },
    { scope: rejilla },
  );

  function alternar(nombre: string, nodo: Element | null) {
    const yaEsta = elegidosLower.includes(nombre.toLowerCase());
    const siguiente = yaEsta
      ? elegidos.filter((p) => p.toLowerCase() !== nombre.toLowerCase())
      : [...elegidos, nombre];
    if (!yaEsta) {
      squish(nodo, true);
      setTimeout(() => squish(nodo, false), 130);
    }
    onChange(siguiente.join(", "));
  }

  function agregarLibre(texto: string) {
    const limpio = texto.trim();
    if (!limpio) return;
    if (elegidosLower.includes(limpio.toLowerCase())) return;
    onChange([...elegidos, limpio].join(", "));
  }

  return (
    <div className={estilos.selector}>
      <div className={estilos.cabecera}>
        <span className={estilos.chispa} aria-hidden="true">
          <Sparkles size={16} strokeWidth={2.4} />
        </span>
        <div>
          <p className={estilos.titulo}>¿Qué le encanta a {etiquetaHijo}?</p>
          <p className={estilos.subtitulo}>
            Toca los que le gusten. Buscaremos sus útiles con esos personajes donde
            los tengamos — y si no, te lo diremos claro.
          </p>
        </div>
      </div>

      <div className={estilos.rejilla} ref={rejilla} role="group" aria-label={`Personajes de ${etiquetaHijo}`}>
        {SUGERIDOS.map((personaje) => {
          const activo = elegidosLower.includes(personaje.nombre);
          return (
            <button
              key={personaje.nombre}
              type="button"
              aria-pressed={activo}
              className={`${estilos.ficha} ${activo ? estilos.fichaActiva : ""}`}
              onClick={(e) => alternar(personaje.nombre, e.currentTarget)}
            >
              <span className={estilos.emoji} aria-hidden="true">
                {personaje.emoji}
              </span>
              <span className={estilos.nombre}>{personaje.nombre}</span>
              {activo && (
                <span className={estilos.marca} aria-hidden="true">
                  <Check size={12} strokeWidth={3.4} />
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Cualquier otro personaje: campo libre. Es la misma preferencia, escrita
          a mano. Se guarda en el mismo string. */}
      <label className={estilos.libre}>
        <Plus size={15} aria-hidden="true" strokeWidth={2.6} className={estilos.libreIcono} />
        <input
          type="text"
          className={estilos.libreInput}
          placeholder="¿Otro? Escríbelo y presiona Enter"
          aria-label={`Agregar otro personaje para ${etiquetaHijo}`}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              agregarLibre(e.currentTarget.value);
              e.currentTarget.value = "";
            }
          }}
          onBlur={(e) => {
            agregarLibre(e.currentTarget.value);
            e.currentTarget.value = "";
          }}
        />
      </label>

      {/* Los personajes libres elegidos también se pueden quitar tocándolos. */}
      {libresElegidos.length > 0 && (
        <div className={estilos.propios}>
          {libresElegidos.map((p) => (
            <button
              key={p}
              type="button"
              className={estilos.chipPropio}
              onClick={() => alternar(p, null)}
              aria-label={`Quitar ${p}`}
            >
              {p}
              <Check size={11} strokeWidth={3.2} aria-hidden="true" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
