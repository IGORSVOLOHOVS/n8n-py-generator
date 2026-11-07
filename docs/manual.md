# Manual

```powershell
.\recipe.ps1 run <command> [options]
```

| command | options | what it does |
| --- | --- | --- |
| `split` | `--input/-i <workflow.json>` `--output/-o <folder>` | writes the workflow as a folder tree; an existing output folder is deleted first |
| `build` | `--input/-i <folder>` `--output/-o <workflow.json>` `[--test/-t <config.json>]` | assembles the folder tree back into a workflow JSON |
| `docs` | none | collects n8n node documentation into `docs/` of the working folder |
| `install` | none | puts an `n8n-gen` command on the user's PATH |

With no command the tool prints its help.

## The folder tree

```
src/
├── workflow_meta.json     every top-level key except nodes and connections
├── connections.json
└── nodes/
    └── <node name>/       "/" and "\" in a name become "_"
        ├── node.json      the node without its code
        ├── code.js        the node's jsCode, when it has one
        ├── code.py        the node's pythonCode, when it has one
        └── test.json      optional: the items a mocked node returns
```

`build` reads the node folders in name order, so the order of `nodes` in the result can differ from the original export. n8n places nodes by their `position`, not by that order.

## The test configuration

A JSON object from node name to mode:

```json
{ "Fetch leads": "mock", "Send to Slack": "disabled" }
```

- `disabled` sets `"disabled": true` on the node.
- `mock` replaces the node with a Code node (`typeVersion` 2) that returns the content of its `test.json`, and drops its credentials. A list of plain objects is wrapped as `[{"json": ...}]`, a list already in that form is kept, and a single object becomes one item. Without a `test.json` the node stays as it is and a warning is printed.

A Code node named in the configuration does not get its `code.js` or `code.py` back, whatever the mode.

## Errors

A file that cannot be read or written is reported on the console and the command ends without a traceback. The exit code is 0 in that case too.
