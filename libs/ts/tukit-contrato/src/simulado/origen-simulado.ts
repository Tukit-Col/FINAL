// El origen simulado: la misma interfaz que el cliente HTTP, alimentada por
// las semillas del repositorio.
//
// Respeta el ciclo asincrono del §0 en vez de devolver los kits de una: el
// trabajo pasa por `encolado`, `procesando` y `espera_revision`, y solo llega
// a `publicado` cuando alguien lo aprueba en `apps/admin`. Si el acudiente
// nunca viera la espera, la pantalla de espera no se podria probar y el dia
// que el backend real tarde tres minutos se descubriria que no existe.
//
// Los tiempos son segundos y no minutos para que se pueda mirar; se ajustan
// con `TUKIT_SIMULADO_SEGUNDOS`.

import { randomUUID } from "node:crypto";
import type {
  AltaProducto,
  ColaAdmin,
  DecisionRevision,
  Etapa,
  EstadoTrabajo,
  MarcarNoDisponible,
  NombreEtapa,
  ProductoDadoDeAlta,
  SinCoincidencia,
  SolicitudTrabajo,
  Trabajo,
  TrabajoAdmin,
  TrabajoCreado,
  ValidarLinea,
} from "../contrato";
import { ETAPAS } from "../contrato";
import type { Catalogo, Colegio, ListaOficial } from "../catalogo";
import { ErrorTukit, type ArchivoLista, type OrigenDatos } from "../origen";
import { CATALOGO, COLEGIOS, listaDe } from "./semillas";
import { armarKits, degradacionesDe, recomendar, resolverSolicitud } from "./armar";
import { actualizar, guardar, listar, obtener, type RegistroTrabajo } from "./almacen";

const SEGUNDOS = Number(process.env["TUKIT_SIMULADO_SEGUNDOS"] ?? 12);
// Reparto del tiempo entre etapas, proporcional a lo que cuesta cada una en el
// pipeline real (resolucion es la cara).
const PESO_ETAPA: Record<NombreEtapa, number> = {
  percepcion: 0.18,
  normalizacion: 0.07,
  resolucion: 0.5,
  optimizacion: 0.25,
};

// `false` deja el trabajo en `espera_revision` para siempre, que es el
// comportamiento fiel al contrato: publicar es una decision de una persona.
// Por defecto se auto-aprueba para que la usuaria pueda recorrer el flujo
// completo sin abrir `apps/admin` en otra ventana.
const AUTOAPROBAR = process.env["TUKIT_SIMULADO_AUTOAPROBAR"] !== "false";
const SEGUNDOS_AUTOAPROBACION = Number(process.env["TUKIT_SIMULADO_SEGUNDOS_REVISION"] ?? 8);

function transcurrido(registro: RegistroTrabajo): number {
  return (Date.now() - registro.base_ms) / 1000;
}

function estadoDe(registro: RegistroTrabajo): EstadoTrabajo {
  if (registro.aprobado) return "publicado";
  const t = transcurrido(registro);
  if (t < SEGUNDOS * 0.15) return "encolado";
  if (t < SEGUNDOS) return "procesando";
  if (AUTOAPROBAR && t >= SEGUNDOS + SEGUNDOS_AUTOAPROBACION) return "publicado";
  return "espera_revision";
}

function etapasDe(registro: RegistroTrabajo): Etapa[] {
  const t = transcurrido(registro);
  let acumulado = 0;
  return ETAPAS.map((nombre) => {
    const duracion = SEGUNDOS * PESO_ETAPA[nombre];
    const inicio = acumulado;
    acumulado += duracion;
    const estado: Etapa["estado"] = t >= acumulado ? "ok" : t > inicio ? "en_curso" : "pendiente";
    const ms = Math.round(
      (estado === "ok" ? duracion : Math.max(0, t - inicio)) * 1000,
    );
    return { nombre, estado, ms };
  });
}

function ajustesDe(registro: RegistroTrabajo) {
  return {
    validadas: registro.validadas,
    sinCoincidencia: registro.sin_coincidencia,
    skusNoDisponibles: registro.skus_no_disponibles,
  };
}

function construir(registro: RegistroTrabajo): Trabajo {
  const estado = estadoDe(registro);
  const resueltos = resolverSolicitud(registro.solicitud);
  const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));

  return {
    trabajo_id: registro.trabajo_id,
    estado,
    etapas: etapasDe(registro),
    // Mientras no este publicado, `kits` va vacio: el acudiente nunca ve un
    // kit sin revisar (§4).
    kits: estado === "publicado" ? kits : [],
    recomendado:
      estado === "publicado"
        ? recomendar(kits, registro.solicitud.preferencias, registro.solicitud.hijos.length)
        : null,
    degradaciones: estado === "publicado" ? degradacionesDe(kits) : [],
  };
}

