// Selector de personajes para el hijo.
//
// Decisiones:
// - Es la entrada real de la preferencia `personaje_por_hijo`; el formulario la sigue leyendo como una
//   lista de nombres separados por comas, así que el componente solo cambia cómo se elige.
// - El eje personaje es ortogonal al nivel de calidad: usa `--color-personaje` y nunca se pinta como
//   un cuarto nivel.
// - La rejilla muestra solo las franquicias que tenemos surtidas completas (el servidor aplica el
//   filtro de las cuatro anclas y llegan en `surtidos`), así que tocar una es una promesa que se
//   cumple. El campo libre es un pedido: se ve distinto porque no garantiza stock.

"use client";

import { useRef } from "react";
import { Check, Sparkles } from "lucide-react";
import { useGSAP, gsap, squish, prefiereMenosMovimiento } from "@tukit/contrato/motion";
import { iconoDe } from "./IconosPersonaje";
import estilos from "./SelectorPersonaje.module.css";

interface Props {
  valor: string;
  onChange: (valor: string) => void;
  etiquetaHijo: string;
  surtidos: string[];
}

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
        clearProps: "transform",
      });
    },
    { scope: rejilla },
  );

  function alternar(nombre: string, nodo: Element | null) {
    const yaEsta = elegidosLower.includes(nombre.toLowerCase());
    const soloPedidos = elegidos.filter((p) => !surtidosSet.has(p.toLowerCase()));
    const siguiente = yaEsta ? soloPedidos : [...soloPedidos, nombre];
    squish(nodo, true);
    setTimeout(() => squish(nodo, false), 130);
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
          <p className={estilos.titulo}>
            ¿Qué le encanta a {etiquetaHijo}?
            <span className={estilos.opcional}>Opcional</span>
          </p>
          <p className={estilos.subtitulo}>
            Sin personaje también está bien: tu kit sale igual. Si quieres, toca los
            que le gusten; estos los tenemos surtidos completos, así que los buscamos
            con esos personajes sin falta.
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

      <button
        type="button"
        aria-pressed={elegidos.length === 0}
        className={`${estilos.sinPersonaje} ${elegidos.length === 0 ? estilos.sinPersonajeActivo : ""}`}
        onClick={() => onChange("")}
      >
        {elegidos.length === 0 && <Check size={13} strokeWidth={3.2} aria-hidden="true" />}
        Sin personaje
      </button>

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
