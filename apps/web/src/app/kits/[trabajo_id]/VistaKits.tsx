// Pantalla de los kits de un trabajo: selector de perfil, líneas del carrito y pago.
//
// Decisiones:
// - Muestra los huecos de catálogo y las líneas que no se pueden cobrar: la pantalla no los tapa.
// - El total incluye solo lo que está en el carrito; la sección «Fuera del carrito» no suma.
// - La agrupación y las reglas puras viven en `lib/kit-vista` y `lib/direccion-checkout`; el pago,
//   las franjas del Fan, el resumen por hijo y las secciones de líneas son componentes vecinos.

"use client";

import { useMemo, useState } from "react";
import { Star, PiggyBank, Sparkles, Gem, SlidersHorizontal } from "lucide-react";
import {
  clasificar,
  formatearPesos,
  hayQueCobrar,
  type PerfilKit,
  type Trabajo,
} from "@tukit/contrato";
import type { EntregaPrevia } from "@/lib/pagar-pedido";
import {
  agruparPorCategoria,
  etiquetasDeHijos,
  gradosDeHijos,
  resumenPorHijo,
  textoDeConsolidacion,
  type ApodoMatricula,
} from "@/lib/kit-vista";
import AsistenteKitSlot from "./AsistenteKitSlot";
import TarjetaLuz from "@/components/TarjetaLuz";
import ResumenRecibo from "./ResumenRecibo";
import styles from "./Kits.module.css";
import Checkout from "./Checkout";
import FranjaFan from "./FranjaFan";
import ResumenPorHijo from "./ResumenPorHijo";
import SeccionesDeLineas from "./SeccionesDeLineas";

const ICONO_PERFIL: Record<PerfilKit, typeof PiggyBank> = {
  Ahorrador: PiggyBank,
  Fan: Sparkles,
  "A tu Medida": SlidersHorizontal,
  Premium: Gem,
};

const PROMESA: Record<PerfilKit, string> = {
  Ahorrador: "Lo más barato que cumple con la lista.",
  Fan: "Con los personajes que pidió tu hijo, donde se puede.",
  "A tu Medida": "La mejor marca que cabe en lo que quieres gastar.",
  Premium: "Las marcas que más aguantan el año.",
};

const ORDEN_PERFIL: PerfilKit[] = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