export class OrigenSimulado implements OrigenDatos {
  readonly nombre = "simulado" as const;

  async crearTrabajo(
    solicitud: SolicitudTrabajo,
    archivos: ArchivoLista[] = [],
  ): Promise<TrabajoCreado> {
    if (!solicitud.contacto?.correo || !solicitud.contacto?.celular) {
      throw new ErrorTukit(
        400,
        "contacto_requerido",
        "Necesitamos tu correo y tu celular para avisarte cuando el kit esté listo.",
        { campo: "contacto" },
      );
    }
    if (solicitud.hijos.length === 0) {
      throw new ErrorTukit(400, "hijos_requeridos", "Agrega al menos un hijo.", {
        campo: "hijos",
      });
    }

    for (const archivo of archivos) {
      // §2.1: un archivo es la lista de UN grado. La senal buena es cuantos
      // grados distintos aparecen, y la reporta el modelo de percepcion, que
      // aqui no corre. El tamano es la misma "guarda barata previa" que el
      // contrato admite, y sirve para que la ruta de error no quede sin
      // probar: los PDF completos del corpus (39 y 22 paginas) caen aqui.
      if (archivo.tamano > 4 * 1024 * 1024) {
        throw new ErrorTukit(
          422,
          "lista_de_varios_grados",
          "Este archivo parece traer la lista de varios grados. Sube solo las páginas del grado de tu hijo.",
          { grados_detectados: [], paginas: 0 },
        );
      }
    }

    // Con archivo no hay percepcion que corra, asi que el origen simulado usa
    // la lista del colegio y el grado que el acudiente ya declaro. Es la
    // unica parte del simulado que no se puede derivar del archivo, y va
    // dicha en pantalla para que no se confunda con el comportamiento real.
    for (const hijo of solicitud.hijos) {
      if (!listaDe(hijo.colegio_id, hijo.grado)) {
        throw new ErrorTukit(
          422,
          "lista_no_encontrada",
          `No tenemos la lista de ${hijo.grado} para ese colegio en el corpus simulado.`,
          { campo: "hijos" },
        );
      }
    }

    const ahora = Date.now();
    const registro: RegistroTrabajo = {
      trabajo_id: randomUUID(),
      solicitud,
      base_ms: ahora,
      creado_ms: ahora,
      origen_entrada: archivos.length > 0 ? "archivo" : "lista_oficial",
      archivos: archivos.map((a) => a.nombre),
      aprobado: false,
      nota_revision: null,
      validadas: [],
      sin_coincidencia: {},
      skus_no_disponibles: [],
      productos_manuales: {},
    };
    guardar(registro);

    return {
      trabajo_id: registro.trabajo_id,
      estado: "encolado",
      estimado_segundos: Math.round(SEGUNDOS + SEGUNDOS_AUTOAPROBACION),
      consultar_en: `/v1/trabajos/${registro.trabajo_id}`,
    };
  }

