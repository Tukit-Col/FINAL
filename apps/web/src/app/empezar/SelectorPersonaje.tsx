"use client";

// Selector de personajes para el hijo.
//
// No es una pantalla suelta ni un mock: es la entrada REAL de la preferencia
// `personaje_por_hijo` del contrato. El formulario la sigue leyendo como una
// lista de nombres separados por comas (misma forma de antes), asi que este
// componente solo cambia COMO se elige, no QUE se guarda. El eje personaje es
// ortogonal al nivel de calidad —por eso usa `--color-personaje` y nunca se
// pinta como un cuarto nivel.
//
// El cambio de fondo (P4b): la rejilla ya no es una lista fija de "sugeridos"
// que promete cualquier cosa. Son las franquicias que de verdad tenemos surtidas
// completas —el filtro de las cuatro anclas lo hace el servidor y nos llega en
// `surtidos`—, asi que tocar una es una promesa que sí cumplimos. El campo libre
// sigue existiendo, pero como PEDIDO: se ve distinto porque no garantiza stock.
//
// Motion de plastilina con rebote al elegir; con `prefers-reduced-motion` no
// anima (el helper del contrato lo resuelve) y el selector sigue funcionando.

import { useRef } from "react";
import { Check, Sparkles } from "lucide-react";
import { useGSAP, gsap, squish, prefiereMenosMovimiento } from "@tukit/contrato/motion";
import { iconoDe } from "./IconosPersonaje";
import estilos from "./SelectorPersonaje.module.css";

interface Props {
  /** Valor actual: nombres separados por comas (lo que el formulario guarda). */
  valor: string;
  /** Devuelve el nuevo string separado por comas. */
  onChange: (valor: string) => void;
  /** Para etiquetar el hijo en la cabecera del selector. */
  etiquetaHijo: string;
  /**
   * Franquicias surtidas completas (pasan el filtro de las cuatro anclas). Son
   * los nombres de catalogo, ya en minuscula. Vienen del servidor.
   */
  surtidos: string[];
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

export default function SelectorPersonaje({ valor, onChange, etiquetaHijo, surtidos }: Props) {
  const rejilla = useRef<HTMLDivElement>(null);
  const elegidos = parsear(valor);
  const elegidosLower = elegidos.map((p) => p.toLowerCase());
  const surtidosSet = new Set(surtidos.map((s) => s.toLowerCase()));

  // Los que el acudiente escribió a mano y no están en la rejilla surtida: son
  // pedidos, y se muestran aparte como chips que se pueden quitar.
  const pedidos = elegidos.filter((p) => !surtidosSet.has(p.toLowerCase()));

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
            Toca los que le gusten. Estos los tenemos surtidos completos, así que
            los buscamos con esos personajes sin falta.
          </p>
        </div>
      </div>

      {surtidos.length > 0 && (
        <div
          className={estilos.rejilla}
          ref={rejilla}
          role="group"
          aria-label={`Personajes surtidos para ${etiquetaHijo}`}
        >
          {surtidos.map((nombre) => {
            const activo = elegidosLower.includes(nombre);
            const Icono = iconoDe(nombre);
            return (
              <button
                key={nombre}
                type="button"
                aria-pressed={activo}
                className={`${estilos.ficha} ${activo ? estilos.fichaActiva : ""}`}
                onClick={(e) => alternar(nombre, e.currentTarget)}
              >
                <Icono className={estilos.icono} />
                <span className={estilos.nombre}>{nombre}</span>
                {activo && (
                  <span className={estilos.marca} aria-hidden="true">
                    <Check size={12} strokeWidth={3.4} />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* Campo libre: es un PEDIDO, no una promesa de stock. Se ve distinto y el
          rótulo lo dice claro. Se guarda en el mismo string. */}
      <div>
        <p className={estilos.rotuloLibre}>
          ¿Le gusta otro?
          <span>Escríbelo y lo pedimos: si aún no lo surtimos, te lo decimos claro.</span>
        </p>
        <label className={estilos.libre}>
          <Sparkles size={15} aria-hidden="true" strokeWidth={2.4} className={estilos.libreIcono} />
          <input
            type="text"
            className={estilos.libreInput}
            placeholder="Otro personaje… y presiona Enter"
            aria-label={`Pedir otro personaje para ${etiquetaHijo}`}
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
      </div>

      {/* Los pedidos escritos a mano se muestran aparte y se quitan tocándolos. */}
      {pedidos.length > 0 && (
        <div className={estilos.propios}>
          {pedidos.map((p) => (
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
