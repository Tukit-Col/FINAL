"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Check, LogIn, UserPlus } from "lucide-react";
import {
  formatearTamano,
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  GRADOS_CANONICOS,
  claveValida,
  reglasDeClave,
  type Colegio,
  type GradoCanonico,
  type HijoNuevo,
  type HijoSolicitud,
  type MatriculaAcudiente,
  type PerfilKit,
  type Pesos,
  type SolicitudTrabajo,
} from "@tukit/contrato";
import {
  aplicarCanonico,
  crearTrabajo,
  subirListas,
  registrarAcudiente,
  guardarMatriculas,
  iniciarSesion,
  FalloApi,
} from "@/lib/api-navegador";
import ProgresoPasos, { type PasoProgreso } from "./ProgresoPasos";
import { avisoCuentaCreada, cuentaCreadaSinSesion } from "@/lib/limite";
import { MAX_HIJOS, avisosDePrecarga, precargarHijos } from "@/lib/precarga-hijos";
import { rutaRecibimos } from "@/lib/recibimos";
import {
  CLAVE_RESTRICCIONES,
  aplicarPersonajes,
  cambiosDelAsistente,
  filtrosDePreferencias,
  leerRestriccionesGuardadas,
} from "@/lib/restricciones-asistente";
import BuscadorColegio from "@/components/BuscadorColegio";
import SelectorPersonaje from "./SelectorPersonaje";
import styles from "./Empezar.module.css";

interface HijoFormulario {
  referencia: string;
  colegioId: string;
  colegioDane: string;
  colegioNombre: string;
  grado: string;
  apodo: string;
  precargado: boolean;
  archivo: File | null;
  errorArchivo: string | null;
  personajes: string;
}

type ClavePrioridad = "precio" | "equilibrio" | "calidad";

interface Prioridad {
  clave: ClavePrioridad;
  titulo: string;
  detalle: string;
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
    detalle: "Te armamos el kit «A tu Medida»: más marca que el Ahorrador, sin llegar al precio del Premium. Si quieres, ponle un tope.",
    pesos: { precio: 0.35, marca_exigida: 0.3, calidad: 0.25, personaje: 0.1 },
    disposicion_sobreprecio: 0.05,
  },
  {
    clave: "calidad",
    titulo: "Puedo estirarme un poco",
    detalle: "Marcas y acabados de gama alta. Te marcamos el Premium.",
    pesos: { precio: 0.15, marca_exigida: 0.35, calidad: 0.4, personaje: 0.1 },
    disposicion_sobreprecio: 0.1,
  },
];

function perfilDeSeleccion(prioridad: ClavePrioridad, tienePersonaje: boolean): PerfilKit {
  if (tienePersonaje) return "Fan";
  return prioridad === "calidad" ? "Premium" : "Ahorrador";
}

function hijoVacio(indice: number): HijoFormulario {
  return {
    referencia: `hijo-${indice}`,
    colegioId: "",
    colegioDane: "",
    colegioNombre: "",
    grado: "",
    apodo: "",
    precargado: false,
    archivo: null,
    errorArchivo: null,
    personajes: "",
  };
}