export default function VistaKits({
  trabajo,
  correo,
  matriculas,
  entregaPrevia,
  abrirPago,
}: {
  trabajo: Trabajo;
  correo: string;
  matriculas: ApodoMatricula[];
  entregaPrevia: EntregaPrevia | null;
  abrirPago: boolean;
}) {
  const recomendado = trabajo.recomendado;
  const [activo, setActivo] = useState<PerfilKit>(recomendado?.perfil ?? "Ahorrador");
  const kits = useMemo(
    () =>
      [...trabajo.kits].sort(
        (a, b) => ORDEN_PERFIL.indexOf(a.perfil) - ORDEN_PERFIL.indexOf(b.perfil),
      ),
    [trabajo.kits],
  );

  const kit = useMemo(() => kits.find((k) => k.perfil === activo) ?? kits[0], [kits, activo]);

  const nombresHijos = useMemo(
    () =>
      etiquetasDeHijos(
        trabajo.kits.flatMap((k) => k.lineas.map((l) => l.hijo)),
        trabajo.hijos,
        matriculas,
      ),
    [trabajo.kits, trabajo.hijos, matriculas],
  );
  const gradosHijos = useMemo(
    () => gradosDeHijos(trabajo.kits.flatMap((k) => k.lineas.map((l) => l.hijo)), trabajo.hijos),
    [trabajo.kits, trabajo.hijos],
  );
  const resumen = useMemo(
    () =>
      kit ? resumenPorHijo(kit, nombresHijos, gradosHijos, trabajo.personajes_por_hijo) : [],
    [kit, nombresHijos, gradosHijos, trabajo.personajes_por_hijo],
  );

  if (!kit) {
    return (
      <div className={styles.pagina}>
        <p className={styles.vacio}>Este pedido no trajo ningún kit.</p>
      </div>
    );
  }

  const eligioEl = trabajo.origen === "parent_apply";
  const rotuloMarcado = eligioEl ? "Tu elección" : "Te recomendamos este";
  const IconoActivo = ICONO_PERFIL[kit.perfil];
  const viendoOtro = recomendado !== null && kit.perfil !== recomendado.perfil;

  return (
    <div className={styles.pagina}>
      <header className={styles.encabezado}>
        <h1>{eligioEl ? "Tu kit está listo" : "Tus kits están listos"}</h1>
        <p>
          {eligioEl
            ? "Este es el kit que elegiste. Si quieres, compáralo con los otros o cambia cualquier producto por otra opción."
            : "Todos cubren la misma lista. Te marcamos uno, pero los demás siguen aquí: cuál conviene depende de cosas que solo sabes tú."}
        </p>
      </header>

      {kits.length > 1 && (
        <div className={styles.selectorKits} role="tablist" aria-label="Ver otro kit">
          <span className={styles.selectorRotulo}>Ver kit</span>
          {kits.map((otro) => {
            const esActivo = otro.perfil === kit.perfil;
            const esMarcado = otro.perfil === recomendado?.perfil;
            return (
              <button
                key={otro.perfil}
                type="button"
                role="tab"
                aria-selected={esActivo}
                className={`${styles.opcionKit} ${esActivo ? styles.opcionKitActiva : ""}`}
                onClick={() => setActivo(otro.perfil)}
                title={esMarcado ? rotuloMarcado : undefined}
              >
                {esMarcado && (
                  <Star
                    size={12}
                    aria-label={rotuloMarcado}
                    fill="currentColor"
                    strokeWidth={0}
                    className={styles.estrellaKit}
                  />
                )}
                {otro.perfil}
                <span className={`${styles.totalOpcion} cifra`}>
                  {hayQueCobrar(otro.total) ? formatearPesos(otro.total) : "—"}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <TarjetaLuz key={`luz-${kit.perfil}`} className={`${styles.tarjetaKit} ${styles.kitActivo}`} aria-live="polite">
        {kit.perfil === recomendado?.perfil && (
          <span className={styles.chapaRecomendado}>
            <Star size={12} aria-hidden="true" fill="currentColor" strokeWidth={0} />
            {rotuloMarcado}
          </span>
        )}
        <span className={styles.nombreKit}>
          <span className={styles.iconoKit} aria-hidden="true">
            <IconoActivo size={18} strokeWidth={2.4} />
          </span>
          {kit.perfil}
        </span>
        <span className={`${styles.totalKit} cifra`}>
          {hayQueCobrar(kit.total) ? formatearPesos(kit.total) : "Sin productos con precio"}
        </span>
        <span className={styles.promesa}>{PROMESA[kit.perfil]}</span>
        {Number.isFinite(kit.objetivos?.disponibilidad) && (
          <span className={styles.objetivos}>
            {Math.round(kit.objetivos.disponibilidad * 100)}% con precio confirmado
          </span>
        )}
      </TarjetaLuz>

      {viendoOtro ? (
        <p className={styles.razon}>
          Estás viendo el kit <strong>{kit.perfil}</strong>. Si lo pagas, es este el que te
          llevamos.{" "}
          <button
            type="button"
            className={styles.volverKit}
            onClick={() => setActivo(recomendado.perfil)}
          >
            Volver a {eligioEl ? "mi kit" : "el recomendado"} ({recomendado.perfil})
          </button>
        </p>
      ) : (
        recomendado &&
        (!eligioEl || recomendado.dentro_de_presupuesto === false) && (
          <p className={styles.razon}>
            <strong>
              {eligioEl ? "Tu kit:" : `Por qué el ${recomendado.perfil}:`}
            </strong>{" "}
            {recomendado.razon}
            {recomendado.dentro_de_presupuesto === false && (
              <em className={styles.fueraPresupuesto}> Ojo: se pasa del tope que pusiste.</em>
            )}
          </p>
        )
      )}

      {kit.perfil === "Fan" && resumen.length <= 1 && (
        <FranjaFan
          lineas={kit.lineas}
          pedidos={trabajo.personajes_por_hijo}
          sinEncaje={kit.personaje_sin_encaje ?? []}
          nombresHijos={nombresHijos}
        />
      )}

      {kit.consolidaciones.length > 0 && resumen.length <= 1 && (
        <section className={styles.consolidaciones}>
          <h2>Lo que juntamos entre tus hijos</h2>
          <p className={styles.explicaJunto}>
            Estos productos son iguales para varios de tus hijos, así que los compramos juntos y sobra menos.
          </p>
          <ul>
            {kit.consolidaciones.map((c, i) => {
              const t = textoDeConsolidacion(
                c,
                nombresHijos,
                c.ahorro > 0 ? formatearPesos(c.ahorro) : null,
                gradosHijos,
              );
              return (
                <li key={`${c.producto}-${i}`}>
                  <strong>{c.producto}</strong>
                  <span>
                    {[t.paraQuienes, t.cantidad].filter(Boolean).join(" · ")}
                  </span>
                  {t.porque && <span className={styles.porqueJunto}>{t.porque}</span>}
                  {t.ahorro && <span className={styles.ahorroJunto}>{t.ahorro}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {resumen.length > 1 && (
        <ResumenPorHijo
          key={`hijos-${kit.perfil}`}
          kit={kit}
          resumen={resumen}
          nombresHijos={nombresHijos}
          gradosHijos={gradosHijos}
          pedidos={trabajo.personajes_por_hijo}
        />
      )}

      <SeccionesDeLineas kit={kit} trabajoId={trabajo.trabajo_id} nombresHijos={nombresHijos} />

      <AsistenteKitSlot trabajoId={trabajo.trabajo_id} perfil={kit.perfil} />

      <ResumenRecibo
        perfil={kit.perfil}
        renglones={agruparPorCategoria(
          kit.lineas.filter((l) => clasificar(l) === "comprable" && !l.descartado),
        ).map((g) => ({ clave: g.categoria, titulo: g.titulo, cantidad: g.lineas.length }))}
        total={hayQueCobrar(kit.total) ? formatearPesos(kit.total) : "Sin productos con precio"}
      />

      <Checkout
        trabajoId={trabajo.trabajo_id}
        perfil={kit.perfil}
        total={kit.total}
        correo={correo}
        entregaPrevia={entregaPrevia}
        abrirPago={abrirPago}
      />
    </div>
  );
}
