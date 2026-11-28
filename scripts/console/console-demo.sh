#!/usr/bin/env bash
# One console server for the recording day: read-only, chat on, checked before filming.
#
#   scripts/console/console-demo.sh start | stop | check
#
# PORT=4178     port on 127.0.0.1
# FW_ROOT=...   data folder (default: <repo>/fwdata)
# CHAT=env      (default) chat as `fw console serve` configures it: .env, CKEY_MODEL
# CHAT=nemotron chat on the Ollama of rtx3060; .env is not read, no hosted key is used
# LOG=...       server log (default: ~/console-demo-<port>.log)
#
# Prints no API key and no .env content.
set -euo pipefail

REPO=${REPO:-$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)}
FW_ROOT=${FW_ROOT:-$REPO/fwdata}
PORT=${PORT:-4178}
CHAT=${CHAT:-env}
LOG=${LOG:-$HOME/console-demo-$PORT.log}
BASE=http://127.0.0.1:$PORT

die() { echo "STOP: $*" >&2; exit 1; }
listener() { ss -ltnp | grep "127.0.0.1:$PORT " | grep -oP 'pid=\K[0-9]+' | head -1 || true; }

preflight() {
  [ -x "$REPO/.venv/bin/fw" ] || die "no $REPO/.venv/bin/fw (run: uv sync)"
  [ -z "$(listener)" ] || die "port $PORT is busy (pid $(listener)); run: $0 stop"
  local f
  for f in tasks story catalog; do
    python3 -c 'import json, sys; json.load(open(sys.argv[1]))' \
      "$FW_ROOT/console/index/$f.json" || die "index/$f.json is unreadable; run: fw console index"
  done
  local free_mb others
  free_mb=$(free -m | awk '/^Mem:/{print $7}')
  [ "$free_mb" -ge 4000 ] || echo "WARN: only ${free_mb} MB of RAM free; close other sessions and browsers"
  others=$(pgrep -fc '^[^ ]*python[^ ]* [^ ]*/fw console serve' || true) # not their shells
  [ "$others" = 0 ] || echo "WARN: $others other console process(es) running; film with one only"
}

check() {
  [ -n "$(listener)" ] || die "nothing listens on $PORT"
  python3 - "$BASE" <<'PY'
import json, sys, urllib.error, urllib.request

base = sys.argv[1]
local = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(path, data=None):
    req = urllib.request.Request(base + path, data, {"Origin": base} if data is not None else {})
    with local.open(req, timeout=120) as r:
        return r.read()


def get(path):
    return json.loads(call(path))


bad = []
status, tasks = get("/api/status"), get("/data/tasks.json")
if not status["locked"]:
    bad.append("server is NOT locked")
if not status["chat_on"]:
    bad.append("chat is off")
held = {x for r in tasks["rounds"] for x in r.get("withhold_eval") or []}
if not held:
    bad.append("no held run listed: check seed/tasks.yaml")
for path in ("/data/story.json", "/data/story.json/", "/data/./story.json"):
    story = get(path)
    shown = {r.get("run") for r in (story.get("pair") or {}).get("runs") or []}
    shown |= set((story.get("follow") or {}).get("runs") or {})
    if held & shown:
        bad.append(path + " serves a held result")
for line in (s["now"] for s in status["stages"] if s["id"] in ("eval", "loop")):
    if any(h in line for h in held):
        bad.append("a status line names a held run")
if any(s["state"] == "blocked" for s in status["stages"] if s["id"] in ("eval", "loop")):
    bad.append("eval/loop are blocked: the manifest or the index cannot be read")

warm = json.loads(call("/api/models/prewarm", b"{}"))  # the model answers, or it does not
models, cfg = get("/api/models"), get("/api/chat/config")
print("locked=%s chat_on=%s" % (status["locked"], status["chat_on"]))
print("tunnel=%s" % models["tunnel"])
print("chat model=%s hosted=%s" % (cfg.get("active_model"), cfg.get("hosted")))
print("prewarm ok=%s %s" % (warm.get("ok"), warm.get("error") or ""))
if not warm.get("ok"):
    bad.append("the chat model does not answer: " + str(warm.get("error")))
if cfg.get("active_kind") == "ollama" and models["tunnel"] != "up":
    bad.append("the chat uses the rtx3060 model but the tunnel is down")
if bad:
    sys.exit("FAIL: " + "; ".join(bad))
print("OK")
PY
}

start() {
  preflight
  local args=(console serve --port "$PORT" --lock --chat) envs=("FW_ROOT=$FW_ROOT")
  case "$CHAT" in
    env) ;;
    nemotron)
      [ ! -f "$FW_ROOT/console/config/chat_provider.json" ] ||
        die "$FW_ROOT/console/config/chat_provider.json overrides Nemotron; rename it first"
      args+=(--no-dotenv)
      envs+=("FW_CHAT_BASE_URL=" "FW_CHAT_MODEL=" "FW_CHAT_API_KEY=" "FW_CHAT_SELF_HOSTED=")
      ;;
    *) die "CHAT must be env or nemotron" ;;
  esac
  # the redirect is on the subshell and it execs: nothing else keeps this terminal's pipe open
  (cd "$REPO" && exec env "${envs[@]}" nohup setsid "$REPO/.venv/bin/fw" "${args[@]}") \
    >>"$LOG" 2>&1 </dev/null &
  for _ in $(seq 40); do
    curl -sf --noproxy '*' -m 2 -o /dev/null "$BASE/api/chat/config" && break
    sleep 0.5
  done
  echo "log: $LOG"
  check
  echo "open: $BASE/#/tasks"
}

stop() {
  local pid
  pid=$(listener)
  if [ -z "$pid" ]; then
    echo "nothing on $PORT"
    return
  fi
  tr '\0' ' ' <"/proc/$pid/cmdline" | grep -q 'console serve' || die "pid $pid on $PORT is not a console"
  kill "$pid" # the server closes its ssh tunnel on SIGTERM
  for _ in $(seq 20); do
    [ -z "$(listener)" ] && break
    sleep 0.3
  done
  [ -z "$(listener)" ] || die "pid $pid did not stop"
  echo "stopped $pid"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  check) check ;;
  *) die "usage: $0 start|stop|check" ;;
esac
