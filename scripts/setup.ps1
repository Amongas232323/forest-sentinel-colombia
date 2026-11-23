# Forest Sentinel - preparación del entorno (Windows / PowerShell 5.1 o superior)
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
# Crea .env a partir de .env.example y rellena SOLO los valores que aún dicen CHANGE_ME,
# así que ejecutarlo otra vez no rompe una instalación existente.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env"
$Example = Join-Path $Root ".env.example"
$Utf8 = New-Object System.Text.UTF8Encoding($false)   # sin BOM: Docker Compose lee mal la primera línea con BOM

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "AVISO: $msg" -ForegroundColor Yellow }

# Contraseña aleatoria criptográficamente segura, solo letras y números (sin $ @ : / # %).
function New-Secret([int]$Length) {
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789".ToCharArray()
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $buf = New-Object byte[] 1
    $sb = New-Object System.Text.StringBuilder
    while ($sb.Length -lt $Length) {
        $rng.GetBytes($buf)
        if ($buf[0] -lt 248) { [void]$sb.Append($chars[$buf[0] % 62]) }   # rechazo: sin sesgo de módulo
    }
    $rng.Dispose()
    return $sb.ToString()
}

# Un intento real de conexión (IPv4 e IPv6) es más fiable que Get-NetTCPConnection o netstat.
function Test-PortInUse([int]$Port) {
    foreach ($h in @("127.0.0.1", "::1")) {
        $c = New-Object System.Net.Sockets.TcpClient
        try {
            $r = $c.BeginConnect($h, $Port, $null, $null)
            if ($r.AsyncWaitHandle.WaitOne(300) -and $c.Connected) { return $true }
        } catch { } finally { $c.Close() }
    }
    return $false
}

function Get-Value([string[]]$Lines, [string]$Key) {
    foreach ($l in $Lines) { if ($l -match "^$Key=(.*)$") { return ($Matches[1] -replace '\s+#.*$', '').Trim() } }
    return ""
}

function Set-Value([System.Collections.Generic.List[string]]$Lines, [string]$Key, [string]$Value) {
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^$Key=") { $Lines[$i] = "$Key=$Value"; return }
    }
    $Lines.Add("$Key=$Value")
}

# 1. Docker
Write-Step "Comprobando Docker"
$dockerOk = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
}
if ($dockerOk) { Write-Host "Docker está en marcha." } else { Write-Warn "Docker no está en marcha o no está instalado. Abre Docker Desktop y espera a que diga 'Engine running'." }

# 2. .env
Write-Step "Preparando .env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $Example $EnvFile
    Write-Host "Creado .env a partir de .env.example."
} else {
    Write-Host ".env ya existe: solo se rellenan los valores que aún dicen CHANGE_ME."
}
$lines = New-Object System.Collections.Generic.List[string]
[System.IO.File]::ReadAllLines($EnvFile, $Utf8) | ForEach-Object { $lines.Add($_) }

$generated = @()
foreach ($key in @("POSTGRES_PASSWORD", "REDIS_PASSWORD", "BOOTSTRAP_ADMIN_PASSWORD")) {
    $v = Get-Value $lines $key
    if ($v -eq "" -or $v -like "*CHANGE_ME*") { Set-Value $lines $key (New-Secret 24); $generated += $key }
}
$jwt = Get-Value $lines "JWT_SECRET"
if ($jwt -eq "" -or $jwt -like "*CHANGE_ME*" -or $jwt.Length -lt 64) { Set-Value $lines "JWT_SECRET" (New-Secret 72); $generated += "JWT_SECRET" }

# URLs para ejecutar la API fuera de Docker (en Docker, docker-compose.yml las reescribe).
$pgUser = Get-Value $lines "POSTGRES_USER"; if (-not $pgUser) { $pgUser = "forest" }
$pgDb = Get-Value $lines "POSTGRES_DB"; if (-not $pgDb) { $pgDb = "forest_sentinel" }
$pgPort = Get-Value $lines "POSTGRES_PORT"; if (-not $pgPort) { $pgPort = "5433" }
$rdPort = Get-Value $lines "REDIS_PORT"; if (-not $rdPort) { $rdPort = "6380" }
$pgPass = Get-Value $lines "POSTGRES_PASSWORD"
$rdPass = Get-Value $lines "REDIS_PASSWORD"
Set-Value $lines "DATABASE_URL" "postgresql+psycopg://${pgUser}:${pgPass}@127.0.0.1:${pgPort}/${pgDb}"
Set-Value $lines "REDIS_URL" "redis://:${rdPass}@127.0.0.1:${rdPort}/0"

# Entorno local: aceptar la web tanto en localhost como en 127.0.0.1.
$webPort = Get-Value $lines "WEB_PORT"; if (-not $webPort) { $webPort = "3000" }
$cors = Get-Value $lines "CORS_ORIGINS"
if ($cors -eq "" -or $cors -eq "http://localhost:3000") { Set-Value $lines "CORS_ORIGINS" "http://localhost:${webPort},http://127.0.0.1:${webPort}" }

