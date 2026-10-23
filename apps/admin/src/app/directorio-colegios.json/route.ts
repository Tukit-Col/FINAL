// El directorio de colegios de Bogota, servido en `/directorio-colegios.json`
// para que el buscador de colegio lo cargue en el navegador sin pegarle a
// ningun servicio. La copia unica vive en `@tukit/contrato` (la comparten las dos
// apps sin importarse entre ellas); aqui solo se sirve, estatico: el JSON se
// fija en el build y cambia solo cuando se regenera.

import directorio from "@tukit/contrato/directorio-colegios.json";

export const dynamic = "force-static";

export function GET() {
  return Response.json(directorio);
}
