"use client";

// P4/P1b — la ficha editable de un colegio. Solo se edita lo que Tukit administra:
// el código DANE (llave del directorio DUEB) y la URL del logo (lo único que el
// padre ve en el selector de /empezar). El resto de los datos (sitio, contactos,
// dirección) sale del directorio oficial y se muestra —solo lectura— en la página
// que envuelve a este formulario, así que aquí no se duplica ni se edita. Manda un
// PATCH con solo lo que cambió y re-pinta con el detalle que el backend devuelve.
//
// Sin URL propia, el logo que se ve sale del directorio de Bogotá por el DANE
// (`logoDelDirectorio`). El campo lo dice con una nota y lo muestra de
// placeholder, pero sigue vacío: el logo del directorio no se guarda en la base.

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import type { ColegioDetalle, ColegioEditable } from "@tukit/contrato";
import { editarColegio, FalloListas } from "@/lib/api-listas";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  colegio: ColegioDetalle;
  // El logo del directorio que se ve hoy, o `null` si el colegio tiene uno
  // propio o el directorio no trae logo para su DANE.
  logoDelDirectorio: string | null;
}

// Un campo del formulario: mapea a una clave de `ColegioEditable`.
const CAMPOS: {
  clave: keyof ColegioEditable;
  etiqueta: string;
  tipo: string;
  maxLength?: number;
  inputMode?: "numeric";
  pattern?: string;
}[] = [
  // El código DANE (llave del directorio DUEB); editable porque el `colegio_id`
  // es un UUID que ya existe, no se re-deriva del DANE al guardar. Son 12
  // dígitos (mismo largo que la columna), de ahí el `maxLength`/teclado numérico y
  // el `pattern`. Vacío sigue siendo válido (no es `required`): así se puede
  // limpiar el DANE, y el backend lo valida igual (12 dígitos o null).
  {
    clave: "dane",
    etiqueta: "Código DANE",
    tipo: "text",
    maxLength: 12,
    inputMode: "numeric",
    pattern: "\\d{12}",
  },
  { clave: "logo_url", etiqueta: "URL del logo", tipo: "url" },
];

function valorInicial(colegio: ColegioDetalle): Record<keyof ColegioEditable, string> {
  return {
    dane: colegio.dane ?? "",
    logo_url: colegio.logo_url ?? "",
    sitio_web: colegio.sitio_web ?? "",
    contacto_nombre: colegio.contacto_nombre ?? "",
    contacto_email: colegio.contacto_email ?? "",
    contacto_telefono: colegio.contacto_telefono ?? "",
  };
}

export default function PerfilColegio({ colegio, logoDelDirectorio }: Props) {
  const idBase = useId();
  const router = useRouter();
  const [actual, setActual] = useState<ColegioDetalle>(colegio);
  const [valores, setValores] = useState(valorInicial(colegio));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [sinCambios, setSinCambios] = useState(false);

  function cambiar(clave: keyof ColegioEditable, valor: string) {
    setValores((v) => ({ ...v, [clave]: valor }));
    setOk(false);
    setSinCambios(false);
  }

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    setGuardando(true);
    setError(null);
    setOk(false);
    setSinCambios(false);

    // Solo se manda lo que cambió. Un campo vaciado se manda `null` (limpia el
    // campo); uno sin tocar no se manda.
    const base = valorInicial(actual);
    const cambios: ColegioEditable = {};
    for (const { clave } of CAMPOS) {
      if (valores[clave] !== base[clave]) {
        cambios[clave] = valores[clave].trim() === "" ? null : valores[clave].trim();
      }
    }

    if (Object.keys(cambios).length === 0) {
      // Nada que guardar: no se llama al backend ni se dice "guardado" (sería
      // engañoso); se avisa que no hubo cambios.
      setGuardando(false);
      setSinCambios(true);
      return;
    }

    try {
      const actualizado = await editarColegio(actual.colegio_id, cambios);
      setActual(actualizado);
      setValores(valorInicial(actualizado));
      setOk(true);
      // Re-consulta el server component: si se acaba de guardar el DANE, la
      // ficha del directorio DUEB (que se lee en el servidor) aparece sin
      // recargar a mano.
      router.refresh();
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo guardar el perfil.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form className={styles.formularioPerfil} onSubmit={guardar}>
      {CAMPOS.map(({ clave, etiqueta, tipo, maxLength, inputMode, pattern }) => {
        const id = `${idBase}-${clave}`;
        const delDirectorio =
          clave === "logo_url" && !valores.logo_url.trim() ? logoDelDirectorio : null;
        return (
          <div key={clave} className={styles.campo}>
            <label htmlFor={id}>{etiqueta}</label>
            <input
              id={id}
              type={tipo}
              value={valores[clave]}
              onChange={(e) => cambiar(clave, e.target.value)}
              disabled={guardando}
              maxLength={maxLength}
              inputMode={inputMode}
              pattern={pattern}
              placeholder={delDirectorio ?? undefined}
              aria-describedby={delDirectorio ? `${id}-nota` : undefined}
            />
            {delDirectorio ? (
              <span id={`${id}-nota`} className={styles.fuente}>
                Hoy se ve el logo del directorio de Bogotá, por el DANE. Escribe una URL para
                reemplazarlo.
              </span>
            ) : null}
          </div>
        );
      })}

      {error ? <p className={styles.pistaError}>{error}</p> : null}
      {ok ? <p className={styles.perfilOk}>Datos guardados.</p> : null}
      {sinCambios ? <p className={styles.fuente}>No hay cambios para guardar.</p> : null}

      <div className={styles.accionesGrado}>
        <button type="submit" className={styles.botonPrincipal} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </form>
  );
}
