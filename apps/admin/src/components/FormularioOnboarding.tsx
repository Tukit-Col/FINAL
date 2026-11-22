"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud } from "lucide-react";
import {
  validarArchivo,
  EXTENSIONES_ACEPTADAS,
  type Colegio,
  type ColegioDesignado,
} from "@tukit/contrato";
import BuscadorColegioOnboarding from "@/components/BuscadorColegioOnboarding";
import { subirOnboarding, FalloApi } from "@/lib/api-onboarding";
import styles from "@/app/onboarding/Onboarding.module.css";

function anioPorDefecto(): number {
  return new Date().getFullYear() + 1;
}

interface Props {
  colegios: Colegio[];
}

export default function FormularioOnboarding({ colegios }: Props) {
  const router = useRouter();
  const idBase = useId();

  const [colegio, setColegio] = useState<ColegioDesignado | null>(null);
  const [grado, setGrado] = useState("");
  const [anio, setAnio] = useState(String(anioPorDefecto()));
  const [archivo, setArchivo] = useState<File | null>(null);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gradosDetectados, setGradosDetectados] = useState<string[]>([]);

  function elegirArchivo(elegido: File | undefined) {
    if (!elegido) return;
    const problema = validarArchivo(elegido);
    setArchivo(problema ? null : elegido);
    setErrorArchivo(problema);
  }

  const anioNum = Number(anio);
  const anioOk = Number.isInteger(anioNum) && anioNum >= 2000 && anioNum <= 2100;
  const listo = colegio !== null && grado.trim() !== "" && archivo !== null && anioOk;

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    if (!listo || enviando || !archivo || !colegio) return;
    setEnviando(true);
    setError(null);
    setGradosDetectados([]);

    try {
      const version = await subirOnboarding({
        colegio,
        grado: grado.trim(),
        anioLectivo: anioNum,
        archivo,
      });
      router.push(`/onboarding/${encodeURIComponent(version.version_id)}`);
    } catch (causa) {
      if (causa instanceof FalloApi) {
        setError(causa.message);
        const detectados = causa.detalle["grados_detectados"];
        if (Array.isArray(detectados)) setGradosDetectados(detectados.map(String));
      } else {
        setError("No pudimos subir la lista. Intenta de nuevo.");
      }
      setEnviando(false);
    }
  }

  return (
    <form className={styles.formulario} onSubmit={enviar}>
      <BuscadorColegioOnboarding colegios={colegios} onElegir={setColegio} />

      <div className={styles.dosColumnas}>
        <label className={styles.campo}>
          <span>Grado</span>
          <input
            value={grado}
            onChange={(e) => setGrado(e.target.value)}
            placeholder="Ej. 3º primaria"
            required
          />
        </label>

        <label className={styles.campo}>
          <span>Año lectivo</span>
          <input
            value={anio}
            onChange={(e) => setAnio(e.target.value)}
            inputMode="numeric"
            placeholder="2026"
            required
          />
          {!anioOk && anio.trim() !== "" ? (
            <span className={styles.pistaError}>Cuatro cifras, entre 2000 y 2100.</span>
          ) : null}
        </label>
      </div>

      <div className={styles.zonaArchivo}>
        <p className={styles.reglaArchivo}>
          Sube solo las páginas del grado, no el PDF completo del colegio con los trece grados.
          Un revisor que empieza con la lista de otro grado revisa lo que no es.
        </p>
        <input
          id={`${idBase}-archivo`}
          type="file"
          className={styles.inputArchivo}
          accept={EXTENSIONES_ACEPTADAS.join(",")}
          onChange={(e) => {
            elegirArchivo(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <label htmlFor={`${idBase}-archivo`} className={styles.soltar}>
          <UploadCloud size={20} aria-hidden="true" />
          <strong>Haz clic para elegir el PDF</strong>
          <span>PDF, JPG, PNG o WEBP · hasta 10 MB</span>
        </label>

        {archivo ? <p className={styles.archivoElegido}>{archivo.name}</p> : null}
        {errorArchivo ? (
          <p className={styles.pistaError} role="alert">
            {errorArchivo}
          </p>
        ) : null}
      </div>

      {error ? (
        <div className={styles.errorCaja} role="alert">
          <strong>{error}</strong>
          {gradosDetectados.length > 0 ? (
            <p>Detectamos estos grados en el archivo: {gradosDetectados.join(", ")}.</p>
          ) : null}
        </div>
      ) : null}

      <div className={styles.barraAccion}>
        <button type="submit" className={styles.principal} disabled={!listo || enviando}>
          {enviando ? "Percibiendo la lista…" : "Subir y percibir"}
        </button>
        {!listo ? (
          <p className={styles.faltante}>Falta el colegio, el grado o el archivo.</p>
        ) : null}
      </div>
    </form>
  );
}
