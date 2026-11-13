"use client";

import { useId, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogIn } from "lucide-react";
import styles from "./Ingresar.module.css";

export default function FormularioIngreso({
  destino,
}: {
  // A donde volver tras entrar (p. ej. `/empezar` en el camino "ya tengo
  // cuenta"). Si no viene, manda el destino por rol que decide el backend.
  destino?: string;
}) {
  const router = useRouter();
  const idCorreo = useId();
  const idClave = useId();
  const [correo, setCorreo] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const respuesta = await fetch("/api/sesion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ correo, clave, destino }),
      });
      const cuerpo = (await respuesta.json()) as { url?: string; mensaje?: string };
      if (!respuesta.ok) {
        setError(cuerpo.mensaje ?? "No pudimos ingresarte.");
        return;
      }
      const url = cuerpo.url ?? "/dashboard";
      // Salto entre apps (a otro origen, p. ej. la app interna) vs navegacion
      // interna: lo primero necesita el navegador; lo segundo, el router.
      if (/^https?:\/\//.test(url)) {
        window.location.assign(url);
      } else {
        // Navegación interna: `router.refresh()` tras `replace` obliga a la Cabecera
        // (Server Component que lee la sesión) a repintarse ya, sin F5, igual que
        // hace SalirBoton al cerrar sesión. La cookie de sesión ya está puesta.
        router.replace(url);
        router.refresh();
      }
    } catch {
      setError("No pudimos conectar. Intenta de nuevo.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className={styles.pagina}>
      <section className={styles.tarjeta} aria-labelledby="titulo-ingreso">
        <Image
          src="/marca/tukit-logo.webp"
          alt="Tukit"
          width={200}
          height={290}
          priority
          className={styles.logo}
        />
        <h1 id="titulo-ingreso" className={styles.titulo}>
          Ingresa a Tukit
        </h1>
        <p className={styles.subtitulo}>Para quien ya se registró: entra para ver tus kits, tus pedidos y a tus hijos.</p>

        <form className={styles.forma} onSubmit={enviar}>
          <label className={styles.campo} htmlFor={idCorreo}>
            <span>Correo</span>
            <input
              id={idCorreo}
              type="email"
              autoComplete="email"
              required
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              placeholder="tucorreo@ejemplo.com"
            />
          </label>

          <label className={styles.campo} htmlFor={idClave}>
            <span>Clave</span>
            <input
              id={idClave}
              type="password"
              autoComplete="current-password"
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              placeholder="tu clave"
            />
          </label>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}

          <button type="submit" className={styles.boton} disabled={enviando || !correo}>
            <LogIn size={17} strokeWidth={2.6} aria-hidden="true" />
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className={styles.alterno}>
          ¿No tienes cuenta? <Link href="/empezar">Créala al armar tu kit</Link>
        </p>
      </section>
    </div>
  );
}