# Datos del responsable de privacidad: valores neutros para una instalación local.
if ((Get-Value $lines "PRIVACY_CONTROLLER_NAME") -like "*CHANGE_ME*") { Set-Value $lines "PRIVACY_CONTROLLER_NAME" "Instalación local de Forest Sentinel" }
if ((Get-Value $lines "PRIVACY_CONTROLLER_ID") -like "*CHANGE_ME*") { Set-Value $lines "PRIVACY_CONTROLLER_ID" "Sin identificación (entorno local)" }

# 3. Correo del administrador (lo único que se pregunta)
Write-Step "Administrador inicial"
$current = Get-Value $lines "BOOTSTRAP_ADMIN_EMAIL"
$prompt = "Correo del administrador"
if ($current -and $current -ne "admin@example.org") { $prompt += " [$current]" }
while ($true) {
    $email = (Read-Host $prompt).Trim()
    if (-not $email -and $current -and $current -ne "admin@example.org") { $email = $current }
    if ($email -match '^[^@\s]+@[^@\s]+\.[^@\s]+$') { break }
    Write-Warn "Escribe un correo válido, por ejemplo nombre@dominio.org"
}
Set-Value $lines "BOOTSTRAP_ADMIN_EMAIL" $email

[System.IO.File]::WriteAllLines($EnvFile, $lines, $Utf8)
if ($generated.Count) { Write-Host ("Generados: " + ($generated -join ", ")) }

# 4. Variables de la terminal que Docker Compose impondría sobre el .env
Write-Step "Revisando variables de entorno de esta terminal"
$keys = $lines | Where-Object { $_ -match '^[A-Z_][A-Z0-9_]*=' } | ForEach-Object { ($_ -split '=', 2)[0] }
$shadow = Get-ChildItem Env: | Where-Object { $keys -contains $_.Name -or $_.Value -like "*CHANGE_ME*" }
if ($shadow) {
    Write-Warn "Estas variables están definidas en la terminal y Docker Compose les da prioridad sobre .env:"
    $shadow | ForEach-Object { Write-Host ("   " + $_.Name) }
    Write-Host "   Bórralas en esta sesión con:   Remove-Item Env:NOMBRE"
    Write-Host "   y de forma permanente con:     [Environment]::SetEnvironmentVariable('NOMBRE', `$null, 'User')"
} else { Write-Host "Ninguna variable de la terminal pisa el .env." }

# 5. Puertos
Write-Step "Comprobando puertos"
$ports = [ordered]@{
    "web"            = $webPort
    "API"            = (Get-Value $lines "API_PORT")
    "PostgreSQL"     = $pgPort
    "Redis"          = $rdPort
    "Mailpit (web)"  = (Get-Value $lines "MAILPIT_UI_PORT")
    "Mailpit (SMTP)" = (Get-Value $lines "MAILPIT_SMTP_PORT")
}
if (-not $ports["API"]) { $ports["API"] = "8000" }
if (-not $ports["Mailpit (web)"]) { $ports["Mailpit (web)"] = "8025" }
if (-not $ports["Mailpit (SMTP)"]) { $ports["Mailpit (SMTP)"] = "1025" }
$busy = $false
foreach ($name in $ports.Keys) {
    $p = [int]$ports[$name]
    if (Test-PortInUse $p) {
        # Intento identificar el proceso (no siempre es posible: Docker o IPv6 pueden ocultarlo).
        $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 } | Select-Object -First 1
        $who = ""
        if ($conn) { $who = " por '" + (Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue).ProcessName + "' (PID $($conn.OwningProcess))" }
        Write-Warn "El puerto $p ($name) ya está en uso$who."
        $busy = $true
    }
}
if ($busy) {
    Write-Host "   Si es una ejecución anterior de Forest Sentinel, detenla con:  docker compose --profile full down"
    Write-Host "   Si es otro programa: ciérralo (taskkill /PID <pid> /F) o cambia el puerto en .env"
    Write-Host "   (WEB_PORT, API_PORT, POSTGRES_PORT, REDIS_PORT, MAILPIT_UI_PORT, MAILPIT_SMTP_PORT)."
    Write-Host "   Si cambias WEB_PORT, ajusta también CORS_ORIGINS y PUBLIC_WEB_URL al nuevo puerto."
} else { Write-Host "Puertos libres." }

# 6. Resumen
$adminPass = Get-Value $lines "BOOTSTRAP_ADMIN_PASSWORD"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Listo. Credenciales del administrador:" -ForegroundColor Green
Write-Host "   Correo:      $email"
Write-Host "   Contraseña:  $adminPass"
Write-Host " (también quedan guardadas en .env, que nunca se sube a git)"
Write-Host ""
Write-Host " Siguiente paso:"
Write-Host "   docker compose --profile full up --build"
Write-Host " y abre http://localhost:$webPort"
Write-Host "============================================================" -ForegroundColor Green
if (-not $dockerOk) { Write-Warn "Recuerda arrancar Docker Desktop antes del siguiente paso." }