  async consultarTrabajo(trabajoId: string): Promise<Trabajo> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    return construir(registro);
  }

  async catalogo(): Promise<Catalogo> {
    return CATALOGO;
  }

  async colegios(): Promise<Colegio[]> {
    return COLEGIOS;
  }

  async listaOficial(colegioId: string, grado: string): Promise<ListaOficial> {
    const lista = listaDe(colegioId, grado);
    if (!lista) {
      throw new ErrorTukit(404, "lista_no_existe", "No tenemos esa lista todavía.");
    }
    return lista;
  }

  async cola(): Promise<ColaAdmin> {
    const entradas = listar()
      .map((registro) => {
        const trabajo = construir(registro);
        const resueltos = resolverSolicitud(registro.solicitud);
        const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));
        const referencia = kits[0];
        const lineas = referencia?.lineas ?? [];
        return {
          trabajo_id: registro.trabajo_id,
          estado: trabajo.estado,
          recibido_en: new Date(registro.creado_ms).toISOString(),
          hijos: registro.solicitud.hijos.length,
          lineas_totales: lineas.length,
          lineas_pendientes: lineas.filter(
            (l) =>
              l.estado_resolucion === "AMBIGUO" ||
              l.estado_resolucion === "SIN_MATCH" ||
              l.estado_resolucion === "HUECO_CATALOGO",
          ).length,
          colegios: [...new Set(registro.solicitud.hijos.map((h) => h.colegio_id))],
          grados: [...new Set(registro.solicitud.hijos.map((h) => h.grado))],
        };
      })
      // Lo que ya se publico sale de la cola; lo demas se ordena por lo que
      // mas trabajo pide, que es lo que `AD-02` quiere priorizar.
      .sort((a, b) => b.lineas_pendientes - a.lineas_pendientes);
    return { entradas };
  }

  async trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    const base = construir(registro);
    const resueltos = resolverSolicitud(registro.solicitud);
    const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));
    const referencia = kits[0];

    return {
      ...base,
      // El admin SI ve los kits antes de publicar: esa es su tarea. El §4
      // vacia `kits` para el acudiente, no para la revision (§7, `AD-03`).
      kits,
      recomendado: recomendar(kits, registro.solicitud.preferencias, registro.solicitud.hijos.length),
      degradaciones: degradacionesDe(kits),
      recibido_en: new Date(registro.creado_ms).toISOString(),
      // Nunca el correo: la notificacion lo referencia por identificador.
      contacto_id: `id-${registro.trabajo_id.slice(0, 8)}`,
      lineas_pendientes: (referencia?.lineas ?? [])
        .filter(
          (l) =>
            l.estado_resolucion === "AMBIGUO" ||
            l.estado_resolucion === "SIN_MATCH" ||
            l.estado_resolucion === "HUECO_CATALOGO",
        )
        .map((l) => l.item_id),
      nota_revision: registro.nota_revision,
    };
  }

  async validarLinea(trabajoId: string, itemId: string, _cuerpo: ValidarLinea): Promise<void> {
    const registro = actualizar(trabajoId, (r) => {
      if (!r.validadas.includes(itemId)) r.validadas.push(itemId);
      delete r.sin_coincidencia[itemId];
    });
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
  }

  async marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void> {
    if (!cuerpo.motivo?.trim()) {
      throw new ErrorTukit(
        400,
        "motivo_requerido",
        "Escribe por qué no hay coincidencia: una marca sin motivo no se puede revisar después.",
        { campo: "motivo" },
      );
    }
    const registro = actualizar(trabajoId, (r) => {
      r.sin_coincidencia[itemId] = cuerpo.motivo;
      r.validadas = r.validadas.filter((id) => id !== itemId);
    });
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
  }

  async altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
    if (!Number.isInteger(cuerpo.precio) || cuerpo.precio <= 0) {
      throw new ErrorTukit(
        400,
        "precio_invalido",
        "El precio va en pesos enteros y tiene que ser positivo.",
        { campo: "precio" },
      );
    }
    const sku = `TK-MAN-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
    if (cuerpo.trabajo_id && cuerpo.item_id) {
      const itemId = cuerpo.item_id;
      actualizar(cuerpo.trabajo_id, (r) => {
        r.productos_manuales[itemId] = {
          sku,
          nombre: cuerpo.nombre,
          precio: cuerpo.precio,
        };
        if (!r.validadas.includes(itemId)) r.validadas.push(itemId);
        delete r.sin_coincidencia[itemId];
      });
    }
    return { sku };
  }

  async marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
    if (!cuerpo.motivo?.trim()) {
      throw new ErrorTukit(400, "motivo_requerido", "Di por qué no está disponible.", {
        campo: "motivo",
      });
    }
    // El `AD-05` real apaga la oferta en catalogo, o sea para todos los
    // trabajos. Aqui se propaga a todos los que estan en la cola, que es el
    // efecto observable.
    for (const registro of listar()) {
      actualizar(registro.trabajo_id, (r) => {
        if (!r.skus_no_disponibles.includes(sku)) r.skus_no_disponibles.push(sku);
      });
    }
  }

  async decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    if (registro.aprobado) {
      throw new ErrorTukit(
        409,
        "trabajo_ya_publicado",
        "Este trabajo ya se publicó: no se puede volver a revisar.",
      );
    }
    actualizar(trabajoId, (r) => {
      r.nota_revision = cuerpo.nota ?? null;
      if (cuerpo.decision === "aprobar") {
        r.aprobado = true;
      } else {
        // Devolver reabre el trabajo sin avisar al acudiente: el reloj vuelve
        // a empezar y el estado baja a `procesando`.
        r.base_ms = Date.now();
      }
    });
  }
}
