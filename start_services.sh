#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"

FLASK_HOST="127.0.0.1"
FLASK_PORT="5000"
MLFLOW_HOST="127.0.0.1"
MLFLOW_PORT="5001"

if [[ ! -x "$VENV_BIN/python" ]]; then
  echo "No se encontro Python en .venv/bin/python"
  echo "Verifica que el entorno virtual exista en $ROOT_DIR/.venv"
  exit 1
fi

if [[ ! -x "$VENV_BIN/mlflow" ]]; then
  echo "No se encontro MLflow en .venv/bin/mlflow"
  echo "Instala dependencias: $VENV_BIN/pip install -r requirements.txt"
  exit 1
fi

cleanup() {
  echo ""
  echo "Deteniendo servicios..."
  if [[ -n "${MLFLOW_PID:-}" ]] && kill -0 "$MLFLOW_PID" 2>/dev/null; then
    kill "$MLFLOW_PID" 2>/dev/null || true
  fi
  if [[ -n "${FLASK_PID:-}" ]] && kill -0 "$FLASK_PID" 2>/dev/null; then
    kill "$FLASK_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"

  if [[ -n "$pids" ]]; then
    echo "Liberando puerto $port..."
    # Termina procesos previos que ocupan el puerto para evitar conflictos.
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}

free_port "$FLASK_PORT"
free_port "$MLFLOW_PORT"

echo "Iniciando MLflow en http://$MLFLOW_HOST:$MLFLOW_PORT"
"$VENV_BIN/mlflow" server \
  --host "$MLFLOW_HOST" \
  --port "$MLFLOW_PORT" \
  --backend-store-uri "sqlite:///$ROOT_DIR/mlflow.db" \
  --default-artifact-root "$ROOT_DIR/mlruns" \
  > "$ROOT_DIR/mlflow.log" 2>&1 &
MLFLOW_PID=$!

sleep 2
if ! kill -0 "$MLFLOW_PID" 2>/dev/null; then
  echo "MLflow no pudo iniciar. Revisa mlflow.log"
  exit 1
fi

echo "Iniciando Flask en http://$FLASK_HOST:$FLASK_PORT"
"$VENV_BIN/python" "$ROOT_DIR/run.py" > "$ROOT_DIR/flask.log" 2>&1 &
FLASK_PID=$!

sleep 2
if ! kill -0 "$FLASK_PID" 2>/dev/null; then
  echo "Flask no pudo iniciar. Revisa flask.log"
  exit 1
fi

echo ""
echo "Servicios activos:"
echo "- Flask:  http://$FLASK_HOST:$FLASK_PORT"
echo "- MLflow: http://$MLFLOW_HOST:$MLFLOW_PORT"
echo ""
echo "Logs:"
echo "- $ROOT_DIR/flask.log"
echo "- $ROOT_DIR/mlflow.log"
echo ""
echo "Presiona Ctrl+C para detener ambos servicios."

wait "$FLASK_PID"
