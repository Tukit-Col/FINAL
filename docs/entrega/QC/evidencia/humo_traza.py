import os, sys
sys.path.insert(0, sys.argv[1])
import humo
humo.OPERADOR_DEMO = {"correo": "operador@tukit.co", "clave": os.environ["HUMO_CLAVE"]}
orig = humo._pedir
tok = {}
def traza(base, ruta, cuerpo=None, *, token=None):
    # Variante B: la bandeja GET de operacion se pide con la sesion del operador.
    if os.environ.get("CON_TOKEN") and ruta == "/v1/operacion/casos" and cuerpo is None and not token:
        if "t" not in tok: tok["t"] = humo._token_operador(base)
        token = tok["t"]
    print("->", "POST" if cuerpo else "GET", ruta.split("?")[0], file=sys.stderr)
    return orig(base, ruta, cuerpo, token=token)
humo._pedir = traza
sys.exit(humo.main([]))
