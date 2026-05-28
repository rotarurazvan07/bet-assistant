#!/bin/sh
set -eu

mkdir -p /app/workspace/config /app/workspace/data
cp -r /app/config/. /app/workspace/config/

uvicorn main:app --host 0.0.0.0 --port 8000 &
api_pid="$!"

nginx -g "daemon off;" &
nginx_pid="$!"

term_handler() {
    kill "$api_pid" "$nginx_pid" 2>/dev/null || true
    wait "$api_pid" "$nginx_pid" 2>/dev/null || true
}

trap term_handler INT TERM

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$nginx_pid" 2>/dev/null; do
    sleep 1
done

term_handler
