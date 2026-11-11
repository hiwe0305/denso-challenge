# flywheel-console

Local, read-mostly web console over the flywheel data tree (`fwdata/`). It indexes
catalog, robot, egocentric and story files, serves a small UI on `127.0.0.1`, runs a
fixed set of laptop jobs, and offers a chat over a local model.

## Commands

- `fw console index [--only catalog,robot,ego,story]` build the index.
- `fw console serve [--port 4178]` serve the UI on `127.0.0.1`.
- `fw console bench [--tag TEXT]` run the chat benchmark.

## Rules

- Binds `127.0.0.1` only; POST only when `Host` and `Origin` are the console itself.
- Model endpoint is `http://127.0.0.1:11435/v1` (SSH tunnel); no hosted API.
- Writes only under `$FW_ROOT/console/`; never reads `vault/` or `holdout` paths.
- Egocentric frames only from `*.deid.mp4`.
- Every path comes from `flywheel.console.paths.ConsolePaths`.
- No imports of other lanes, adapters or heavy runtimes (import-linter contract).
