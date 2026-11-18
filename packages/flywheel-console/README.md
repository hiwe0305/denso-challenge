# flywheel-console

Local, read-mostly web console over the flywheel data tree (`fwdata/`). It indexes
catalog, robot, egocentric and story files, serves a small UI on `127.0.0.1`, runs a
fixed set of laptop jobs, and offers a chat over a local model.

## Commands

- `fw console index [--only catalog,robot,ego,story]` build the index.
- `fw console serve [--port 4178] [--lock] [--chat]` serve the UI on `127.0.0.1`. `--lock` is
  read-only (no jobs, uploads or chat); `--lock --chat` keeps the chat, which only reads.
- `fw console bench [--tag TEXT]` run the chat benchmark.

## Rules

- Binds `127.0.0.1` only; POST only when `Host` and `Origin` are the console itself.
- Chat model: by default Nemotron in the Ollama of `rtx3060`, reached at `http://127.0.0.1:11435`
  (SSH tunnel). The server opens the tunnel and loads the model when it starts.
- Another model is opt-in, by environment only (Hiếu, 16/11/2026): `FW_CHAT_BASE_URL` (any
  OpenAI chat-completions server, called with the `openai` library), `FW_CHAT_MODEL`,
  `FW_CHAT_API_KEY`, `FW_CHAT_NAME`. Example: `FW_CHAT_BASE_URL=https://openrouter.ai/api/v1`.
  The key is never written to a file or a log.
- A server that is not on this machine is hosted. While a hosted model answers, the chat tools
  do not see catalog rows whose `data_class` is not `public` (design 27/10 section 8.4).
- Writes only under `$FW_ROOT/console/`; never reads `vault/` or `holdout` paths.
- Egocentric frames only from `*.deid.mp4`.
- Every path comes from `flywheel.console.paths.ConsolePaths`.
- No imports of other lanes, adapters or heavy runtimes (import-linter contract).
