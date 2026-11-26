"""`python -m flywheel.eval.agentqa.mcp --pack <pack.json>`: the MCP server on stdio (DA-49)."""

import sys

from flywheel.eval.agentqa.mcp.server import main

sys.exit(main())