function unirEnLista(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

type Modo = "elegir" | "existente" | "nuevo" | "autenticado";

export default function FormularioEmpezar({
  colegios,
  surtidos,
  canonicos,
  sesion = null,
  matriculasIniciales = [],
}: {
  colegios: Colegio[];
  surtidos: string[];
  canonicos: GradoCanonico[];
  sesion?: { correo: string } | null;
  matriculasIniciales?: MatriculaAcudiente[];
}) {
  const router = useRouter();
  const idBase = useId();

  const [modo, setModo] = useState<Modo>(sesion ? "autenticado" : "nuevo");
  const colegiosAliados = useMemo(
    () => colegios.filter((c) => c.es_partner ?? c.grados.length > 0),
    [colegios],
  );
  const [precarga] = useState(() => precargarHijos(matriculasIniciales, colegios));
  const avisosPrecarga = useMemo(
    () => avisosDePrecarga(precarga.fuera, precarga.precargados.length),
    [precarga],
  );
  const [hijos, setHijos] = useState<HijoFormulario[]>(() =>
    precarga.precargados.length > 0
      ? precarga.precargados.map((m, i) => ({
          ...hijoVacio(i + 1),
          colegioId: m.colegio_id,
          grado: m.grado,
          apodo: m.apodo ?? "",
          precargado: true,
        }))
      : [hijoVacio(1)],
  );
  const [correo, setCorreo] = useState(sesion?.correo ?? "");
  const [clave, setClave] = useState("");
  const [aceptaTerminos, setAceptaTerminos] = useState(false);
  const idReglasClave = useId();
  const [celular, setCelular] = useState("");
  const [prioridad, setPrioridad] = useState<ClavePrioridad>("equilibrio");
  const [presupuesto, setPresupuesto] = useState("");
  const conTope = prioridad === "equilibrio" && Number.parseInt(presupuesto, 10) > 0;
  const [marcasExcluidas, setMarcasExcluidas] = useState<string[]>([]);
  const [soloDisponibles, setSoloDisponibles] = useState(false);
  const hayFiltros = marcasExcluidas.length > 0 || soloDisponibles;
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [gradosDetectados, setGradosDetectados] = useState<string[]>([]);

  useEffect(() => {
    function tomar(crudo: unknown) {
      const cambios = cambiosDelAsistente(crudo);
      if (!cambios) {
        if (crudo && typeof crudo === "object") {
          setMarcasExcluidas([]);
          setSoloDisponibles(false);
        }
        return;
      }
      if (cambios.prioridad) setPrioridad(cambios.prioridad);
      setPresupuesto(cambios.presupuesto);
      setMarcasExcluidas(cambios.marcasExcluidas);
      setSoloDisponibles(cambios.soloDisponibles);
      setHijos((actuales) => aplicarPersonajes(actuales, cambios.personajes));
    }
    tomar(leerRestriccionesGuardadas(typeof window === "undefined" ? undefined : window.sessionStorage));
    const alRecibir = (evento: Event) => tomar((evento as CustomEvent<unknown>).detail);
    window.addEventListener(CLAVE_RESTRICCIONES, alRecibir);
    return () => window.removeEventListener(CLAVE_RESTRICCIONES, alRecibir);
  }, []);
  const [progreso, setProgreso] = useState<{
    registroFirma?: string;
    sinSesion?: boolean;
    matriculasFirma?: string;
    trabajoId?: string;
    trabajoFirma?: string;
  }>({});

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

  function gradoVerificado(hijo: HijoFormulario): boolean {
    return porId.get(hijo.colegioId)?.grados.includes(hijo.grado) ?? false;
  }

  function necesitaArchivo(hijo: HijoFormulario): boolean {
    if (!hijo.colegioId) return true;
    return hijo.grado !== "" && !gradoVerificado(hijo);
  }

  function hijoCompleto(hijo: HijoFormulario): boolean {
    if (!hijo.grado) return false;
    if (!hijo.colegioId) return Boolean(hijo.colegioNombre) && hijo.archivo !== null;
    if (necesitaArchivo(hijo)) return hijo.archivo !== null;
    return true;
  }

  const pideContacto = modo === "nuevo";
  const listo =
    (!pideContacto ||
      (correo.trim().length > 3 &&
        celular.trim().length > 6 &&
        claveValida(clave) &&
        aceptaTerminos)) &&
    hijos.every(hijoCompleto);

  const faltantesContacto: string[] = [];
  if (pideContacto) {
    if (correo.trim().length <= 3) faltantesContacto.push("tu correo");
    if (!claveValida(clave)) faltantesContacto.push("una contraseña de al menos 8 caracteres");
    if (!aceptaTerminos) faltantesContacto.push("aceptar la política de datos y los términos");
    if (celular.trim().length <= 6) faltantesContacto.push("tu celular");
  }

  const faltantesHijos: string[] = [];
  hijos.forEach((hijo, i) => {
    const suf = hijos.length > 1 ? ` del hijo ${i + 1}` : "";
    const tieneColegio = Boolean(hijo.colegioId) || Boolean(hijo.colegioNombre);
    if (!tieneColegio) faltantesHijos.push(`el colegio${suf}`);
    else if (!hijo.grado) faltantesHijos.push(`el grado${suf}`);
    else if (necesitaArchivo(hijo) && hijo.archivo === null) faltantesHijos.push(`la lista${suf}`);
  });

  const faltantes =
    modo === "nuevo"
      ? [...faltantesContacto, ...faltantesHijos]
      : [...faltantesHijos, ...faltantesContacto];

  const mostrarFormulario = modo === "nuevo" || modo === "autenticado";
  const pasoHijos = modo === "nuevo" ? 2 : 1;
  const pasoContacto = 2;
  const pasoPrioridad = 3;

  type PasoEmpezar = "registro" | "hijos" | "contacto" | "preferencias";
  const ORDEN_PASOS: PasoEmpezar[] = ["registro", "hijos", "contacto", "preferencias"];
  function pasoActual(): PasoEmpezar | null {
    if (!mostrarFormulario) return null;
    if (modo === "nuevo" && faltantesContacto.length > 0) return "registro";
    if (faltantesHijos.length > 0) return "hijos";
    return "preferencias";
  }
  const actual = pasoActual();
  function estadoDePaso(paso: PasoEmpezar): PasoProgreso["estado"] {
    if (actual === null) return "futuro";
    if (paso === actual) return "actual";
    if (ORDEN_PASOS.indexOf(paso) > ORDEN_PASOS.indexOf(actual)) return "futuro";
    const faltantes = paso === "hijos" ? faltantesHijos : paso === "contacto" ? faltantesContacto : [];
    return faltantes.length === 0 ? "completo" : "futuro";
  }
  const pasosProgreso: PasoProgreso[] = (
    modo === "nuevo"
      ? ([
          ["registro", "Regístrate"],
          ["hijos", "De quién es la lista"],
          ["preferencias", "Cuál kit te marcamos"],
        ] as const)
      : ([
          ["hijos", "De quién es la lista"],
          ["contacto", "A dónde te avisamos"],
          ["preferencias", "Cuál kit te marcamos"],
        ] as const)
  ).map(([clave, titulo]) => ({ clave, titulo, estado: estadoDePaso(clave) }));

  function propsDePaso(paso: PasoEmpezar): { className: string; "aria-current"?: "step" } {
    const futuro = actual !== null && ORDEN_PASOS.indexOf(paso) > ORDEN_PASOS.indexOf(actual);
    const completo = estadoDePaso(paso) === "completo";
    return {
      className: futuro
        ? `${styles.bloque} ${styles.bloqueInactivo}`
        : completo
          ? `${styles.bloque} ${styles.bloqueCompleto}`
          : styles.bloque,
      ...(paso === actual ? { "aria-current": "step" as const } : {}),
    };
  }

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!listo || enviando) return;
    setEnviando(true);
    setError(null);
    setAviso(null);
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

    const contacto = { correo: correo.trim(), celular: celular.trim() };

    const preferencias = {
      pesos: elegida.pesos,
      disposicion_sobreprecio: elegida.disposicion_sobreprecio,
      prioridad: elegida.clave,
      ...(conTope ? { presupuesto_por_hijo: Number.parseInt(presupuesto, 10) } : {}),
      ...(Object.keys(personajePorHijo).length > 0
        ? { personaje_por_hijo: personajePorHijo }
        : {}),
      ...filtrosDePreferencias(marcasExcluidas, soloDisponibles),
    };

    if (modo === "nuevo") {
      const registro = {
        correo: contacto.correo,
        clave,
        acepta_terminos: aceptaTerminos,
        celular: contacto.celular,
        hijos: hijos
          .filter((hijo) => hijo.colegioId)
          .map((hijo) => ({
            colegio_id: hijo.colegioId,
            grado: hijo.grado,
            ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim() } : {}),
          })),
      };
      const firmaRegistro = JSON.stringify(registro);
      if (progreso.registroFirma !== firmaRegistro) {
        try {
          await registrarAcudiente(registro);
          setProgreso((p) => ({ ...p, registroFirma: firmaRegistro, sinSesion: false }));
        } catch (causa) {
          if (causa instanceof FalloApi && causa.codigo === "correo_ya_registrado") {
            setError(causa.message);
            setModo("existente");
          } else if (causa instanceof FalloApi && cuentaCreadaSinSesion(causa)) {
            setProgreso((p) => ({ ...p, registroFirma: firmaRegistro, sinSesion: true }));
            setError(avisoCuentaCreada(causa));
          } else if (causa instanceof FalloApi) setError(causa.message);
          else setError("No pudimos crear tu cuenta. Intenta de nuevo.");
          setEnviando(false);
          return;
        }
      } else if (progreso.sinSesion) {
        try {
          await iniciarSesion({ correo: contacto.correo, clave });
          setProgreso((p) => ({ ...p, sinSesion: false }));
        } catch (causa) {
          if (causa instanceof FalloApi && causa.estado === 429) setError(avisoCuentaCreada(causa));
          else if (causa instanceof FalloApi) setError(causa.message);
          else setError("No pudimos entrar a tu cuenta. Intenta de nuevo.");
          setEnviando(false);
          return;
        }
      }
    }

    if (modo === "autenticado") {
      const nuevos: HijoNuevo[] = hijos
        .filter((hijo) => !hijo.precargado && hijo.colegioId)
        .map((hijo) => ({
          colegio_id: hijo.colegioId,
          grado: hijo.grado,
          ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim() } : {}),
        }));
      if (nuevos.length > 0) {
        const firmaMatriculas = JSON.stringify(nuevos);
        if (progreso.matriculasFirma !== firmaMatriculas) {
          try {
            await guardarMatriculas(nuevos);
            setProgreso((p) => ({ ...p, matriculasFirma: firmaMatriculas }));
          } catch {
            setAviso(
              "No pudimos guardar tus hijos nuevos en tu cuenta, pero seguimos con tu kit. Podrás agregarlos más tarde.",
            );
          }
        }
      }
    }

    const hijosVerificados = hijos.filter(
      (hijo) => hijo.colegioId && gradoVerificado(hijo),
    );
    const hijosSubida = hijos.filter((hijo) => necesitaArchivo(hijo) && hijo.archivo);

    const soloHijo = hijos.length === 1 ? hijos[0] : null;
    const canonicoDelHijo =
      soloHijo && soloHijo.colegioId && gradoVerificado(soloHijo)
        ? canonicos.find(
            (c) => c.colegio_id === soloHijo.colegioId && c.grado === soloHijo.grado,
          )
        : undefined;

    if (soloHijo && canonicoDelHijo && prioridad !== "equilibrio" && !hayFiltros) {
      const personaje = personajePorHijo[soloHijo.referencia]?.[0];
      try {
        const aplicado = await aplicarCanonico({
          colegio_id: canonicoDelHijo.colegio_id,
          grado: canonicoDelHijo.grado,
          anio_lectivo: canonicoDelHijo.anio_lectivo,
          perfil: perfilDeSeleccion(prioridad, Boolean(personaje)),
          ...(personaje ? { personaje } : {}),
          ...(soloHijo.apodo.trim() ? { apodo: soloHijo.apodo.trim().slice(0, 40) } : {}),
        });
        router.push(`/kits/${aplicado.trabajo_id}`);
        if (modo === "nuevo") router.refresh();
        return;
      } catch (causa) {
        if (causa instanceof FalloApi) setError(causa.message);
        else setError("No pudimos armar tu kit. Intenta de nuevo.");
        setEnviando(false);
        return;
      }
    }

    try {
      let trabajoInstantaneo: string | null = null;

      if (hijosVerificados.length > 0) {
        const solicitud: SolicitudTrabajo = {
          hijos: hijosVerificados.map<HijoSolicitud>((hijo) => ({
            referencia: hijo.referencia,
            colegio_id: hijo.colegioId,
            grado: hijo.grado,
            ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim().slice(0, 40) } : {}),
          })),
          preferencias,
        };
        const firmaTrabajo = JSON.stringify(solicitud);
        if (progreso.trabajoId && progreso.trabajoFirma === firmaTrabajo) {
          trabajoInstantaneo = progreso.trabajoId;
        } else {
          const creado = await crearTrabajo(solicitud);
          trabajoInstantaneo = creado.trabajo_id;
          setProgreso((p) => ({ ...p, trabajoId: creado.trabajo_id, trabajoFirma: firmaTrabajo }));
        }
      }

      if (hijosSubida.length > 0) {
        const resultado = await subirListas(
          hijosSubida.map((hijo) => ({
            referencia: hijo.referencia,
            ...(hijo.colegioId
              ? { colegio_id: hijo.colegioId }
              : hijo.colegioDane
                ? { colegio_dane: hijo.colegioDane, colegio_nombre: hijo.colegioNombre }
                : { colegio_nombre: hijo.colegioNombre }),
            grado: hijo.grado,
            ...(hijo.apodo.trim() ? { apodo: hijo.apodo.trim().slice(0, 40) } : {}),
          })),
          hijosSubida.map((hijo) => ({
            referencia: hijo.referencia,
            archivo: hijo.archivo as File,
          })),
          undefined,
          preferencias,
        );
        router.push(rutaRecibimos(resultado.subidas, trabajoInstantaneo));
        if (modo === "nuevo") router.refresh();
        return;
      }

      router.push(`/esperando/${trabajoInstantaneo}`);
      if (modo === "nuevo") router.refresh();
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setError(causa.message);
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

      {modo !== "autenticado" && (
        <div className={styles.dosColumnas} role="group" aria-label="¿Ya tienes cuenta?">
          <button
            type="button"
            aria-pressed={modo === "existente"}
            className={`${styles.opcionEntrada} ${modo === "existente" ? styles.opcionActiva : ""}`}
            onClick={() => setModo("existente")}
          >
            <LogIn size={16} strokeWidth={2.4} aria-hidden="true" />
            <span className={styles.opcionTexto}>
              <strong>Ya tengo cuenta, ingresar</strong>
              <span>Te precargamos a tus hijos: no vuelves a escribir su colegio ni su grado.</span>
            </span>
          </button>
          <button
            type="button"
            aria-pressed={modo === "nuevo"}
            className={`${styles.opcionEntrada} ${modo === "nuevo" ? styles.opcionActiva : ""}`}
            onClick={() => setModo("nuevo")}
          >
            <UserPlus size={16} strokeWidth={2.4} aria-hidden="true" />
            <span className={styles.opcionTexto}>
              <strong>Crear cuenta nueva</strong>
              <span>Guardamos tus pedidos y a tus hijos para la próxima vez.</span>
            </span>
          </button>
        </div>
      )}

      {mostrarFormulario && <ProgresoPasos pasos={pasosProgreso} />}

      {modo === "existente" && (
        <section className={styles.bloque}>
          <p className={styles.explicacion}>
            Entra con tu cuenta y te precargamos a tus hijos: no vuelves a teclear su
            colegio ni su grado, solo eliges el kit.
          </p>
          <Link href="/ingresar?destino=/empezar" className={styles.enviar}>
            <LogIn size={17} strokeWidth={2.6} aria-hidden="true" />
            Ingresar a mi cuenta
          </Link>
        </section>
      )}

      {modo === "nuevo" && (
        <section {...propsDePaso("registro")} aria-labelledby={`${idBase}-registro`}>
          <h2 id={`${idBase}-registro`} className={styles.tituloBloque}>
            <span className={styles.paso}>1</span> Regístrate
          </h2>
          <p className={styles.explicacion}>
            Creamos tu cuenta para guardar tus pedidos y avisarte cuando el kit esté
            listo. La próxima vez entras y ya tienes a tus hijos cargados.
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
            <div className={styles.campo}>
              <label htmlFor={`${idReglasClave}-clave`}>
                <span>Contraseña</span>
              </label>
              <input
                id={`${idReglasClave}-clave`}
                type="password"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                placeholder="Elige una contraseña"
                autoComplete="new-password"
                aria-describedby={idReglasClave}
                required
              />
              <ul id={idReglasClave} className={styles.reglasClave} aria-live="polite">
                {reglasDeClave(clave).map((regla) => (
                  <li key={regla.id} className={regla.cumple ? styles.reglaCumple : styles.reglaPendiente}>
                    <Check size={13} aria-hidden="true" strokeWidth={3} />
                    {regla.texto}
                    <span className={styles.soloLectores}>{regla.cumple ? " (listo)" : " (falta)"}</span>
                  </li>
                ))}
              </ul>
            </div>
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
          <label className={styles.casillaTerminos}>
            <input
              type="checkbox"
              checked={aceptaTerminos}
              onChange={(e) => setAceptaTerminos(e.target.checked)}
              required
            />
            <span>
              Leí y acepto la{" "}
              <Link href="/legal/privacidad" target="_blank" rel="noopener noreferrer">
                política de tratamiento de datos personales
              </Link>{" "}
              y los{" "}
              <Link href="/legal/terminos" target="_blank" rel="noopener noreferrer">
                términos y condiciones
              </Link>
              .
            </span>
          </label>
        </section>
      )}

      {mostrarFormulario && (
        <>
      <section {...propsDePaso("hijos")} aria-labelledby={`${idBase}-hijos`}>
        <h2 id={`${idBase}-hijos`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoHijos}</span> De quién es la lista
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

              <BuscadorColegio
                colegiosAliados={colegiosAliados}
                colegioId={hijo.colegioId}
                colegioDane={hijo.colegioDane}
                colegioNombre={hijo.colegioNombre}
                onElegirAliado={(colegioId) =>
                  cambiar(indice, { colegioId, colegioDane: "", colegioNombre: "", grado: "" })
                }
                onElegirDirectorio={({ dane, nombre }) =>
                  cambiar(indice, { colegioId: "", colegioDane: dane, colegioNombre: nombre, grado: "" })
                }
                onEscribir={(nombre) =>
                  cambiar(indice, { colegioId: "", colegioDane: "", colegioNombre: nombre, grado: "" })
                }
                onCambiar={() =>
                  cambiar(indice, { colegioId: "", colegioDane: "", colegioNombre: "", grado: "" })
                }
              />

              {(hijo.colegioId || hijo.colegioNombre) &&
                (modo === "nuevo" || (modo === "autenticado" && !hijo.precargado)) && (
                  <label className={styles.campo}>
                    <span>Apodo de tu hijo (opcional)</span>
                    <input
                      type="text"
                      value={hijo.apodo}
                      onChange={(e) => cambiar(indice, { apodo: e.target.value })}
                      placeholder="Escribe el apodo de tu hijo para personalizar tu kit"
                      autoComplete="off"
                    />
                  </label>
                )}
              {modo === "autenticado" && hijo.precargado && hijo.apodo && (
                <p className={styles.apodoPrecargado}>Apodo: {hijo.apodo}</p>
              )}

              {(colegio || hijo.colegioNombre) && (
                <div className={styles.gradoBloque}>
                  <span className={styles.campoRotulo}>Grado</span>
                  <div className={styles.gradoChips} role="radiogroup" aria-label="Elige el grado">
                    {GRADOS_CANONICOS.map((g) => {
                      const activo = hijo.grado === g;
                      const oficial = Boolean(hijo.colegioId);
                      const verificado = oficial && (colegio?.grados.includes(g) ?? false);
                      const clase = activo
                        ? styles.chipGradoActivo
                        : verificado
                          ? styles.chipGradoVerificado
                          : "";
                      return (
                        <button
                          key={g}
                          type="button"
                          role="radio"
                          aria-checked={activo}
                          aria-label={
                            oficial
                              ? `${g}, ${verificado ? "con lista verificada" : "sin lista verificada"}`
                              : g
                          }
                          title={
                            oficial
                              ? verificado
                                ? "Tiene lista verificada del colegio"
                                : "Sin lista verificada todavía"
                              : undefined
                          }
                          className={`${styles.chipGrado} ${clase}`}
                          onClick={() => cambiar(indice, { grado: g })}
                        >
                          {g}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {colegio &&
                hijo.grado !== "" &&
                !colegio.grados.includes(hijo.grado) && (
                  <div className={styles.zonaListaGrado}>
                    <span className={styles.campoRotulo}>Subir lista de grado ({hijo.grado})</span>
                    <p className={styles.reglaArchivo}>
                      Este grado todavía no tiene lista verificada del colegio.
                      Adjunta tu lista y la revisamos para armar el kit.
                    </p>
                    <input
                      id={`lista-grado-${hijo.referencia}`}
                      type="file"
                      className={styles.inputArchivo}
                      accept={EXTENSIONES_ACEPTADAS.join(",")}
                      onChange={(e) => {
                        elegirArchivo(indice, e.target.files?.[0]);
                        e.target.value = "";
                      }}
                    />
                    <label htmlFor={`lista-grado-${hijo.referencia}`} className={styles.soltar}>
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

              {!hijo.colegioId && hijo.colegioNombre && (
                <div className={styles.zonaArchivo}>
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

                  {hijo.colegioNombre && hijo.grado && !error && (
                    <p className={styles.sugerenciaOk} role="status">
                      <Check size={16} strokeWidth={3} aria-hidden="true" />
                      Con esto revisamos tu lista, armamos tu kit y dejamos {hijo.colegioNombre} ·{" "}
                      {hijo.grado} verificado para los demás.
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

        {modo === "autenticado" &&
          avisosPrecarga.map((texto) => (
            <p key={texto} className={styles.avisoCaja} role="status">
              {texto}
            </p>
          ))}

        {hijos.length < MAX_HIJOS && (
          <button
            type="button"
            className={styles.agregar}
            onClick={() =>
              setHijos((a) => [
                ...a,
                hijoVacio(Math.max(0, ...a.map((h) => Number(h.referencia.slice(5)) || 0)) + 1),
              ])
            }
          >
            + Agregar otro hijo
          </button>
        )}
      </section>

      {modo !== "nuevo" && (
      <section {...propsDePaso("contacto")} aria-labelledby={`${idBase}-contacto`}>
        <h2 id={`${idBase}-contacto`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoContacto}</span> A dónde te avisamos
        </h2>
        <p className={styles.explicacion}>
          Armar el kit toma minutos, no segundos, porque una persona revisa cada
          lista para que la calidad no falle. No tienes que quedarte mirando la
          pantalla: te escribimos cuando esté listo.
        </p>
        <p className={styles.explicacion}>
          Te avisamos a los datos de tu cuenta
          {sesion?.correo ? (
            <>
              : <strong>{sesion.correo}</strong>
            </>
          ) : null}
          .
        </p>
      </section>
      )}

      <section {...propsDePaso("preferencias")} aria-labelledby={`${idBase}-preferencias`}>
        <h2 id={`${idBase}-preferencias`} className={styles.tituloBloque}>
          <span className={styles.paso}>{pasoPrioridad}</span> Cuál kit te marcamos
        </h2>
        <p className={styles.explicacion}>
          Todos los kits llevan la misma lista; lo que cambia es la marca de cada
          producto y, con ella, cuánto gastas. Siempre verás el Ahorrador y el
          Premium, y te marcamos el que va con lo que elijas aquí. No preguntamos por
          el estrato ni por nada del hogar.
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

        {hayFiltros && (
          <p className={styles.explicacion}>
            Tu kit va {marcasExcluidas.length > 0 ? `sin ${marcasExcluidas.join(", ")}` : ""}
            {marcasExcluidas.length > 0 && soloDisponibles ? " y " : ""}
            {soloDisponibles ? "solo con productos que hay hoy" : ""}.{" "}
            <button
              type="button"
              className={styles.quitar}
              onClick={() => {
                setMarcasExcluidas([]);
                setSoloDisponibles(false);
              }}
            >
              Quitar
            </button>
          </p>
        )}

        {prioridad === "equilibrio" && (
          <div className={styles.panelTope}>
            <label className={styles.campo}>
              <span>
                Tope para tu kit «A tu Medida» <em>(opcional)</em>
              </span>
              <input
                type="text"
                inputMode="numeric"
                value={presupuesto ? `$ ${Number(presupuesto).toLocaleString("es-CO")}` : ""}
                onChange={(e) => setPresupuesto(e.target.value.replace(/\D/g, "").slice(0, 9))}
                placeholder="Ej.: 350.000"
                aria-describedby={`${idBase}-ayuda-presupuesto`}
              />
            </label>
            <p id={`${idBase}-ayuda-presupuesto`} className={styles.ayudaTope}>
              {conTope
                ? "Te armamos la mejor marca que no pase de este tope. Si ni el kit más barato cabe, te lo decimos con su precio."
                : "Sin tope, «A tu Medida» sube de marca donde vale la pena, sin pasar de la mitad de camino entre el precio del Ahorrador y el del Premium."}
            </p>
          </div>
        )}
      </section>

      {error && (
        <div className={styles.errorCaja} role="alert">
          <strong>{error}</strong>
          {gradosDetectados.length > 0 && (
            <p>Detectamos estos grados en el archivo: {gradosDetectados.join(", ")}.</p>
          )}
        </div>
      )}

      {aviso && (
        <div className={styles.avisoCaja} role="status">
          {aviso}
        </div>
      )}

      <div className={styles.barraAccion}>
        <button type="submit" className={styles.enviar} disabled={!listo || enviando}>
          {enviando ? "Creando tu pedido…" : "Armar mis kits"}
        </button>
        {!listo && (
          <p className={styles.faltante}>
            {faltantes.length > 0
              ? `${faltantes.length === 1 ? "Falta" : "Faltan"} ${unirEnLista(faltantes)} para continuar.`
              : "Completa los datos que faltan para continuar."}
          </p>
        )}
      </div>
        </>
      )}
    </form>
  );
}
