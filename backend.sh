#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.runtime"
BIN_DIR="$RUNTIME_DIR/bin"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
ENV_FILE="$ROOT_DIR/.env"
SKIP_BUILD=false
SKIP_MIGRATIONS=false

services=(research ai worker event-worker news-worker agent-worker api)
workers=(worker event-worker news-worker agent-worker)

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  die "Docker Compose is required. Install the Docker Compose plugin or docker-compose."
}

die() {
  echo "Error: $*" >&2
  exit 1
}

load_env() {
  [[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE. Copy .env.example to .env first."

  set -a
  # .env is a local shell-compatible environment file. Strip Windows CRLF.
  # shellcheck disable=SC1090
  source <(sed 's/\r$//' "$ENV_FILE")
  set +a

  : "${API_PORT:=8080}"
  : "${WEB_PORT:=3000}"
  : "${RESEARCH_PORT:=8001}"
  : "${AI_PORT:=8000}"
  : "${POSTGRES_PORT:=5432}"
  : "${POSTGRES_USER:=cryptobot}"
  : "${POSTGRES_PASSWORD:=cryptobot}"
  : "${POSTGRES_DB:=cryptobot}"
  : "${RESEARCH_DATABASE_USER:=research_service}"
  : "${RESEARCH_DATABASE_PASSWORD:=research_service}"
  : "${API_DATABASE_USER:=api_service}"
  : "${API_DATABASE_PASSWORD:=api_service}"
  : "${MIGRATION_DATABASE_URL:=postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}?sslmode=disable}"
  : "${DATABASE_URL:=postgres://${RESEARCH_DATABASE_USER}:${RESEARCH_DATABASE_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}?sslmode=disable}"
  : "${MARKET_DATABASE_URL:=postgres://${API_DATABASE_USER}:${API_DATABASE_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}?sslmode=disable}"
  : "${RESEARCH_SERVICE_URL:=http://127.0.0.1:${RESEARCH_PORT}}"
  : "${AI_SERVICE_URL:=http://127.0.0.1:${AI_PORT}}"
  : "${NEXT_PUBLIC_API_URL:=http://localhost:${API_PORT}}"
  : "${AI_PROVIDER:=auto}"
  : "${OPENAI_BASE_URL:=https://api.openai.com/v1}"
  : "${OPENAI_TIMEOUT_SECONDS:=30}"
  : "${OPENAI_REASONING_EFFORT:=low}"
  : "${LANGSMITH_TRACING:=}"
  : "${LANGSMITH_API_KEY:=}"
  : "${LANGSMITH_ENDPOINT:=https://api.smith.langchain.com}"
  : "${LANGSMITH_PROJECT:=}"
  : "${LANGSMITH_WORKSPACE_ID:=}"
  : "${GROQ_MODEL:=openai/gpt-oss-120b}"
  : "${GROQ_BASE_URL:=https://api.groq.com/openai/v1}"
  : "${GROQ_TIMEOUT_SECONDS:=10}"
  : "${INTERNAL_SERVICE_TOKEN:=development-internal-token}"
  : "${CORS_ALLOWED_ORIGINS:=http://localhost:3000}"
  : "${COOKIE_SECURE:=false}"
  : "${WORKER_ID:=worker-v2}"
  : "${EVENT_WORKER_ID:=events-v2}"
  if [[ "$AI_PROVIDER" == openai || -n "${OPENAI_API_KEY:-}" ]]; then
    : "${OPENAI_MODEL:=gpt-4o-mini}"
    case "${SENTIMENT_MODEL:-}" in
      ""|sentiment-v1|openai/gpt-oss-120b|gpt-oss-120b) SENTIMENT_MODEL="${OPENAI_MODEL#openai/}" ;;
      openai/*) SENTIMENT_MODEL="${SENTIMENT_MODEL#openai/}" ;;
    esac
    case "${SENTIMENT_MODEL_VERSION:-}" in
      ""|2026-08-01|groq-*) SENTIMENT_MODEL_VERSION="${OPENAI_MODEL_VERSION:-openai-gpt-4o-mini}" ;;
    esac
  else
    : "${SENTIMENT_MODEL:=sentiment-v1}"
    : "${SENTIMENT_MODEL_VERSION:=2026-08-01}"
  fi

  export API_PORT WEB_PORT RESEARCH_PORT AI_PORT POSTGRES_PORT POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
  export RESEARCH_DATABASE_USER RESEARCH_DATABASE_PASSWORD API_DATABASE_USER API_DATABASE_PASSWORD
  export MIGRATION_DATABASE_URL DATABASE_URL MARKET_DATABASE_URL RESEARCH_SERVICE_URL AI_SERVICE_URL
  export NEXT_PUBLIC_API_URL
  export AI_PROVIDER OPENAI_API_KEY OPENAI_MODEL OPENAI_MODEL_VERSION OPENAI_BASE_URL OPENAI_TIMEOUT_SECONDS OPENAI_REASONING_EFFORT MODEL_CHEAP
  export LANGSMITH_TRACING LANGSMITH_API_KEY LANGSMITH_ENDPOINT LANGSMITH_PROJECT LANGSMITH_WORKSPACE_ID
  export GROQ_API_KEY GROQ_MODEL GROQ_BASE_URL GROQ_TIMEOUT_SECONDS
  export SENTIMENT_MODEL SENTIMENT_MODEL_VERSION
  export INTERNAL_SERVICE_TOKEN CORS_ALLOWED_ORIGINS COOKIE_SECURE WORKER_ID EVENT_WORKER_ID
  export PORT="$API_PORT"
  export JWT_PRIVATE_KEY_FILE="${JWT_PRIVATE_KEY_FILE:-$RUNTIME_DIR/jwt-private.pem}"
  [[ "$JWT_PRIVATE_KEY_FILE" = /* ]] || JWT_PRIVATE_KEY_FILE="$ROOT_DIR/$JWT_PRIVATE_KEY_FILE"
  export JWT_PRIVATE_KEY_FILE
}

uses_external_database() {
  local name value
  for name in MIGRATION_DATABASE_URL DATABASE_URL MARKET_DATABASE_URL; do
    value="${!name:-}"
    [[ -z "$value" ]] && continue
    if [[ "$value" =~ @([^/:]+) ]]; then
      case "${BASH_REMATCH[1]}" in
        localhost|127.0.0.1|postgres) ;;
        *) return 0 ;;
      esac
    fi
  done
  return 1
}

ensure_runtime_dirs() {
  mkdir -p "$BIN_DIR" "$LOG_DIR" "$PID_DIR"
}

ensure_database() {
  if uses_external_database; then
    echo "External PostgreSQL configured; skipping Docker PostgreSQL."
    return
  fi
  compose --profile local-db up -d postgres
}

wait_database() {
  [[ -x "$VENV_PYTHON" ]] || die "Missing .venv. Run ./backend.sh setup first."
  local attempt
  for attempt in {1..45}; do
    if "$VENV_PYTHON" -c 'import os, psycopg; c=psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], connect_timeout=2); c.close()' >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done
  die "PostgreSQL did not become reachable. Check .env and Docker."
}

run_migrations() {
  if $SKIP_MIGRATIONS; then
    return
  fi
  wait_database
  (cd "$ROOT_DIR" && "$VENV_PYTHON" -m app.migrate)
}

pid_file() {
  echo "$PID_DIR/$1.pid"
}

is_running() {
  local name="$1" pid_file_path pid
  pid_file_path="$(pid_file "$name")"
  [[ -f "$pid_file_path" ]] || return 1
  pid="$(<"$pid_file_path")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

clear_stale_pid() {
  local name="$1" path
  path="$(pid_file "$name")"
  if [[ -f "$path" ]] && ! is_running "$name"; then
    rm -f "$path"
  fi
}

start_process() {
  local name="$1"
  shift
  local out="$LOG_DIR/$name.out.log"
  local err="$LOG_DIR/$name.err.log"
  local path pid

  clear_stale_pid "$name"
  if is_running "$name"; then
    echo "$name already running (PID $(<"$(pid_file "$name")"))"
    return
  fi

  path="$(pid_file "$name")"
  nohup bash -c 'cd -- "$1" && shift && exec "$@"' backend-launcher "$ROOT_DIR" "$@" >"$out" 2>"$err" < /dev/null &
  pid=$!
  echo "$pid" > "$path"
  echo "Started $name (PID $pid)"
}

build_api() {
  if $SKIP_BUILD; then
    return
  fi
  command -v go >/dev/null 2>&1 || die "Go 1.23 is required to build API."
  (cd "$ROOT_DIR/server" && go build -o "$BIN_DIR/cryptobot-api" ./cmd/api)
}

wait_http() {
  local name="$1" url="$2" attempt
  for attempt in {1..120}; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name ready at $url"
      return
    fi
    sleep 0.5
  done
  die "$name did not become ready. Check $LOG_DIR/$name.err.log"
}

start_research() {
  start_process research "$VENV_PYTHON" -m uvicorn app.main:app --app-dir "$ROOT_DIR" --host 127.0.0.1 --port "$RESEARCH_PORT"
  wait_http research "http://127.0.0.1:$RESEARCH_PORT/ready"
}

start_ai() {
  start_process ai "$VENV_PYTHON" -m uvicorn app.main:app --app-dir "$ROOT_DIR/ai" --host 127.0.0.1 --port "$AI_PORT"
  wait_http ai "http://127.0.0.1:$AI_PORT/health"
}

start_worker() {
  local name="$1"
  case "$name" in
    worker) start_process worker "$VENV_PYTHON" -m app.worker queue ;;
    event-worker) start_process event-worker "$VENV_PYTHON" -m app.event_worker ;;
    news-worker) start_process news-worker "$VENV_PYTHON" -m app.news_worker ;;
    agent-worker) start_process agent-worker "$VENV_PYTHON" -m app.agent_worker ;;
    *) die "Unknown worker: $name" ;;
  esac
}

start_api() {
  build_api
  [[ -x "$BIN_DIR/cryptobot-api" ]] || die "Missing API binary. Build without --skip-build first."
  start_process api "$BIN_DIR/cryptobot-api"
  wait_http api "http://127.0.0.1:$API_PORT/ready"
}

start_up() {
  ensure_database
  run_migrations
  start_research
  start_ai
  for worker in "${workers[@]}"; do start_worker "$worker"; done
  start_api
}

stop_service() {
  local name="$1" path pid
  path="$(pid_file "$name")"
  [[ -f "$path" ]] || return
  pid="$(<"$path")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$path"
  echo "Stopped $name"
}

stop_target() {
  local target="${1:-all}" service
  if [[ "$target" == workers ]]; then
    for service in "${workers[@]}"; do stop_service "$service"; done
  elif [[ "$target" == all ]]; then
    for service in "${services[@]}"; do stop_service "$service"; done
  else
    stop_service "$target"
  fi
}

show_status() {
  local service
  echo "Native services:"
  for service in "${services[@]}"; do
    if is_running "$service"; then
      echo "  $service: running (PID $(<"$(pid_file "$service")"))"
    else
      echo "  $service: stopped"
    fi
  done
  echo
  compose --profile local-db ps
}

setup() {
  local python_bin
  python_bin="$(command -v python3.12 || command -v python3 || true)"
  [[ -n "$python_bin" ]] || die "Python 3.12 is required."
  command -v go >/dev/null 2>&1 || die "Go 1.23 is required."
  "$python_bin" -m venv "$ROOT_DIR/.venv"
  "$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
  "$ROOT_DIR/.venv/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/ai/requirements.txt"
  (cd "$ROOT_DIR/server" && go mod download)
  echo "Native backend dependencies ready."
}

usage() {
  cat <<'EOF'
Usage: ./backend.sh <command> [target] [options]

Commands:
  up                    Start PostgreSQL and all backend services
  db                    Start local PostgreSQL only
  api                   Start Go API and research service
  research              Start research service
  ai                    Start AI service
  worker                Start backtest worker
  event-worker         Start event worker
  news-worker          Start news worker
  workers               Start all workers
  frontend              Start Next.js frontend in web/
  stop [service|workers] Stop services
  status                Show service and PostgreSQL status
  logs <service>        Follow service output
  down                  Stop backend and local PostgreSQL
  setup                 Create .venv and install dependencies

Options:
  --skip-build          Reuse existing API binary
  --skip-migrations     Skip database migrations
EOF
}

main() {
  local command="${1:-help}" target="" service
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-build) SKIP_BUILD=true ;;
      --skip-migrations) SKIP_MIGRATIONS=true ;;
      *) [[ -z "$target" ]] || die "Unknown argument: $1"; target="$1" ;;
    esac
    shift
  done

  if [[ "$command" == setup || "$command" == help ]]; then
    if [[ "$command" == setup ]]; then setup; return; fi
    if [[ "$command" == help ]]; then usage; return; fi
  fi

  load_env
  ensure_runtime_dirs
  VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

  if [[ "$command" == frontend ]]; then
    command -v pnpm >/dev/null 2>&1 || die "pnpm is required to run frontend."
    (cd "$ROOT_DIR/web" && PORT="$WEB_PORT" pnpm dev)
    return
  fi

  case "$command" in
    up) start_up ;;
    db) ensure_database ;;
    api) ensure_database; run_migrations; start_research; start_api ;;
    research) ensure_database; run_migrations; start_research ;;
    ai) start_ai ;;
    worker|event-worker|news-worker|agent-worker) ensure_database; run_migrations; start_worker "$command" ;;
    workers) ensure_database; run_migrations; for service in "${workers[@]}"; do start_worker "$service"; done ;;
    stop) stop_target "${target:-all}" ;;
    status) show_status ;;
    logs)
      [[ -n "$target" ]] || die "Use: ./backend.sh logs api"
      [[ -f "$LOG_DIR/$target.out.log" ]] || die "No log found for $target"
      tail -n 100 -f "$LOG_DIR/$target.out.log"
      ;;
    down) stop_target all; if ! uses_external_database; then compose --profile local-db down; fi ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
