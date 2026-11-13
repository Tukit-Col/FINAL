// Las reglas puras del campo de dirección del checkout: los turnos que deciden
// qué respuesta de Google todavía vale, qué error de Google apaga el
// autocompletado y qué se borra al editar a mano una dirección de Google.
//
// Runner nativo de Node sobre TypeScript. Correr: `node --test test/direccion-checkout.test.ts`.

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  crearTurnos,
  escribirDireccionAMano,
  esRechazoDePermisos,
  type Reloj,
} from "../src/lib/direccion-checkout.ts";

// Un reloj a mano: `avanzar` dispara lo que venció.
function relojFalso() {
  let ahora = 0;
  let siguiente = 0;
  const pendientes = new Map<number, { vence: number; fn: () => void }>();
  const reloj: Reloj = {
    programar(fn, ms) {
      const id = ++siguiente;
      pendientes.set(id, { vence: ahora + ms, fn });
      return id;
    },
    cancelar(id) {
      pendientes.delete(id as number);
    },
  };
  function avanzar(ms: number) {
    ahora += ms;
    for (const [id, { vence, fn }] of [...pendientes]) {
      if (vence <= ahora) {
        pendientes.delete(id);
        fn();
      }
    }
  }
  return { reloj, avanzar, pendientes };
}

test("la búsqueda sale tras la espera y su respuesta vale si no se tecleó más", () => {
  const { reloj, avanzar } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  const buscados: number[] = [];
  turnos.teclear((turno) => buscados.push(turno));
  avanzar(249);
  assert.deepEqual(buscados, []);
  avanzar(1);
  assert.equal(buscados.length, 1);
  assert.equal(turnos.vigente(buscados[0]), true);
});

test("teclear de nuevo cancela la búsqueda pendiente y vence la que está en vuelo", () => {
  const { reloj, avanzar } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  const buscados: number[] = [];
  turnos.teclear((turno) => buscados.push(turno));
  avanzar(250);
  turnos.teclear((turno) => buscados.push(turno));
  turnos.teclear((turno) => buscados.push(turno));
  avanzar(250);
  assert.equal(buscados.length, 2);
  assert.equal(turnos.vigente(buscados[0]), false);
  assert.equal(turnos.vigente(buscados[1]), true);
});

test("elegir antes de que venza la espera cancela la búsqueda y la selección vale", () => {
  // Antes, la búsqueda vencía después de elegir: abría una sesión de más y
  // descartaba los detalles del lugar elegido.
  const { reloj, avanzar, pendientes } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  let buscadas = 0;
  turnos.teclear(() => buscadas++);
  const eleccion = turnos.elegir();
  assert.equal(pendientes.size, 0);
  avanzar(1000);
  assert.equal(buscadas, 0);
  assert.equal(turnos.vigente(eleccion), true);
});

test("teclear mientras llegan los detalles de lo elegido gana lo escrito", () => {
  const { reloj } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  const eleccion = turnos.elegir();
  turnos.teclear(() => {});
  assert.equal(turnos.vigente(eleccion), false);
});

test("una tecla sin búsqueda (pocas letras o sin Google) también vence lo que está en vuelo", () => {
  const { reloj, pendientes } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  const eleccion = turnos.elegir();
  turnos.teclear();
  assert.equal(pendientes.size, 0);
  assert.equal(turnos.vigente(eleccion), false);
});

test("cerrar cancela la búsqueda pendiente", () => {
  const { reloj, avanzar } = relojFalso();
  const turnos = crearTurnos(250, reloj);
  let buscadas = 0;
  turnos.teclear(() => buscadas++);
  turnos.cerrar();
  avanzar(1000);
  assert.equal(buscadas, 0);
});

test("solo los errores de permisos de Google apagan el autocompletado", () => {
  assert.equal(esRechazoDePermisos({ code: "PERMISSION_DENIED" }), true);
  assert.equal(esRechazoDePermisos({ code: "REQUEST_DENIED" }), true);
  assert.equal(esRechazoDePermisos({ code: "UNAUTHENTICATED" }), true);
  assert.equal(esRechazoDePermisos(Object.assign(new Error("x"), { code: "PERMISSION_DENIED" })), true);
  // Pasajeros: se reintenta en la siguiente tecla.
  assert.equal(esRechazoDePermisos({ code: "UNAVAILABLE" }), false);
  assert.equal(esRechazoDePermisos({ code: "UNKNOWN_ERROR" }), false);
  assert.equal(esRechazoDePermisos(new TypeError("Failed to fetch")), false);
  assert.equal(esRechazoDePermisos(null), false);
  assert.equal(esRechazoDePermisos("PERMISSION_DENIED"), false);
});

const DE_GOOGLE = {
  direccion: "Cl. 26 #69-76, Bogotá, Colombia",
  google_place_id: "ChIJ-lugar",
  localidad: "Fontibón",
  ciudad: "Bogotá",
};

test("editar a mano una dirección de Google suelta el lugar y la localidad", () => {
  assert.deepEqual(escribirDireccionAMano(DE_GOOGLE, "Cl. 26 #69-7"), {
    direccion: "Cl. 26 #69-7",
    google_place_id: "",
    localidad: "",
    ciudad: "Bogotá",
  });
});

test("editar una dirección escrita a mano conserva la localidad elegida", () => {
  const manual = { ...DE_GOOGLE, google_place_id: "" };
  assert.deepEqual(escribirDireccionAMano(manual, "Calle 26 # 69-76"), {
    ...manual,
    direccion: "Calle 26 # 69-76",
  });
});

test("editar a mano una dirección con pin de OpenStreetMap suelta el pin y la localidad", () => {
  const conPin = {
    direccion: "Calle 72 # 10-34",
    google_place_id: "",
    localidad: "Chapinero",
    latitud: 4.65,
    longitud: -74.05,
  };
  assert.deepEqual(escribirDireccionAMano(conPin, "Calle 73 # 10-34"), {
    direccion: "Calle 73 # 10-34",
    google_place_id: "",
    localidad: "",
    latitud: null,
    longitud: null,
  });
});

test("sin pin ni lugar elegido, escribir solo cambia el texto", () => {
  const manual = { direccion: "Cl", google_place_id: "", localidad: "Suba", latitud: null, longitud: null };
  assert.deepEqual(escribirDireccionAMano(manual, "Cll 1"), { ...manual, direccion: "Cll 1" });
});
