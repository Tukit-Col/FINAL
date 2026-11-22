// Formulario de `/empezar`: de quién es la lista, cuál kit marcar y el envío.
//
// Decisiones:
// - Es un pedido por hogar y no por hijo, para poder juntar lo que se repite entre hermanos.
// - Cada paso del envío (registro, matrículas, trabajo) guarda la firma de lo que ya hizo, así un
//   reintento tras un fallo no repite lo que ya salió bien.
// - Camino rápido: con un solo hijo de lista verificada, sin tope ni filtros y sin el punto medio,
//   se aplica el kit canónico del grado en vez de crear un trabajo.
// - Las reglas y los cuerpos de las peticiones viven en `lib/formulario-empezar` y
//   `lib/envio-empezar`; las secciones de pantalla, en los componentes vecinos.

"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LogIn } from "lucide-react";
import {
  claveValida,
  validarArchivo,
  type Colegio,
  type GradoCanonico,
  type MatriculaAcudiente,
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
  leerRestriccionesGuardadas,
} from "@/lib/restricciones-asistente";
import {
  contactoCompleto,
  estadoDePaso,
  faltantesDeContacto,
  faltantesDeHijos,
  faltantesEnOrden,
  hijoCompleto,
  hijoVacio,
  pasoActual,
  pasoEsFuturo,
  perfilDeSeleccion,
  siguienteReferencia,
  unirEnLista,
  type ClavePrioridad,
  type HijoFormulario,
  type Modo,
  type PasoEmpezar,
} from "@/lib/formulario-empezar";
import {
  archivosDeSubida,
  canonicoDelUnicoHijo,
  construirPreferencias,
  construirRegistro,
  construirSolicitud,
  cuerpoCanonico,
  destinoDeSubida,
  hijosConListaVerificada,
  hijosParaSubir,
  matriculasNuevas,
  personajesPorHijo,
} from "@/lib/envio-empezar";
import BloqueHijo from "./BloqueHijo";
import SelectorCamino from "./SelectorCamino";
import SeccionContacto from "./SeccionContacto";
import SeccionPreferencias from "./SeccionPreferencias";
import SeccionRegistro, { type PropsSeccion } from "./SeccionRegistro";
import styles from "./Empezar.module.css";

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

  const pideContacto = modo === "nuevo";
  const datosContacto = {
    correo,
    celular,
    claveOk: claveValida(clave),
    aceptaTerminos,
  };
  const listo =
    (!pideContacto || contactoCompleto(datosContacto)) &&
    hijos.every((hijo) => hijoCompleto(hijo, porId));

  const faltantesContacto = pideContacto ? faltantesDeContacto(datosContacto) : [];
  const faltantesHijos = faltantesDeHijos(hijos, porId);
  const faltantesPorPaso = { contacto: faltantesContacto, hijos: faltantesHijos };
  const faltantes = faltantesEnOrden(modo, faltantesPorPaso);

  const mostrarFormulario = modo === "nuevo" || modo === "autenticado";
  const pasoHijos = modo === "nuevo" ? 2 : 1;
  const pasoContacto = 2;
  const pasoPrioridad = 3;

  const actual = pasoActual(modo, faltantesPorPaso);
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
  ).map(([clavePaso, titulo]) => ({
    clave: clavePaso,
    titulo,
    estado: estadoDePaso(clavePaso, actual, faltantesPorPaso),
  }));

  function propsDePaso(paso: PasoEmpezar): PropsSeccion {
    const futuro = pasoEsFuturo(paso, actual);
    const completo = estadoDePaso(paso, actual, faltantesPorPaso) === "completo";
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

    const personajePorHijo = personajesPorHijo(hijos);
    const contacto = { correo: correo.trim(), celular: celular.trim() };
    const preferencias = construirPreferencias({
      prioridad,
      presupuesto,
      conTope,
      personajePorHijo,
      marcasExcluidas,
      soloDisponibles,
    });

    if (modo === "nuevo") {
      const registro = construirRegistro({ ...contacto, clave, aceptaTerminos }, hijos);
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
      const nuevos = matriculasNuevas(hijos);
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

    const hijosVerificados = hijosConListaVerificada(hijos, porId);
    const hijosSubida = hijosParaSubir(hijos, porId);

    const rapido = canonicoDelUnicoHijo(hijos, canonicos, porId);
    if (rapido && prioridad !== "equilibrio" && !hayFiltros) {
      const { soloHijo, canonico } = rapido;
      const personaje = personajePorHijo[soloHijo.referencia]?.[0];
      try {
        const aplicado = await aplicarCanonico(
          cuerpoCanonico(soloHijo, canonico, perfilDeSeleccion(prioridad, Boolean(personaje)), personaje),
        );
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
        const solicitud = construirSolicitud(hijosVerificados, preferencias);
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
          hijosSubida.map(destinoDeSubida),
          archivosDeSubida(hijosSubida),
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

      {modo !== "autenticado" && <SelectorCamino modo={modo} onElegir={setModo} />}

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
        <SeccionRegistro
          propsSeccion={propsDePaso("registro")}
          idBase={idBase}
          idReglasClave={idReglasClave}
          correo={correo}
          onCorreo={setCorreo}
          clave={clave}
          onClave={setClave}
          celular={celular}
          onCelular={setCelular}
          aceptaTerminos={aceptaTerminos}
          onAceptaTerminos={setAceptaTerminos}
        />
      )}

      {mostrarFormulario && (
        <>
          <section {...propsDePaso("hijos")} aria-labelledby={`${idBase}-hijos`}>
            <h2 id={`${idBase}-hijos`} className={styles.tituloBloque}>
              <span className={styles.paso}>{pasoHijos}</span> De quién es la lista
            </h2>

            {hijos.map((hijo, indice) => (
              <BloqueHijo
                key={hijo.referencia}
                hijo={hijo}
                indice={indice}
                totalHijos={hijos.length}
                modo={modo}
                colegio={porId.get(hijo.colegioId)}
                colegiosAliados={colegiosAliados}
                surtidos={surtidos}
                hayError={Boolean(error)}
                onCambiar={(cambio) => cambiar(indice, cambio)}
                onQuitar={() => setHijos((a) => a.filter((_, i) => i !== indice))}
                onElegirArchivo={(elegido) => elegirArchivo(indice, elegido)}
              />
            ))}

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
                onClick={() => setHijos((a) => [...a, hijoVacio(siguienteReferencia(a))])}
              >
                + Agregar otro hijo
              </button>
            )}
          </section>

          {modo !== "nuevo" && (
            <SeccionContacto
              propsSeccion={propsDePaso("contacto")}
              idBase={idBase}
              numeroPaso={pasoContacto}
              correoSesion={sesion?.correo}
            />
          )}

          <SeccionPreferencias
            propsSeccion={propsDePaso("preferencias")}
            idBase={idBase}
            numeroPaso={pasoPrioridad}
            prioridad={prioridad}
            onPrioridad={setPrioridad}
            marcasExcluidas={marcasExcluidas}
            soloDisponibles={soloDisponibles}
            onQuitarFiltros={() => {
              setMarcasExcluidas([]);
              setSoloDisponibles(false);
            }}
            presupuesto={presupuesto}
            onPresupuesto={setPresupuesto}
            conTope={conTope}
          />

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
