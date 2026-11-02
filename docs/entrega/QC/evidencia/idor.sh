#!/usr/bin/env bash
# IDOR de solo lectura: una cuenta nueva (atacante) contra recursos de la cuenta E2E.
set -u
U=http://127.0.0.1:3000
J=$(mktemp); C="curl -s -m 60 -b $J -c $J -H content-type:application/json"
TID=$(cat ~/s0work/tid); PED=$(jq -r .pedido_id ~/s0work/orden.json); TX=$(jq -r .transaccion_wompi ~/s0work/orden.json)
M="qc.idor.$(date +%s)@example.org"; COL=bccf0294-f6b2-5203-84dd-e7fc643ae17f
code(){ curl -s -o /tmp/qc_idor_body -w '%{http_code}' -m 60 -b $J "$@"; }
r=$($C -o /dev/null -w '%{http_code}' -X POST $U/api/registro -d "{\"correo\":\"$M\",\"clave\":\"Qc-Idor-2026!x\",\"hijos\":[{\"colegio_id\":\"$COL\",\"grado\":\"Primero\",\"apodo\":\"Ana\"}],\"acepta_terminos\":true}")
echo "registro_atacante $r"
grep -q tukit "$J" && echo "cookie_atacante si" || echo "cookie_atacante NO"
echo "GET trabajo_ajeno $(code $U/api/trabajos/$TID) $(head -c 90 /tmp/qc_idor_body)"
echo "GET pedido_ajeno $(code $U/api/pedidos/$PED) $(head -c 90 /tmp/qc_idor_body)"
IT=$(jq -r '[.. | objects | select(has("item_id")) | .item_id][0] // empty' ~/s0work/kit.json)
[ -n "$IT" ] && echo "GET opciones_linea_ajena $(code $U/api/trabajos/$TID/kits/Fan/lineas/$IT/opciones) $(head -c 90 /tmp/qc_idor_body)"
echo "GET casos_propios $(code $U/api/casos) n=$(jq '(.casos // .) | length' /tmp/qc_idor_body 2>/dev/null)"
echo "GET exportar_propio $(code $U/api/cuenta/mis-datos/exportar) contiene_pedido_ajeno=$(grep -c "$PED" /tmp/qc_idor_body) contiene_trabajo_ajeno=$(grep -c "$TID" /tmp/qc_idor_body)"
echo "GET pedido_ajeno_sin_cookie $(curl -s -o /tmp/qc_idor_body -w '%{http_code}' -m 60 $U/api/pedidos/$PED) $(head -c 90 /tmp/qc_idor_body)"
echo "GET trabajo_ajeno_sin_cookie $(curl -s -o /tmp/qc_idor_body -w '%{http_code}' -m 60 $U/api/trabajos/$TID) $(head -c 90 /tmp/qc_idor_body)"
echo "GET pedido_inventado $(code $U/api/pedidos/00000000-0000-4000-8000-000000000000) $(head -c 90 /tmp/qc_idor_body)"
rm -f $J /tmp/qc_idor_body
