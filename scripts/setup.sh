#!/usr/bin/env bash
# Forest Sentinel - preparación del entorno (Linux, macOS o Git Bash en Windows)
#
#   ./scripts/setup.sh
#
# Crea .env a partir de .env.example y rellena SOLO los valores que aún dicen CHANGE_ME,
# así que ejecutarlo otra vez no rompe una instalación existente.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
EXAMPLE="$ROOT/.env.example"

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33mAVISO: %s\033[0m\n' "$1"; }

# Contraseña aleatoria segura, solo letras y números (sin $ @ : / # %).
secret() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1"; }

get() { grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/[[:space:]]+$//' || true; }

set_value() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  if grep -qE "^$key=" "$ENV_FILE"; then
    awk -v k="$key" -v v="$value" 'BEGIN{FS=OFS="="} $0 ~ "^"k"=" {print k"="v; next} {print}' "$ENV_FILE" > "$tmp"
  else
    cat "$ENV_FILE" > "$tmp"; printf '%s=%s\n' "$key" "$value" >> "$tmp"
  fi
  cat "$tmp" > "$ENV_FILE"; rm -f "$tmp"
}

port_busy() {
  # Un intento real de conexión es más fiable que netstat (que en Windows cambia de idioma y de formato).
  local p="$1" h
  for h in 127.0.0.1 localhost; do
    if (exec 3<>"/dev/tcp/$h/$p") >/dev/null 2>&1; then return 0; fi
  done
  if command -v lsof >/dev/null 2>&1; then lsof -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 && return 0; fi
  return 1
}

# 1. Docker
step "Comprobando Docker"
DOCKER_OK=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then DOCKER_OK=1; echo "Docker está en marcha."
else warn "Docker no está en marcha o no está instalado. Arranca Docker Desktop (o el servicio docker) y vuelve a intentarlo."; fi

# 2. .env
step "Preparando .env"
if [ ! -f "$ENV_FILE" ]; then cp "$EXAMPLE" "$ENV_FILE"; echo "Creado .env a partir de .env.example."
else echo ".env ya existe: solo se rellenan los valores que aún dicen CHANGE_ME."; fi
# Quita retornos de carro por si el archivo se editó en Windows.
tmp="$(mktemp)"; tr -d '\r' < "$ENV_FILE" > "$tmp"; cat "$tmp" > "$ENV_FILE"; rm -f "$tmp"

GENERATED=()
for key in POSTGRES_PASSWORD REDIS_PASSWORD BOOTSTRAP_ADMIN_PASSWORD; do
  v="$(get "$key")"
  if [ -z "$v" ] || [[ "$v" == *CHANGE_ME* ]]; then set_value "$key" "$(secret 24)"; GENERATED+=("$key"); fi
done
jwt="$(get JWT_SECRET)"
if [ -z "$jwt" ] || [[ "$jwt" == *CHANGE_ME* ]] || [ "${#jwt}" -lt 64 ]; then set_value JWT_SECRET "$(secret 72)"; GENERATED+=("JWT_SECRET"); fi

PG_USER="$(get POSTGRES_USER)"; PG_USER="${PG_USER:-forest}"
PG_DB="$(get POSTGRES_DB)"; PG_DB="${PG_DB:-forest_sentinel}"
PG_PORT="$(get POSTGRES_PORT)"; PG_PORT="${PG_PORT:-5433}"
RD_PORT="$(get REDIS_PORT)"; RD_PORT="${RD_PORT:-6380}"
set_value DATABASE_URL "postgresql+psycopg://${PG_USER}:$(get POSTGRES_PASSWORD)@127.0.0.1:${PG_PORT}/${PG_DB}"
set_value REDIS_URL "redis://:$(get REDIS_PASSWORD)@127.0.0.1:${RD_PORT}/0"

WEB_PORT="$(get WEB_PORT)"; WEB_PORT="${WEB_PORT:-3000}"
cors="$(get CORS_ORIGINS)"
if [ -z "$cors" ] || [ "$cors" = "http://localhost:3000" ]; then set_value CORS_ORIGINS "http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT}"; fi

[[ "$(get PRIVACY_CONTROLLER_NAME)" == *CHANGE_ME* ]] && set_value PRIVACY_CONTROLLER_NAME "Instalación local de Forest Sentinel"
[[ "$(get PRIVACY_CONTROLLER_ID)" == *CHANGE_ME* ]] && set_value PRIVACY_CONTROLLER_ID "Sin identificación (entorno local)"

# 3. Correo del administrador (lo único que se pregunta)
step "Administrador inicial"
current="$(get BOOTSTRAP_ADMIN_EMAIL)"
prompt="Correo del administrador"
[ -n "$current" ] && [ "$current" != "admin@example.org" ] && prompt="$prompt [$current]"
while true; do
  read -r -p "$prompt: " email
  email="$(printf '%s' "$email" | tr -d '[:space:]')"
  if [ -z "$email" ] && [ -n "$current" ] && [ "$current" != "admin@example.org" ]; then email="$current"; fi
  if [[ "$email" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; then break; fi
  warn "Escribe un correo válido, por ejemplo nombre@dominio.org"
done
set_value BOOTSTRAP_ADMIN_EMAIL "$email"
[ "${#GENERATED[@]}" -gt 0 ] && echo "Generados: ${GENERATED[*]}"

# 4. Variables de la terminal que Docker Compose impondría sobre el .env
step "Revisando variables de entorno de esta terminal"
SHADOW=()
while IFS= read -r key; do
  if printenv "$key" >/dev/null 2>&1; then SHADOW+=("$key"); fi
done < <(grep -oE '^[A-Z_][A-Z0-9_]*=' "$ENV_FILE" | tr -d '=')
while IFS= read -r name; do
  [[ " ${SHADOW[*]-} " == *" $name "* ]] || SHADOW+=("$name")
done < <(env | grep -E '^[A-Za-z_][A-Za-z0-9_]*=.*CHANGE_ME' | cut -d= -f1)
if [ "${#SHADOW[@]}" -gt 0 ]; then
  warn "Estas variables están definidas en la terminal y Docker Compose les da prioridad sobre .env:"
  for n in "${SHADOW[@]}"; do echo "   $n"; done
  echo "   Bórralas con:  unset NOMBRE   (y quítalas de ~/.bashrc, ~/.zshrc o ~/.profile si las pusiste ahí)"
else echo "Ninguna variable de la terminal pisa el .env."; fi

# 5. Puertos
step "Comprobando puertos"
API_PORT="$(get API_PORT)"; API_PORT="${API_PORT:-8000}"
MP_UI="$(get MAILPIT_UI_PORT)"; MP_UI="${MP_UI:-8025}"
MP_SMTP="$(get MAILPIT_SMTP_PORT)"; MP_SMTP="${MP_SMTP:-1025}"
BUSY=0
for entry in "web:$WEB_PORT" "API:$API_PORT" "PostgreSQL:$PG_PORT" "Redis:$RD_PORT" "Mailpit web:$MP_UI" "Mailpit SMTP:$MP_SMTP"; do
  name="${entry%%:*}"; p="${entry##*:}"
  if port_busy "$p"; then warn "El puerto $p ($name) ya está en uso."; BUSY=1; fi
done
if [ "$BUSY" -eq 1 ]; then
  echo "   Si es una ejecución anterior de Forest Sentinel:  docker compose --profile full down"
  echo "   Si es otro programa, ciérralo o cambia el puerto en .env (WEB_PORT, API_PORT, POSTGRES_PORT,"
  echo "   REDIS_PORT, MAILPIT_UI_PORT, MAILPIT_SMTP_PORT). Si cambias WEB_PORT, ajusta CORS_ORIGINS y PUBLIC_WEB_URL."
else echo "Puertos libres."; fi

# 6. Resumen
printf '\n\033[32m============================================================\033[0m\n'
echo " Listo. Credenciales del administrador:"
echo "   Correo:      $email"
echo "   Contraseña:  $(get BOOTSTRAP_ADMIN_PASSWORD)"
echo " (también quedan guardadas en .env, que nunca se sube a git)"
echo
echo " Siguiente paso:"
echo "   docker compose --profile full up --build"
echo " y abre http://localhost:$WEB_PORT"
printf '\033[32m============================================================\033[0m\n'
[ "$DOCKER_OK" -eq 1 ] || warn "Recuerda arrancar Docker antes del siguiente paso."
