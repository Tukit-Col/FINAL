"use client";

import { useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Layers } from "lucide-react";
import type { LineaKit } from "@tukit/contrato";
import { cambiarProductoDeKit, opcionesDeLinea } from "@/lib/api-navegador";
import {
  aplicarPlanEnLote,
  marcasDisponibles,
  planDeCambioPorMarca,
  type OpcionesPorLinea,
} from "@/lib/cambio-en-lote";
import { idAnclaCategoria, type CategoriaKit } from "@/lib/kit-vista";
import styles from "./Kits.module.css";

/**
 * Cabecera de un grupo del carrito: título, conteo y "Cambiar todos".
 * Las opciones de cada renglón se piden solo al abrir el selector. El cambio
 * es un PUT por renglón (sin endpoint nuevo) y cada uno se puede deshacer con
 * su propio "Cambiar por otra opción".
 */
export default function CabeceraCategoria({
  titulo,
  categoria,
  lineas,
  trabajoId,
  perfil,
}: {
  titulo: string;
  categoria: CategoriaKit;
  lineas: LineaKit[];
  trabajoId: string;
  perfil: string;
}) {
  const router = useRouter();
  const idCampo = useId();
  const activas = useMemo(() => lineas.filter((l) => !l.descartado), [lineas]);
  const [abierto, setAbierto] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [opciones, setOpciones] = useState<OpcionesPorLinea | null>(null);
  const [marca, setMarca] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<string | null>(null);

  const marcas = useMemo(() => (opciones ? marcasDisponibles(opciones) : []), [opciones]);
  const plan = useMemo(
    () => (opciones && marca ? planDeCambioPorMarca(activas, opciones, marca) : null),
    [activas, opciones, marca],
  );

  async function abrir() {
    setAbierto(true);
    setResultado(null);
    setError(null);
    if (opciones) return;
    setCargando(true);
    const respuestas = await Promise.allSettled(
      activas.map((l) => opcionesDeLinea(trabajoId, perfil, l.item_id)),
    );
    const porLinea: OpcionesPorLinea = {};
    let fallaron = 0;
    respuestas.forEach((r, i) => {
      if (r.status === "fulfilled") porLinea[activas[i]!.item_id] = r.value.opciones;
      else fallaron += 1;
    });
    setOpciones(porLinea);
    if (fallaron > 0) {
      setError(`No pudimos cargar las opciones de ${fallaron} de ${activas.length}. Las demás sí.`);
    }
    setCargando(false);
  }

  async function aplicar() {
    if (!plan || plan.cambian.length === 0) return;
    setAplicando(true);
    setError(null);
    const { hechos, fallidos } = await aplicarPlanEnLote(plan, (itemId, sku) =>
      cambiarProductoDeKit(trabajoId, perfil, itemId, sku),
    );
    const partes = [`Cambiamos ${hechos} a ${marca}.`];
    if (plan.sinEsaMarca.length > 0) partes.push(`${plan.sinEsaMarca.length} no tienen esa marca.`);
    if (fallidos.length > 0) {
      setError(`No pudimos cambiar ${fallidos.length}. Intenta de nuevo con esos.`);
    }
    setResultado(partes.join(" "));
    setOpciones(null);
    setMarca("");
    setAbierto(false);
    setAplicando(false);
    router.refresh();
  }

  return (
    <header className={styles.cabeceraCategoria}>
      <div className={styles.cabeceraCategoriaFila}>
        <h3 id={`${idAnclaCategoria(categoria)}-titulo`}>
          {titulo} <span className={`${styles.conteo} cifra`}>{activas.length}</span>
        </h3>
        {activas.length >= 2 && !abierto && (
          <button type="button" className={styles.botonCambiar} onClick={abrir}>
            <Layers size={14} aria-hidden="true" /> Cambiar todos
          </button>
        )}
      </div>

      {abierto && (
        <div className={styles.panelLote}>
          {cargando ? (
            <p className={styles.notaCambio} role="status">
              Buscando marcas…
            </p>
          ) : marcas.length === 0 ? (
            <p className={styles.notaCambio}>No hay otras marcas para cambiar en este grupo.</p>
          ) : (
            <>
              <label htmlFor={idCampo} className={styles.tituloCambio}>
                Cambiar todos por la marca
              </label>
              <select
                id={idCampo}
                className={styles.selectorMarca}
                value={marca}
                onChange={(e) => setMarca(e.target.value)}
              >
                <option value="">Elige una marca</option>
                {marcas.map((m) => (
                  <option key={m.marca} value={m.marca}>
                    {m.marca} ({m.lineas} de {activas.length})
                  </option>
                ))}
              </select>
              {plan && (
                <p className={styles.vistaPreviaLote} role="status">
                  {plan.cambian.length} de {activas.length} cambian
                  {plan.sinEsaMarca.length > 0 && `, ${plan.sinEsaMarca.length} sin esa marca`}
                  {plan.cambian.length === 0 && ". Todas ya la tienen o no la ofrecen"}.
                </p>
              )}
            </>
          )}
          <div className={styles.accionesLote}>
            <button
              type="button"
              className={styles.botonCambiar}
              onClick={aplicar}
              disabled={aplicando || !plan || plan.cambian.length === 0}
            >
              {aplicando ? "Aplicando…" : "Aplicar"}
            </button>
            <button type="button" className={styles.botonLoteSecundario} onClick={() => setAbierto(false)}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {resultado && !abierto && (
        <p className={styles.notaCambio} role="status">
          {resultado}
        </p>
      )}
      {error && (
        <p className={styles.errorCambio} role="alert">
          {error}
        </p>
      )}
    </header>
  );
}
