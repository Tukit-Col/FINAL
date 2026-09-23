"use client";

import { useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  type Colegio,
  type HijoSolicitud,
  type Pesos,
  type SolicitudTrabajo,
} from "@tukit/contrato";
import { crearTrabajo, FalloApi } from "@/lib/api-navegador";
import SelectorPersonaje from "./SelectorPersonaje";
import styles from "./Empezar.module.css";

type Entrada = "lista_oficial" | "archivo";

interface HijoFormulario {
  referencia: string;
  colegioId: string;
  grado: string;
  entrada: Entrada;
  archivo: File | null;
  errorArchivo: string | null;
  personajes: string;
}

// El paso 3 no es una encuesta socioeconómica: es la ÚNICA palanca del
// acudiente sobre cuál de los tres kits le marcamos. Por eso pregunta lo que el
// recomendador de verdad lee —los pesos y la disposición a pagar de más
// (`optimizador.recomendar`)— y no un "dolor" que no movía nada.
//
// El encuadre es cuánto gastar, NO precio contra calidad: la calidad asegurada
// está en los tres kits, lo que cambia es la economía. Tres opciones, cada una
// con su efecto declarado en pantalla:
//   • "Lo más económico" -> Ahorrador (el gasto manda, sin sobreprecio)
//   • "Un punto medio"   -> Ahorrador por defecto de la encuesta (P21)
//   • "Puedo estirarme"  -> Premium, si acepta pagar un poco más
// El Fan no vive aquí: se dispara solo si en el paso 1 pediste un personaje.
type ClavePrioridad = "precio" | "equilibrio" | "calidad";

interface Prioridad {
  clave: ClavePrioridad;
  titulo: string;
  detalle: string;
  // Lo que se manda al backend: los pesos suman 1.0 (el §3 lo exige, y el
  // validador de inteligencia devuelve 422 si no) y la disposición a pagar de
  // más, que es lo que destraba el Premium.
  pesos: Pesos;
  disposicion_sobreprecio: number;
}

const PRIORIDADES: Prioridad[] = [
  {
    clave: "precio",
    titulo: "Lo más económico",
    detalle: "Gastar lo menos posible. Te marcamos el Ahorrador.",
    pesos: { precio: 0.6, marca_exigida: 0.15, calidad: 0.2, personaje: 0.05 },
    disposicion_sobreprecio: 0,
  },
  {
    clave: "equilibrio",
    titulo: "Un punto medio",
    detalle: "Sin gastar de más, pero con algo de marca. Te marcamos el Ahorrador y dejamos los otros dos a la vista.",
    pesos: { precio: 0.35, marca_exigida: 0.3, calidad: 0.25, personaje: 0.1 },
    disposicion_sobreprecio: 0.05,
  },
  {
    clave: "calidad",
    titulo: "Puedo estirarme un poco",
    detalle: "Marcas y acabados de gama alta. Te marcamos el Premium si cabe en tu tope.",
    pesos: { precio: 0.15, marca_exigida: 0.35, calidad: 0.4, personaje: 0.1 },
    disposicion_sobreprecio: 0.1,
  },
];

function hijoVacio(indice: number): HijoFormulario {
  return {
    referencia: `hijo-${indice}`,
    colegioId: "",
    grado: "",
    entrada: "lista_oficial",
    archivo: null,
    errorArchivo: null,
    personajes: "",
  };
}

