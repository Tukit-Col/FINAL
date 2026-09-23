"use client";

import { useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Check, School, Send } from "lucide-react";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  GRADOS_CANONICOS,
  type Colegio,
  type HijoSolicitud,
  type Pesos,
  type SolicitudTrabajo,
} from "@tukit/contrato";
import { crearTrabajo, sugerirColegio, FalloApi } from "@/lib/api-navegador";
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
  // Estado de la sugerencia de colegio (solo en la ruta "subir archivo", cuando
  // el par no es aliado todavía). null = sin enviar; luego el tarea_id.
  sugerido: string | null;
  sugiriendo: boolean;
  errorSugerencia: string | null;
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
    sugerido: null,
    sugiriendo: false,
    errorSugerencia: null,
  };
}

// Iniciales del colegio para el avatar cuando no hay logo: dos letras de las
// dos primeras palabras significativas, en mayúscula.
function iniciales(nombre: string): string {
  const palabras = nombre
    .split(/\s+/)
    .filter((p) => p.length > 2 && !/^(de|del|la|el|los|las|y)$/i.test(p));
  const base = palabras.length > 0 ? palabras : nombre.split(/\s+/);
  return base
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

// ------------------------------------------------------- Selector de colegio

function SelectorColegio({
  colegios,
  valor,
  onElegir,
}: {
  colegios: Colegio[];
  valor: string;
  onElegir: (colegioId: string) => void;
}) {
  const [busqueda, setBusqueda] = useState("");
  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return colegios;
    return colegios.filter((c) => c.nombre.toLowerCase().includes(q));
  }, [colegios, busqueda]);

  return (
    <div className={styles.colegioBloque}>
      <span className={styles.campoRotulo}>Colegio</span>
      <div className={styles.buscador}>
        <Search size={16} strokeWidth={2.4} aria-hidden="true" />
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Busca tu colegio…"
          aria-label="Buscar colegio"
        />
      </div>
      <div className={styles.listaColegios} role="radiogroup" aria-label="Elige el colegio">
        {filtrados.map((c) => {
          const activo = c.colegio_id === valor;
          return (
            <button
              key={c.colegio_id}
              type="button"
              role="radio"
              aria-checked={activo}
              className={`${styles.tarjetaColegio} ${activo ? styles.colegioActivo : ""}`}
              onClick={() => onElegir(c.colegio_id)}
            >
              <span className={styles.logoColegio} aria-hidden="true">
                {c.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.logo_url} alt="" />
                ) : (
                  <span className={styles.logoIniciales}>{iniciales(c.nombre)}</span>
                )}
              </span>
              <span className={styles.colegioTexto}>
                <span className={styles.colegioNombre}>{c.nombre}</span>
                <span className={styles.colegioMeta}>
                  {c.grados.length === 0
                    ? "Sin lista verificada · sube el archivo"
                    : `${c.grados.length} ${c.grados.length === 1 ? "grado verificado" : "grados verificados"}`}
                </span>
              </span>
              {activo && (
                <span className={styles.colegioMarca} aria-hidden="true">
                  <Check size={14} strokeWidth={3.2} />
                </span>
              )}
            </button>
          );
        })}
        {filtrados.length === 0 && (
          <p className={styles.sinColegios}>
            <School size={18} strokeWidth={2} aria-hidden="true" />
            No encontramos ese colegio entre los aliados todavía.
          </p>
        )}
      </div>
    </div>
  );
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

  async function sugerir(indice: number) {
    const hijo = hijos[indice];
    if (!hijo || !hijo.colegioId || !hijo.grado || hijo.sugiriendo) return;
    cambiar(indice, { sugiriendo: true, errorSugerencia: null });
    try {
      const { tarea_id } = await sugerirColegio({
        colegioId: hijo.colegioId,
        grado: hijo.grado,
        anioLectivo: new Date().getFullYear(),
        archivo: hijo.archivo,
      });
      cambiar(indice, { sugerido: tarea_id, sugiriendo: false });
    } catch (causa) {
      cambiar(indice, {
        sugiriendo: false,
        errorSugerencia:
          causa instanceof FalloApi
            ? causa.message
            : "No pudimos enviar la sugerencia. Intenta de nuevo.",
      });
    }
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
        // más. El tope por hijo salió del formulario a pedido del acudiente; el
        // encuadre del paso 3 ya es "hasta dónde estirar el bolsillo".
        pesos: elegida.pesos,
        disposicion_sobreprecio: elegida.disposicion_sobreprecio,
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

              <SelectorColegio
                colegios={colegios}
                valor={hijo.colegioId}
                onElegir={(colegioId) =>
                  cambiar(indice, { colegioId, grado: "", sugerido: null, errorSugerencia: null })
                }
              />

              {colegio &&
                (() => {
                  // La ruta "lista oficial" solo puede usar grados VERIFICADOS
                  // (los únicos con la ruta rápida a optimización). La ruta
                  // "subir archivo" no depende de eso: el grado sale del PDF que
                  // el acudiente manda, así que ahí se ofrecen todos los grados
                  // canónicos —es lo que hace usable un colegio sin lista
                  // verificada todavía, que es justo cuando se sugiere—.
                  const grados =
                    hijo.entrada === "archivo" ? GRADOS_CANONICOS : colegio.grados;
                  if (grados.length === 0) return null;
                  return (
                    <div className={styles.gradoBloque}>
                      <span className={styles.campoRotulo}>Grado</span>
                      <div
                        className={styles.gradoChips}
                        role="radiogroup"
                        aria-label="Elige el grado"
                      >
                        {grados.map((g) => {
                          const activo = hijo.grado === g;
                          return (
                            <button
                              key={g}
                              type="button"
                              role="radio"
                              aria-checked={activo}
                              className={`${styles.chipGrado} ${activo ? styles.chipGradoActivo : ""}`}
                              onClick={() => cambiar(indice, { grado: g })}
                            >
                              {g}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}

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
                      onChange={() => cambiar(indice, { entrada: valor, grado: "" })}
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

                  {/* Sugerir el colegio+grado al backlog del administrador: el PDF
                      que subiste es la mejor semilla de onboarding, así que en vez
                      de quedarse solo en tu pedido lo mandamos a que lo verifiquen
                      y quede como lista aliada para el próximo acudiente. */}
                  <div className={styles.sugerencia}>
                    {hijo.sugerido ? (
                      <p className={styles.sugerenciaOk} role="status">
                        <Check size={16} strokeWidth={3} aria-hidden="true" />
                        Listo: le mandamos tu lista al equipo. La revisamos y queda
                        como lista verificada del colegio.
                      </p>
                    ) : (
                      <>
                        <div className={styles.sugerenciaTexto}>
                          <strong>¿Quieres que quede como lista del colegio?</strong>
                          <span>
                            Mándanos este colegio y grado con tu archivo: lo revisamos
                            a mano y lo dejamos verificado para todos.
                          </span>
                        </div>
                        <button
                          type="button"
                          className={styles.botonSugerir}
                          disabled={!hijo.colegioId || !hijo.grado || hijo.sugiriendo}
                          onClick={() => sugerir(indice)}
                        >
                          <Send size={15} strokeWidth={2.6} aria-hidden="true" />
                          {hijo.sugiriendo ? "Enviando…" : "Sugerir mi colegio"}
                        </button>
                      </>
                    )}
                    {hijo.errorSugerencia && (
                      <p className={styles.errorCampo} role="alert">
                        {hijo.errorSugerencia}
                      </p>
                    )}
                  </div>
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
          Armar el kit toma minutos, no segundos, porque una persona revisa cada
          lista para que la calidad no falle. No tienes que quedarte mirando la
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
          Los tres kits llevan la misma lista y la misma calidad. Lo único que cambia
          es cuánto gastas. Dinos hasta dónde quieres estirar el bolsillo y te marcamos
          uno; los otros dos quedan a la vista. No preguntamos por el estrato ni por
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
