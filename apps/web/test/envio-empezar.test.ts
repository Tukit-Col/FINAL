import { test } from "node:test";
import assert from "node:assert/strict";
import { hijoVacio, type HijoFormulario } from "../src/lib/formulario-empezar.ts";
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
} from "../src/lib/envio-empezar.ts";

const COLEGIOS = new Map([["san-pedro", { grados: ["Primero"] }]]);
const ARCHIVO = { name: "lista.pdf" } as File;

function hijo(cambio: Partial<HijoFormulario> = {}): HijoFormulario {
  return { ...hijoVacio(1), colegioId: "san-pedro", grado: "Primero", ...cambio };
}

test("los personajes se separan por comas y los hijos sin personaje no aparecen", () => {
  const hijos = [hijo({ personajes: " Spider-Man, Frozen ,," }), hijo({ referencia: "hijo-2" })];
  assert.deepEqual(personajesPorHijo(hijos), { "hijo-1": ["Spider-Man", "Frozen"] });
});

test("las preferencias llevan los pesos de la prioridad y solo lo que el acudiente pidió", () => {
  const base = {
    prioridad: "equilibrio" as const,
    presupuesto: "",
    conTope: false,
    personajePorHijo: {},
    marcasExcluidas: [],
    soloDisponibles: false,
  };
  assert.deepEqual(construirPreferencias(base), {
    pesos: { precio: 0.35, marca_exigida: 0.3, calidad: 0.25, personaje: 0.1 },
    disposicion_sobreprecio: 0.05,
    prioridad: "equilibrio",
  });
  const completa = construirPreferencias({
    ...base,
    presupuesto: "350000",
    conTope: true,
    personajePorHijo: { "hijo-1": ["Frozen"] },
    marcasExcluidas: ["Norma"],
    soloDisponibles: true,
  });
  assert.equal(completa.presupuesto_por_hijo, 350000);
  assert.deepEqual(completa.personaje_por_hijo, { "hijo-1": ["Frozen"] });
  assert.deepEqual(completa.marcas_excluidas, ["Norma"]);
  assert.equal(completa.solo_disponibles, true);
});

test("el registro manda solo los hijos de colegios de Tukit y el apodo sin recortar", () => {
  const hijos = [
    hijo({ apodo: "  Nico  " }),
    hijo({ referencia: "hijo-2", colegioId: "", colegioNombre: "Otro", grado: "Tercero" }),
  ];
  const registro = construirRegistro(
    { correo: "a@b.co", clave: "clave1234", aceptaTerminos: true, celular: "300" },
    hijos,
  );
  assert.deepEqual(registro, {
    correo: "a@b.co",
    clave: "clave1234",
    acepta_terminos: true,
    celular: "300",
    hijos: [{ colegio_id: "san-pedro", grado: "Primero", apodo: "Nico" }],
  });
});

test("las matrículas nuevas excluyen a los hijos precargados y a los de colegio escrito", () => {
  const hijos = [
    hijo({ precargado: true }),
    hijo({ referencia: "hijo-2" }),
    hijo({ referencia: "hijo-3", colegioId: "", colegioNombre: "Otro" }),
  ];
  assert.deepEqual(matriculasNuevas(hijos), [{ colegio_id: "san-pedro", grado: "Primero" }]);
});

test("se separan los hijos con lista verificada de los que suben archivo", () => {
  const verificado = hijo();
  const sinLista = hijo({ referencia: "hijo-2", grado: "Quinto", archivo: ARCHIVO });
  const sinArchivo = hijo({ referencia: "hijo-3", grado: "Quinto" });
  const hijos = [verificado, sinLista, sinArchivo];
  assert.deepEqual(hijosConListaVerificada(hijos, COLEGIOS), [verificado]);
  assert.deepEqual(hijosParaSubir(hijos, COLEGIOS), [sinLista]);
});

test("el canónico solo aplica con un único hijo de colegio y grado verificados", () => {
  const canonicos = [{ colegio_id: "san-pedro", grado: "Primero", anio_lectivo: 2026 }] as never;
  const unico = hijo();
  assert.equal(canonicoDelUnicoHijo([unico], canonicos, COLEGIOS)?.canonico.anio_lectivo, 2026);
  assert.equal(canonicoDelUnicoHijo([unico, hijo({ referencia: "hijo-2" })], canonicos, COLEGIOS), null);
  assert.equal(canonicoDelUnicoHijo([hijo({ grado: "Quinto" })], canonicos, COLEGIOS), null);
  assert.equal(canonicoDelUnicoHijo([hijo({ colegioId: "" })], canonicos, COLEGIOS), null);
});

test("el cuerpo del canónico recorta el apodo a 40 caracteres y agrega el personaje si hay", () => {
  const canonico = { colegio_id: "san-pedro", grado: "Primero", anio_lectivo: 2026 } as never;
  const largo = "x".repeat(50);
  assert.deepEqual(cuerpoCanonico(hijo({ apodo: largo }), canonico, "Fan", "Frozen"), {
    colegio_id: "san-pedro",
    grado: "Primero",
    anio_lectivo: 2026,
    perfil: "Fan",
    personaje: "Frozen",
    apodo: "x".repeat(40),
  });
  assert.equal("personaje" in cuerpoCanonico(hijo(), canonico, "Premium", undefined), false);
});

test("la solicitud de trabajo lleva una fila por hijo y las preferencias", () => {
  const preferencias = { prioridad: "precio" } as never;
  assert.deepEqual(construirSolicitud([hijo({ apodo: "Nico" })], preferencias), {
    hijos: [{ referencia: "hijo-1", colegio_id: "san-pedro", grado: "Primero", apodo: "Nico" }],
    preferencias,
  });
});

test("el destino de una subida usa el colegio de Tukit, el DANE o solo el nombre", () => {
  assert.deepEqual(destinoDeSubida(hijo({ colegioDane: "x" })), {
    referencia: "hijo-1",
    colegio_id: "san-pedro",
    grado: "Primero",
  });
  assert.deepEqual(
    destinoDeSubida(hijo({ colegioId: "", colegioDane: "123", colegioNombre: "Nuevo", grado: "Tercero" })),
    { referencia: "hijo-1", colegio_dane: "123", colegio_nombre: "Nuevo", grado: "Tercero" },
  );
  assert.deepEqual(destinoDeSubida(hijo({ colegioId: "", colegioNombre: "A mano", grado: "Tercero" })), {
    referencia: "hijo-1",
    colegio_nombre: "A mano",
    grado: "Tercero",
  });
});

test("los archivos de la subida van con la referencia de su hijo", () => {
  assert.deepEqual(archivosDeSubida([hijo({ archivo: ARCHIVO })]), [
    { referencia: "hijo-1", archivo: ARCHIVO },
  ]);
});
