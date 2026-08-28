# Agent Lab recipes

Runnable code for the [Agent Lab](https://agentlab.choosemission.com) — a
neutral environment, run by MISSION, for practical experimentation with
**cross-boundary agent trust**: letting agents work with systems and other
agents owned by somebody else, without either party taking on risk they cannot
account for.

One directory per recipe, under `recipes/`. Clone once and you have them all.

| Recipe | What you run here | Status |
| --- | --- | --- |
| [`hello-agent`](recipes/hello-agent/) | An A2A client that calls a Lab-hosted agent through **your own** Agent Gateway, and the two identity schemas that make the exchange accountable | available |

Recipes that need no code — `hello-gateway`, which you should do first — are
worked through in a console and have nothing here.

## Finding your way

This repository is the *execution* half. Discovery — what exists, what to do
next, what each recipe teaches — lives on the Lab's catalogue MCP server:

```bash
claude mcp add --transport http lab-catalog https://agentlab.choosemission.com/mcp
```

Signing in opens a browser. Once connected, `get_started` orients you and
`get_recipe` returns any recipe's full entry.

Each recipe directory has a `README.md` for you and a `CLAUDE.md` for your
agent. Start with the `README.md`.

## Ground rules

These are Lab-wide.

- **Calls to Lab targets go through an Agent Gateway, and the targets admit
  nothing else.** Being unable to route around the gateway is the security
  property the Lab demonstrates, not an obstacle to work around.
- **Secrets stay local.** `.env` is gitignored here; keep it that way. No key
  the Lab hands you belongs in a commit.
- **This is an experimental environment.** No production data, no personal
  content, no real credentials beyond the ones the Lab issues. No warranty, no
  SLA.

## Licence

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) — parts of this
repository are derived from Affinidi's
[affinidi-labs-tgw-get-started](https://github.com/affinidi/affinidi-labs-tgw-get-started),
and each recipe records its provenance.
