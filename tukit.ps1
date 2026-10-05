# Equivalente en Windows de `make arriba` / `make abajo` / `make estado`.
#
# El Makefile asume Linux/macOS (.venv/bin/python, nohup, kill), asi que aqui
# se hace lo mismo con PowerShell. Postgres corre en Docker en el puerto 5433
# porque el 5432 lo ocupa el Postgres instalado en la maquina.
#
#   .\tukit.ps1 arriba    # levanta Postgres, los 6 servicios y los 3 trabajadores
#   .\tukit.ps1 abajo     # detiene servicios y trabajadores (Postgres sigue)
#   .\tukit.ps1 estado    # pregunta al gateway quien responde
#   .\tukit.ps1 embeddings  # calcula el canal semantico del catalogo (pide GEMINI_API_KEY)
#   .\tukit.ps1 exportar    # = make curaduria-exportar: listas revisadas -> datos/ (para git)
#   .\tukit.ps1 importar    # = make curaduria-importar: datos/ -> base (tras un git pull)
#
# Las llaves (GEMINI_API_KEY, etc.) van en `.env`, en la raiz: git lo ignora.

param([ValidateSet('arriba', 'abajo', 'estado', 'embeddings', 'exportar', 'importar')][string]$accion = 'arriba')

$raiz = $PSScriptRoot
$py = Join-Path $raiz '.venv\Scripts\python.exe'
$ejecucion = Join-Path $raiz '.ejecucion'

$env:TUKIT_DB_PORT = '5433'
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = (@('libs\py\tukit_comun', 'servicios\identidad', 'servicios\catalogo',
    'servicios\inteligencia', 'servicios\gateway', 'servicios\comercio',
    'servicios\operacion') | ForEach-Object { Join-Path $raiz $_ }) -join ';'
$env:TUKIT_IDENTIDAD_URL = 'http://127.0.0.1:8011'
$env:TUKIT_CATALOGO_URL = 'http://127.0.0.1:8012'
$env:TUKIT_INTELIGENCIA_URL = 'http://127.0.0.1:8013'
$env:TUKIT_COMERCIO_URL = 'http://127.0.0.1:8014'
$env:TUKIT_OPERACION_URL = 'http://127.0.0.1:8015'

# `.env` gana sobre los valores de arriba. Lineas VARIABLE=valor; # es comentario.
$archivoEnv = Join-Path $raiz '.env'
if (Test-Path $archivoEnv) {
    foreach ($linea in Get-Content $archivoEnv) {
        if ($linea -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            Set-Item "env:$($Matches[1])" $Matches[2]
        }
    }
}

$servicios = [ordered]@{
    'identidad'    = @('-m', 'tukit_identidad.api', '--puerto', '8011')
    'catalogo'     = @('-m', 'tukit_catalogo.api', '--puerto', '8012')
    'inteligencia' = @('-m', 'tukit_inteligencia.api', '--puerto', '8013')
    'comercio'     = @('-m', 'tukit_comercio.api', '--puerto', '8014')
    'operacion'    = @('-m', 'tukit_operacion.api', '--puerto', '8015')
    'gateway'      = @('-m', 'tukit_gateway.api', '--puerto', '8010')
}
$trabajadores = [ordered]@{
    'repartidor'       = @('-m', 'tukit_operacion.repartidor', '--seguir')
    'poller'           = @('-m', 'tukit_inteligencia.poller', '--seguir')
    'poller-identidad' = @('-m', 'tukit_identidad.poller', '--seguir')
    # Desde ADR 0024 el pipeline ya no corre dentro de la API: sin el
    # trabajador, ningun trabajo sale de `encolado`.
    'trabajador'       = @('-m', 'tukit_inteligencia.trabajador', '--seguir')
    # Compensacion C1 de la saga (ADR 0023): libera reservas y cancela pedidos
    # sin pagar cuando vence la ventana de pago.
    'barredor'         = @('-m', 'tukit_comercio.barredor', '--seguir')
}

function Estado {
    try {
        Invoke-RestMethod http://127.0.0.1:8010/v1/servicios | ConvertTo-Json -Depth 5
    } catch {
        Write-Host '  La puerta no responde en http://127.0.0.1:8010'
    }
}

function Abajo {
    Get-ChildItem $ejecucion -Filter *.pid -ErrorAction SilentlyContinue | ForEach-Object {
        $id = Get-Content $_.FullName
        try { Stop-Process -Id $id -Force -ErrorAction Stop } catch {}
        Remove-Item $_.FullName
    }
    Write-Host 'Procesos detenidos.'
}

function Lanzar($nombre, $argumentos) {
    $p = Start-Process -FilePath $py -ArgumentList $argumentos -WorkingDirectory $raiz `
        -RedirectStandardOutput "$ejecucion\$nombre.log" -RedirectStandardError "$ejecucion\$nombre.err.log" `
        -WindowStyle Hidden -PassThru
    Set-Content "$ejecucion\$nombre.pid" $p.Id
}

switch ($accion) {
    'estado' { Estado }
    'embeddings' {
        Push-Location (Join-Path $raiz 'servicios\catalogo')
        & $py -m tukit_catalogo.enriquecer
        Pop-Location
    }
    'exportar' {
        # Conceptos y listas revisadas, luego sus colegios, luego los productos
        # (nuevos, reclasificados y con atributos corregidos), ofertas y precios.
        & $py -m tukit_catalogo.curaduria exportar
        if ($LASTEXITCODE -eq 0) { & $py -m tukit_identidad.curaduria exportar }
        if ($LASTEXITCODE -eq 0) {
            Push-Location (Join-Path $raiz 'servicios\catalogo')
            & $py -m tukit_catalogo.representantes --escribir
            & $py -m tukit_catalogo.volcar --escribir
            # El precio ordena los niveles (un economico nunca mas caro que un
            # premium) y la base vuelve a quedar igual al CSV que se comparte.
            if ($LASTEXITCODE -eq 0) { & $py -m tukit_catalogo.nivelar --escribir }
            if ($LASTEXITCODE -eq 0) { & $py -m tukit_catalogo.cargador --datos ..\..\datos\catalogo | Select-Object -First 8 }
            Pop-Location
        }
    }
    'importar' {
        # Los conceptos primero (bd-cargar): una lista no entra sin sus conceptos.
        Push-Location (Join-Path $raiz 'servicios\catalogo')
        & $py -m tukit_catalogo.cargador --datos ..\..\datos\catalogo | Select-Object -First 8
        Pop-Location
        & $py -m tukit_identidad.curaduria importar
        & $py -m tukit_catalogo.curaduria importar
    }
    'abajo' { Abajo }
    'arriba' {
        New-Item -ItemType Directory -Force $ejecucion | Out-Null
        Abajo | Out-Null
        docker start tukit_postgres | Out-Null
        foreach ($s in $servicios.Keys) { Lanzar $s $servicios[$s] }
        Write-Host 'Esperando a que respondan...'
        for ($i = 0; $i -lt 60; $i++) {
            try {
                if ((Invoke-RestMethod http://127.0.0.1:8010/v1/servicios).todos_arriba) { break }
            } catch {}
            Start-Sleep -Milliseconds 500
        }
        foreach ($t in $trabajadores.Keys) { Lanzar $t $trabajadores[$t] }
        Estado
        Write-Host '  Base para el frontend: http://127.0.0.1:8010'
        Write-Host "  Registros en $ejecucion"
    }
}
