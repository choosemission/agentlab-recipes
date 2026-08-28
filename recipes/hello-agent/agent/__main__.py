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
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore

from agent import IdentityMirrorExecutor, create_agent_card

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# An A2A server is three things stacked, and this is all of them.
#
#   the card      what a caller discovers before sending anything. `url` is the
#                 address they should use: served directly it is this one, and
#                 served through a gateway surface the gateway overwrites it
#                 with its own access point — step 3 is noticing that
#   the executor  your agent. See `agent.py`
#   the handler   the SDK's plumbing between them: it parses `message/send`,
#                 creates the task, runs your executor, and stores the result
#
# `.build()` returns a Starlette app with the routes A2A requires already on it:
# `POST /` for JSON-RPC, and `/.well-known/agent-card.json` for discovery (plus
# `/.well-known/agent.json`, the older spelling, for callers that still ask for
# it). Add your own to `app.routes` if you want them.
app = A2AStarletteApplication(
    agent_card=create_agent_card(f"http://localhost:{PORT}"),
    http_handler=DefaultRequestHandler(
        agent_executor=IdentityMirrorExecutor(),
        # Where tasks live between turns. In memory, so a restart forgets every
        # one of them — fine here, and the thing to replace first if you build
        # something that has to survive one.
        task_store=InMemoryTaskStore(),
    ),
).build()

if __name__ == "__main__":
    # 127.0.0.1, not 0.0.0.0: this listens to your own machine and nothing else.
    uvicorn.run(app, host="127.0.0.1", port=PORT)
