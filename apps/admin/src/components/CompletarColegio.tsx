"use client";

// Región del revisor (P4/E4): completar el perfil del colegio NUEVO antes de
// aprobar. Solo aparece cuando la versión trae `colegio_datos` — es decir, la
// subió un acudiente para un colegio que aún no existe en Tukit (lo eligió del
// directorio de Bogotá o lo escribió a mano). Para un colegio ya aliado no hay
// nada que crear y esta región no se pinta.
//
// El `nombre` y el `dane` los fijó la subida y el `dane` no se edita (deriva el
// `colegio_id`; cambiarlo desligaría la lista del colegio), así que se muestran
// como contexto de solo lectura. El resto —logo, sitio, dirección, contacto de
// la institución— son datos de la INSTITUCIÓN, no del menor: no son PII, y se
// completan aquí para que la aprobación cree la identidad completa. El poller de
// Identidad hace el upsert al cerrar la versión sin pisar lo que ya se editó.
//
// Guarda con `completarColegioDeVersion` (merge en el backend); tras guardar,
// `router.refresh` re-lee la revisión con los datos ya combinados. Deshabilitado
// cuando la versión ya está revisada: no se edita un colegio de una lista cerrada.

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { DatosColegioNuevo } from "@tukit/contrato";
import { completarColegioDeVersion, FalloListas } from "@/lib/api-listas";
import styles from "@/app/onboarding/Onboarding.module.css";

interface Props {
  versionId: string;
  datos: DatosColegioNuevo;
  revisada: boolean;
}

// Los campos editables, en el orden en que se muestran. `dane` y `nombre` van
// aparte: el DANE es de solo lectura y el nombre se edita como los demás pero se
// separa arriba porque es el que la subida ya trajo.
const CAMPOS: { clave: keyof DatosColegioNuevo; etiqueta: string; tipo: string }[] = [
  { clave: "logo_url", etiqueta: "Logo (URL)", tipo: "url" },
  { clave: "sitio_web", etiqueta: "Sitio web", tipo: "url" },
  { clave: "direccion", etiqueta: "Dirección", tipo: "text" },
  { clave: "contacto_nombre", etiqueta: "Contacto (secretaría)", tipo: "text" },
  { clave: "contacto_email", etiqueta: "Correo de la institución", tipo: "email" },
  { clave: "contacto_telefono", etiqueta: "Teléfono de la institución", tipo: "tel" },
];

export default function CompletarColegio({ versionId, datos, revisada }: Props) {
  const router = useRouter();
  const [valores, setValores] = useState<Record<string, string>>(() => ({
    nombre: datos.nombre ?? "",
    logo_url: datos.logo_url ?? "",
    sitio_web: datos.sitio_web ?? "",
    direccion: datos.direccion ?? "",
    contacto_nombre: datos.contacto_nombre ?? "",
    contacto_email: datos.contacto_email ?? "",
    contacto_telefono: datos.contacto_telefono ?? "",
  }));
  const [guardando, setGuardando] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function fijar(clave: string, valor: string) {
    setValores((previo) => ({ ...previo, [clave]: valor }));
    setGuardado(false);
  }

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      // Se manda solo lo que tiene texto: el backend hace merge y no queremos
      // pisar un dato con una cadena vacía. El `dane` nunca viaja (no editable).
      const cambios: Record<string, string> = {};
      cambios.nombre = valores.nombre?.trim() ?? "";
      for (const { clave } of CAMPOS) {
        const v = valores[clave]?.trim() ?? "";
        if (v) cambios[clave] = v;
      }
      await completarColegioDeVersion(versionId, cambios);
      setGuardado(true);
      router.refresh();
    } catch (causa) {
      setError(
        causa instanceof FalloListas ? causa.message : "No se pudieron guardar los datos del colegio.",
      );
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className={styles.formulario}>
      <p className={styles.bajada}>
        Este colegio todavía no existe en Tukit: nacerá al aprobar la lista. Complétalo para que
        quede con logo, sitio y contacto, y sirva de caché a otros acudientes del mismo colegio y
        grado. Estos son datos de la institución, nunca del estudiante.
      </p>

      <div className={styles.campo}>
        <span>Nombre del colegio</span>
        <input
          type="text"
          value={valores.nombre}
          onChange={(e) => fijar("nombre", e.target.value)}
          disabled={revisada || guardando}
          placeholder="Nombre de la institución"
        />
      </div>

      {datos.dane ? (
        <div className={styles.campo}>
          <span>DANE (deriva el identificador; no editable)</span>
          <input type="text" value={datos.dane} readOnly disabled />
        </div>
      ) : null}

      <div className={styles.dosColumnas}>
        {CAMPOS.map(({ clave, etiqueta, tipo }) => (
          <label key={clave} className={styles.campo}>
            <span>{etiqueta}</span>
            <input
              type={tipo}
              value={valores[clave] ?? ""}
              onChange={(e) => fijar(clave, e.target.value)}
              disabled={revisada || guardando}
            />
          </label>
        ))}
      </div>

      {revisada ? (
        <p className={styles.faltante}>
          La versión ya está publicada; el colegio ya se dio de alta con estos datos.
        </p>
      ) : (
        <div className={styles.barraAccion}>
          <button
            type="button"
            className={styles.secundario}
            onClick={guardar}
            disabled={guardando}
          >
            {guardando ? "Guardando…" : "Guardar datos del colegio"}
          </button>
          {guardado ? <span className={styles.faltante}>Guardado.</span> : null}
        </div>
      )}
      {error ? <p className={styles.errorCaja}>{error}</p> : null}
    </div>
  );
}