export default function FormularioEmpezar({
  colegios,
  surtidos,
}: {
  colegios: Colegio[];
  surtidos: string[];
}) {
  const router = useRouter();
  const idBase = useId();

  const [hijos, setHijos] = useState<HijoFormulario[]>([hijoVacio(1)]);
  const [correo, setCorreo] = useState("");
  const [celular, setCelular] = useState("");
  const [presupuesto, setPresupuesto] = useState("");
  const [prioridad, setPrioridad] = useState<ClavePrioridad>("equilibrio");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gradosDetectados, setGradosDetectados] = useState<string[]>([]);

  const porId = useMemo(() => new Map(colegios.map((c) => [c.colegio_id, c])), [colegios]);

  function cambiar(indice: number, cambio: Partial<HijoFormulario>) {
    setHijos((actuales) =>
      actuales.map((hijo, i) => (i === indice ? { ...hijo, ...cambio } : hijo)),
    );
  }

  function elegirArchivo(indice: number, elegido: File | undefined) {
    if (!elegido) return;
    const problema = validarArchivo(elegido);
    cambiar(indice, {
      archivo: problema ? null : elegido,
      errorArchivo: problema,
    });
  }

  const listo =
    correo.trim().length > 3 &&
    celular.trim().length > 6 &&
    hijos.every(
      (hijo) =>
        hijo.colegioId &&
        hijo.grado &&
        (hijo.entrada === "lista_oficial" || hijo.archivo !== null),
    );

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!listo || enviando) return;
    setEnviando(true);
    setError(null);
    setGradosDetectados([]);

    // El presupuesto es una cota DURA, no un gusto, y va en pesos enteros.
    // Se limpia aqui de puntos y espacios porque la gente lo escribe como lo
    // lee: "700.000".
    const soloDigitos = presupuesto.replace(/\D/g, "");
    const personajePorHijo: Record<string, string[]> = {};
    for (const hijo of hijos) {
      const lista = hijo.personajes
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      if (lista.length > 0) personajePorHijo[hijo.referencia] = lista;
    }

    const elegida =
      PRIORIDADES.find((p) => p.clave === prioridad) ?? PRIORIDADES[1]!;

    const solicitud: SolicitudTrabajo = {
      contacto: { correo: correo.trim(), celular: celular.trim() },
      hijos: hijos.map<HijoSolicitud>((hijo) => ({
        referencia: hijo.referencia,
        colegio_id: hijo.colegioId,
        grado: hijo.grado,
      })),
      preferencias: {
        // Lo que el recomendador de verdad lee: pesos + disposición a pagar de
        // más. Antes íbamos con `dolor_declarado`, que no movía la elección del
        // kit y hacía del paso 3 un adorno.
        pesos: elegida.pesos,
        disposicion_sobreprecio: elegida.disposicion_sobreprecio,
        ...(soloDigitos ? { presupuesto_por_hijo: Number(soloDigitos) } : {}),
        ...(Object.keys(personajePorHijo).length > 0
          ? { personaje_por_hijo: personajePorHijo }
          : {}),
      },
    };

    const archivos = hijos
      .filter((hijo) => hijo.entrada === "archivo" && hijo.archivo)
      .map((hijo) => ({ referencia: hijo.referencia, archivo: hijo.archivo as File }));

    try {
      const creado = await crearTrabajo(solicitud, archivos);
      router.push(`/esperando/${creado.trabajo_id}`);
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setError(causa.message);
        // El 422 del §2.1 trae los grados que detecto en el archivo. Son la
        // parte util del rechazo: sin ellos el acudiente no sabe que paginas
        // recortar.
        const detectados = causa.detalle["grados_detectados"];
        if (Array.isArray(detectados)) setGradosDetectados(detectados.map(String));
      } else {
        setError("No pudimos crear el pedido. Intenta de nuevo.");
      }
      setEnviando(false);
    }
  }

  return (
    <form className={styles.pagina} onSubmit={enviar}>
      <header className={styles.encabezado}>
        <h1>Armemos el kit de tu hogar</h1>
        <p>
          Es un pedido por hogar y no por hijo: así podemos juntar lo que se repite
          entre hermanos y cobrarte una caja en vez de dos sueltos.
        </p>
      </header>

      {/* ------------------------------------------------------------ Hijos */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-hijos`}>
        <h2 id={`${idBase}-hijos`} className={styles.tituloBloque}>
          <span className={styles.paso}>1</span> De quién es la lista
        </h2>

        {hijos.map((hijo, indice) => {
          const colegio = porId.get(hijo.colegioId);
          return (
            <fieldset key={hijo.referencia} className={styles.hijo}>
              <legend className={styles.leyenda}>
                Hijo {indice + 1}
                {hijos.length > 1 && (
                  <button
                    type="button"
                    className={styles.quitar}
                    onClick={() => setHijos((a) => a.filter((_, i) => i !== indice))}
                  >
                    Quitar
                  </button>
                )}
              </legend>

              <div className={styles.dosColumnas}>
                <label className={styles.campo}>
                  <span>Colegio</span>
                  <select
                    value={hijo.colegioId}
                    onChange={(e) => cambiar(indice, { colegioId: e.target.value, grado: "" })}
                    required
                  >
                    <option value="">Elige el colegio…</option>
                    {colegios.map((c) => (
                      <option key={c.colegio_id} value={c.colegio_id}>
                        {c.nombre}
                      </option>
                    ))}
                  </select>
                </label>

                <label className={styles.campo}>
                  <span>Grado</span>
                  <select
                    value={hijo.grado}
                    onChange={(e) => cambiar(indice, { grado: e.target.value })}
                    disabled={!colegio}
                    required
                  >
                    <option value="">{colegio ? "Elige el grado…" : "Primero el colegio"}</option>
                    {colegio?.grados.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className={styles.entradas} role="group" aria-label="Cómo nos das la lista">
                {(
                  [
                    ["lista_oficial", "Usar la lista que ya tiene el colegio"],
                    ["archivo", "Subir el archivo que me mandaron"],
                  ] as [Entrada, string][]
                ).map(([valor, etiqueta]) => (
                  <label
                    key={valor}
                    className={`${styles.opcionEntrada} ${
                      hijo.entrada === valor ? styles.opcionActiva : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name={`entrada-${hijo.referencia}`}
                      value={valor}
                      checked={hijo.entrada === valor}
                      onChange={() => cambiar(indice, { entrada: valor })}
                    />
                    {etiqueta}
                  </label>
                ))}
              </div>

              {hijo.entrada === "archivo" && (
                <div className={styles.zonaArchivo}>
                  {/* El aviso va ANTES de subir, no como error despues de
                      esperar: una restriccion que solo aparece cuando ya
                      perdiste el tiempo es una restriccion mal puesta. */}
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
                      elegirArchivo(indice, e.target.files?.[0]);
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
                </div>
              )}

              <SelectorPersonaje
                etiquetaHijo={`Hijo ${indice + 1}`}
                valor={hijo.personajes}
                onChange={(personajes) => cambiar(indice, { personajes })}
                surtidos={surtidos}
              />
            </fieldset>
          );
        })}

        {hijos.length < 4 && (
          <button
            type="button"
            className={styles.agregar}
            onClick={() => setHijos((a) => [...a, hijoVacio(a.length + 1)])}
          >
            + Agregar otro hijo
          </button>
        )}
      </section>

      {/* --------------------------------------------------------- Contacto */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-contacto`}>
        <h2 id={`${idBase}-contacto`} className={styles.tituloBloque}>
          <span className={styles.paso}>2</span> A dónde te avisamos
        </h2>
        <p className={styles.explicacion}>
          Armar el kit toma minutos, no segundos. No tienes que quedarte mirando la
          pantalla: te escribimos cuando esté listo.
        </p>
        <div className={styles.dosColumnas}>
          <label className={styles.campo}>
            <span>Correo</span>
            <input
              type="email"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              placeholder="tucorreo@ejemplo.com"
              autoComplete="email"
              required
            />
          </label>
          <label className={styles.campo}>
            <span>Celular</span>
            <input
              type="tel"
              value={celular}
              onChange={(e) => setCelular(e.target.value)}
              placeholder="+57 300 123 4567"
              autoComplete="tel"
              required
            />
          </label>
        </div>
      </section>

      {/* ----------------------------------------------------- Preferencias */}
      <section className={styles.bloque} aria-labelledby={`${idBase}-preferencias`}>
        <h2 id={`${idBase}-preferencias`} className={styles.tituloBloque}>
          <span className={styles.paso}>3</span> Cuál de los tres te marcamos
        </h2>
        <p className={styles.explicacion}>
          Los tres kits cubren la misma lista y la misma calidad asegurada: lo que
          cambia es cuánto gastas. Dinos hasta dónde quieres estirar el bolsillo y te
          marcamos uno —los otros dos quedan a la vista—. No te pedimos el estrato ni
          nada del hogar.
        </p>

        <fieldset className={styles.opciones}>
          <legend className={styles.leyendaSimple}>Cuánto quieres gastar</legend>
          {PRIORIDADES.map((opcion) => (
            <label
              key={opcion.clave}
              className={`${styles.tarjetaPrioridad} ${
                prioridad === opcion.clave ? styles.opcionActiva : ""
              }`}
            >
              <input
                type="radio"
                name="prioridad"
                value={opcion.clave}
                checked={prioridad === opcion.clave}
                onChange={() => setPrioridad(opcion.clave)}
              />
              <span className={styles.prioridadTexto}>
                <strong>{opcion.titulo}</strong>
                <span className={styles.prioridadDetalle}>{opcion.detalle}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <label className={styles.campo}>
          <span>
            Tope por hijo en pesos <em>(opcional, pero si lo pones lo respetamos)</em>
          </span>
          <input
            type="text"
            inputMode="numeric"
            value={presupuesto}
            onChange={(e) => setPresupuesto(e.target.value)}
            placeholder="Ej. 700000"
          />
          <span className={styles.pistaCampo}>
            Es una cota dura: si el kit que priorizas se pasa de este tope, te marcamos
            el que sí cabe y te lo decimos.
          </span>
        </label>
      </section>

      {error && (
        <div className={styles.errorCaja} role="alert">
          <strong>{error}</strong>
          {gradosDetectados.length > 0 && (
            <p>Detectamos estos grados en el archivo: {gradosDetectados.join(", ")}.</p>
          )}
        </div>
      )}

      <div className={styles.barraAccion}>
        <button type="submit" className={styles.enviar} disabled={!listo || enviando}>
          {enviando ? "Creando tu pedido…" : "Armar mis tres kits"}
        </button>
        {!listo && (
          <p className={styles.faltante}>
            Falta el colegio, el grado y cómo te avisamos.
          </p>
        )}
      </div>
    </form>
  );
}
