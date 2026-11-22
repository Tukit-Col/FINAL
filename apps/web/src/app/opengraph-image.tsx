import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export const alt = "Tukit — la lista del colegio, resuelta";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Imagen() {
  const logo = await readFile(join(process.cwd(), "src/app/icon.png"));
  const src = `data:image/png;base64,${logo.toString("base64")}`;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 56,
          background: "linear-gradient(135deg, #fdf9ee 0%, #e0efff 100%)",
        }}
      >
        <img src={src} width={300} height={300} alt="" />
        <div style={{ display: "flex", flexDirection: "column", maxWidth: 560 }}>
          <div style={{ fontSize: 96, fontWeight: 800, color: "#1e3a8a" }}>Tukit</div>
          <div style={{ fontSize: 40, color: "#475569", marginTop: 8 }}>
            La lista del colegio, resuelta.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
