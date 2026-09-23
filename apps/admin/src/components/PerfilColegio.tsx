"use client";

// P4/P1b — la ficha editable de un colegio. Un formulario sobre los campos que
// `editarColegio` acepta (logo, sitio web, contactos de la secretaría académica),
// que manda un PATCH con solo lo que cambió y re-pinta con el detalle que el
// backend devuelve. Los contactos son del colegio, NUNCA de un menor (§12.4).

import { useState } from "react";
import type { ColegioDetalle, ColegioEditable } from "@tukit/contrato";
import { editarColegio, FalloListas } from "@/lib/api-listas";
import styles from "@/app/colegios/Colegios.module.css";

interface Props {
  colegio: ColegioDetalle;
}

// Un campo del formulario: mapea a una clave de `ColegioEditable`.
const CAMPOS: { clave: keyof ColegioEditable; etiqueta: string; tipo: string }[] = [
  { clave: "logo_url", etiqueta: "URL del logo", tipo: "url" },
  { clave: "sitio_web", etiqueta: "Sitio web", tipo: "url" },
  { clave: "contacto_nombre", etiqueta: "Contacto (secretaría académica)", tipo: "text" },
  { clave: "contacto_email", etiqueta: "Correo de contacto del colegio", tipo: "email" },
  { clave: "contacto_telefono", etiqueta: "Teléfono de contacto del colegio", tipo: "tel" },
];

function valorInicial(colegio: ColegioDetalle): Record<keyof ColegioEditable, string> {
  return {
    logo_url: colegio.logo_url ?? "",
    sitio_web: colegio.sitio_web ?? "",
    contacto_nombre: colegio.contacto_nombre ?? "",
    contacto_email: colegio.contacto_email ?? "",
    contacto_telefono: colegio.contacto_telefono ?? "",
  };
}

export default function PerfilColegio({ colegio }: Props) {
  const [actual, setActual] = useState<ColegioDetalle>(colegio);
  const [valores, setValores] = useState(valorInicial(colegio));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  function cambiar(clave: keyof ColegioEditable, valor: string) {
    setValores((v) => ({ ...v, [clave]: valor }));
    setOk(false);
  }

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault();
    setGuardando(true);
    setError(null);
    setOk(false);

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
      setGuardando(false);
      setOk(true);
      return;
    }

    try {
      const actualizado = await editarColegio(actual.colegio_id, cambios);
      setActual(actualizado);
      setValores(valorInicial(actualizado));
      setOk(true);
    } catch (causa) {
      setError(causa instanceof FalloListas ? causa.message : "No se pudo guardar el perfil.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form className={styles.formularioPerfil} onSubmit={guardar}>
      {CAMPOS.map(({ clave, etiqueta, tipo }) => (
        <label key={clave} className={styles.campo}>
          <span>{etiqueta}</span>
          <input
            type={tipo}
            value={valores[clave]}
            onChange={(e) => cambiar(clave, e.target.value)}
            disabled={guardando}
          />
        </label>
      ))}

      {actual.direccion ? (
        <p className={styles.fuente}>Dirección (no editable aquí): {actual.direccion}</p>
      ) : null}

      {error ? <p className={styles.pistaError}>{error}</p> : null}
      {ok ? <p className={styles.perfilOk}>Perfil guardado.</p> : null}

      <div className={styles.accionesGrado}>
        <button type="submit" className={styles.botonPrincipal} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar perfil"}
        </button>
      </div>
    </form>
  );
}
