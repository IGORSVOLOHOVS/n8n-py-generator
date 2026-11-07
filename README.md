# n8n-py-generator

A console tool for working on large n8n workflows as files instead of one JSON blob.

- **split** takes an exported n8n workflow and writes one folder per node. A Code node's `jsCode` goes to `code.js` and its `pythonCode` to `code.py`, so the code can be edited and diffed as code. The rest of each node stays in `node.json`, beside `connections.json` and `workflow_meta.json`.
- **build** puts the folders back together into a workflow JSON that n8n imports. With `--test <config.json>` it can disable chosen nodes or replace them with a Code node that returns the items in the node's own `test.json`, so a workflow runs without its real credentials.
- **docs** collects n8n node documentation for an AI agent: the community node packages listed on npm, saved as CSV chunks of 250 under `docs/n8n_community/`, and a sparse clone of the built-in nodes of `n8n-io/n8n` under `docs/n8n/`, with a guide in `docs/n8n_docs.md`.
- **install** puts an `n8n-gen` command on the user's PATH: a batch shim on Windows, a symlink in `~/.local/bin` elsewhere.

## Use

```powershell
.\recipe.ps1 run split --input workflow.json --output src
.\recipe.ps1 run build --input src --output workflow_generated.json
.\recipe.ps1 run build --input src --output workflow_test.json --test test-config.json
.\recipe.ps1 run docs
```

`docs/install.md` says what to install and `docs/manual.md` describes every command. `.\recipe.ps1 test` runs the tests, mypy and ruff; the tests never touch the network.

## Licence

MIT, see `LICENSE`.
