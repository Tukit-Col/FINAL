"use client";

import { useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  type Colegio,
  type DolorDeclarado,
  type HijoSolicitud,
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

const DOLORES: { valor: DolorDeclarado; etiqueta: string }[] = [
  { valor: "disponibilidad", etiqueta: "Que esté agotado y toque recorrer papelerías" },
  { valor: "libros", etiqueta: "Los libros y el plan lector" },
  { valor: "un_solo_lugar", etiqueta: "No encontrar todo en un solo lugar" },
  { valor: "precio", etiqueta: "El precio" },
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

export default function FormularioEmpezar({ colegios }: { colegios: Colegio[] }) {
  const router = useRouter();
  const idBase = useId();

  const [hijos, setHijos] = useState<HijoFormulario[]>([hijoVacio(1)]);
  const [correo, setCorreo] = useState("");
  const [celular, setCelular] = useState("");
  const [presupuesto, setPresupuesto] = useState("");
  const [dolor, setDolor] = useState<DolorDeclarado>("disponibilidad");
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

    const solicitud: SolicitudTrabajo = {
      contacto: { correo: correo.trim(), celular: celular.trim() },
      hijos: hijos.map<HijoSolicitud>((hijo) => ({
        referencia: hijo.referencia,
        colegio_id: hijo.colegioId,
        grado: hijo.grado,
      })),
      preferencias: {
        dolor_declarado: dolor,
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

              {/* El contrato convierte la atribucion colegio-lista en un
                  bloqueante de correccion de esta ruta: el acudiente no puede
                  detectar el error porque confia en la lista que le
                  mostramos. Cuando la atribucion es dudosa se lo decimos y le
                  ofrecemos la otra entrada, que es la unica que el si puede
                  verificar. */}
              {colegio?.atribucion_dudosa && (
                <p className={styles.avisoAtribucion} role="status">
                  Esta lista comparte plantilla con la de otro colegio y no pudimos
                  separarlas con total confianza. Si algo no te cuadra, mejor sube el
                  archivo que te mandaron.
                </p>
              )}

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
          <span className={styles.paso}>3</span> Qué te importa más
        </h2>
        <p className={styles.explicacion}>
          No te pedimos el estrato ni nada del hogar: con esto basta para elegir cuál de
          los tres kits te marcamos.
        </p>

        <fieldset className={styles.opciones}>
          <legend className={styles.leyendaSimple}>Lo que más te pesa</legend>
          {DOLORES.map((opcion) => (
            <label
              key={opcion.valor}
              className={`${styles.opcionEntrada} ${
                dolor === opcion.valor ? styles.opcionActiva : ""
              }`}
            >
              <input
                type="radio"
                name="dolor"
                value={opcion.valor}
                checked={dolor === opcion.valor}
                onChange={() => setDolor(opcion.valor)}
              />
              {opcion.etiqueta}
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
            placeholder="700000"
          />
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
