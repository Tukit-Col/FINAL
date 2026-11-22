import directorio from "@tukit/contrato/directorio-colegios.json";

export const dynamic = "force-static";

export function GET() {
  return Response.json(directorio);
}
