# Copyright 2026 Choose Mission Ltd
# Portions copyright Affinidi Pte. Ltd., from `affinidi-labs-tgw-get-started`
# at commit 64babfc3ef27a3b1fb73ec9c25246b032b5708c4 (`a2a/a2a_server.py`), by
# way of the Lab's own repository. See PROVENANCE.md.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at http://www.apache.org/licenses/LICENSE-2.0
#
# See NOTICE for the attribution this file carries.
"""Serve the agent on localhost. The whole server, and this is all of it.

    ./venv/bin/python agent/ [port]     # default 8080
    curl localhost:8080/.well-known/agent-card.json

**No door on it.** A Lab target admits nothing but an Agent Gateway carrying the
key the Lab gave it; this one runs on your own machine and has nothing to
protect, so the API-key gate is left out rather than half-built. Add one here, in
front of `app`, if you put a descendant of this somewhere real.

Do not point a surface at this while running the recipe: that means a tunnel, and
a restarted tunnel invalidates the target URL and the agent card at once.
"""

from __future__ import annotations

import sys

import uvicorn
from starlette.applications import Starlette
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from agent import IdentityMirrorExecutor, create_agent_card

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# The card describes the protocol interface; the handler runs the executor and
# stores tasks. Route factories expose discovery and JSON-RPC over HTTP.
card = create_agent_card(f"http://localhost:{PORT}")
handler = DefaultRequestHandler(
    agent_card=card,
    agent_executor=IdentityMirrorExecutor(),
    task_store=InMemoryTaskStore(),
)
app = Starlette(routes=[
    *create_agent_card_routes(card),
    *create_jsonrpc_routes(handler, rpc_url="/"),
])

if __name__ == "__main__":
    # 127.0.0.1, not 0.0.0.0: this listens to your own machine and nothing else.
    uvicorn.run(app, host="127.0.0.1", port=PORT)
