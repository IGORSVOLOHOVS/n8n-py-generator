# n8n-py-generator: software requirements specification

Reverse-engineered on 2026-11-18 from commit `554a79e`. Every requirement
describes behaviour present in the code at that commit; the requirements were
read from the code, and an independent check on 2026-11-19 ran the test suite and
a few probes (see `docs/README.md`, section 11).
Documentation hub: [`docs/README.md`](docs/README.md).

## 1. Purpose and scope

Purpose: let an n8n workflow be stored, edited and diffed as a folder tree
with Code-node source in separate files, and be assembled back into a
workflow JSON, optionally with nodes disabled or mocked; and collect n8n node
references for an AI agent (`README.md:3-8`).

In scope:

- `split`: workflow JSON to folder tree.
- `build`: folder tree to workflow JSON, with an optional test configuration.
- `docs`: npm community-node list to CSV, built-in node sources from `n8n-io/n8n`, a fixed guide file.
- `install`: a command shim (Windows) or symlink (other platforms).

Out of scope (nothing in the code does it): talking to an n8n instance
(import, export, execution), validating a workflow against n8n's schema,
merging or diffing workflows, editing credentials.

## 2. Context

| Actor / system | Role | Source |
| --- | --- | --- |
| User at a console | Runs one of the four commands, directly or through `recipe.ps1 run` | `n8n_gen.py:390-422`, `recipe.ps1:60-63` |
| n8n (external) | Produces the exported workflow JSON and imports the built one; the tool does not contact it | `README.md:5-6` |
| npm registry search API | Source of the community-node list | `n8n_gen.py:220` |
| GitHub `n8n-io/n8n` | Source of built-in node code, fetched with `git` | `n8n_gen.py:284-289` |
| File system | Input and output of every command | whole module |

Runtime: CPython 3.13 (`pyproject.toml:20`), dependencies installed by uv
from `uv.lock` (`docs/install.md:4`). `docs` needs `git` on PATH and network
access to `registry.npmjs.org` and `github.com` (`docs/install.md:5`). The
code branches on `sys.platform == "win32"` only in `install`
(`n8n_gen.py:342`).

## 3. Functional requirements

### 3.1 Split

- **FR-1.** The system shall read the file given by `--input` as UTF-8 JSON and write a folder tree under `--output` consisting of `workflow_meta.json`, `connections.json` and `nodes/<folder>/` for each element of `nodes`.
  Source: `n8n_gen.py:37-86`. Verification: `test_split_writes_a_folder_per_node_and_extracts_the_code`.
- **FR-2.** The system shall delete the output folder, if it exists, before writing.
  Source: `n8n_gen.py:44-47`. Verification: `test_split_replaces_an_existing_output_folder`.
- **FR-3.** The system shall name a node's folder after its `name` with `/` and `\` replaced by `_`, and use `Unnamed_Node` when the node has no `name`.
  Source: `n8n_gen.py:55`. Verification: `test_split_writes_a_folder_per_node_and_extracts_the_code` (`/` replacement); no test (`\` replacement, `Unnamed_Node`).
- **FR-4.** The system shall move `parameters.jsCode` into `code.js` and `parameters.pythonCode` into `code.py`, removing them from the node, and write the rest of the node to `node.json`.
  Source: `n8n_gen.py:60-76`. Verification: `test_split_writes_a_folder_per_node_and_extracts_the_code`.
- **FR-5.** The system shall write the workflow's `connections` to `connections.json` and every other top-level key except `nodes` and `connections` to `workflow_meta.json`.
  Source: `n8n_gen.py:79-86`. Verification: `test_split_writes_a_folder_per_node_and_extracts_the_code`.

### 3.2 Build

- **FR-6.** The system shall assemble a workflow from `workflow_meta.json`, `connections.json` and each subdirectory of `nodes/` in sorted order, ignoring plain files in `nodes/`.
  Source: `n8n_gen.py:93-115`, `173`. Verification: `test_assemble_skips_loose_files_in_the_nodes_folder`.
- **FR-7.** The system shall put the content of `code.js` into `parameters.jsCode` and of `code.py` into `parameters.pythonCode` when those files exist.
  Source: `n8n_gen.py:160-169`. Verification: `test_split_then_build_gives_back_the_same_workflow`.
- **FR-8.** The system shall skip FR-7 for a node whose resulting `type` is `n8n-nodes-base.code` and whose name is a key of the test configuration.
  Source: `n8n_gen.py:159`, `docs/manual.md:43`. Verification: no test.
- **FR-9.** The system shall write the assembled workflow to `--output` as UTF-8 JSON.
  Source: `n8n_gen.py:187-189`. Verification: `test_split_then_build_gives_back_the_same_workflow`.
- **FR-10.** The system shall, for a tree produced by `split` and no test configuration, produce a workflow equal as a JSON value to the original, except that `nodes` comes out in the sorted order of the folder names (`n8n_gen.py:110`, `docs/manual.md:30`).
  Source: `n8n_gen.py:37-174`. Verification: `test_split_then_build_gives_back_the_same_workflow` (synthetic four-node workflow whose nodes are already in that order; a workflow listing `Zeta` before `Alpha` came back reordered in a probe run outside the suite). The same probe confirmed FR-3 `Unnamed_Node`, FR-8 (a `disabled` Code node came back with empty `parameters`) and FR-16.

### 3.3 Test configuration

- **FR-11.** The system shall, when `--test` is given, read that file as a JSON object mapping node names to modes.
  Source: `n8n_gen.py:182-185`. Verification: `test_build_reads_the_test_config_from_a_file`.
- **FR-12.** The system shall set `"disabled": true` on a node whose mode is `disabled`, leaving its type unchanged.
  Source: `n8n_gen.py:122-126`. Verification: `test_test_config_disables_a_node`.
- **FR-13.** The system shall, for a node whose mode is `mock` and whose folder holds `test.json`, set `type` to `n8n-nodes-base.code`, `typeVersion` to 2, `parameters` to `{"jsCode": "return <items>;"}`, and remove `credentials`.
  Source: `n8n_gen.py:127-151`. Verification: `test_mock_turns_a_node_into_a_code_node_without_credentials`.
- **FR-14.** The system shall build the mock items as: a list whose every element is an object with a `json` key is kept; any other list has each element wrapped as `{"json": element}`; a non-list becomes `[{"json": value}]`.
  Source: `n8n_gen.py:133-140`. Verification: `test_mock_turns_a_node_into_a_code_node_without_credentials`, `test_mock_leaves_items_that_are_already_wrapped`, `test_mock_wraps_a_single_object`.
- **FR-15.** The system shall log a warning and leave the node unchanged when the mode is `mock` and `test.json` is missing.
  Source: `n8n_gen.py:153-156`. Verification: `test_mock_without_test_json_warns_and_keeps_the_node`.
- **FR-16.** The system shall ignore, without a message, modes other than `disabled` and `mock` and configured names that match no node; FR-8 still applies, so a Code node with an unknown mode loses its code.
  Source: `n8n_gen.py:120-157`. Verification: no test.

### 3.4 Error handling of split and build

- **FR-17.** The system shall catch any exception in `split` or `build`, log `Failed to split workflow: <error>` or `Failed to build workflow: <error>`, and return normally; a failed build writes no output file.
  Source: `n8n_gen.py:89-90`, `186-192`, `docs/manual.md:45-47`. Verification: `test_split_of_a_missing_file_logs_and_does_not_raise`, `test_build_of_a_missing_folder_logs_and_does_not_raise`.

### 3.5 Docs collection

- **FR-18.** The system shall request `https://registry.npmjs.org/-/v1/search?text=keywords:n8n-community-node-package&size=250&from=<offset>` with offsets 0, 250, ..., stopping on an empty `objects` list or when the offset exceeds `total`, pausing 0.5 s between requests.
  Source: `n8n_gen.py:206-256`. Verification: `test_docs_pages_through_npm_and_writes_csv_chunks`, `test_docs_stops_on_an_empty_page`.
- **FR-19.** The system shall stop paging and log the cause on a non-200 status or a body that is not JSON.
  Source: `n8n_gen.py:223-231`. Verification: `test_docs_stops_on_an_http_error`, `test_docs_stops_on_a_body_that_is_not_json`.
- **FR-20.** The system shall save the collected `name`, `description`, `version` and npm `link` of each package into `docs/n8n_community/n8n_nodes_<n>.csv`, at most 250 rows per file, with a header and no index column, and log `No nodes collected.` when there are none.
  Source: `n8n_gen.py:236-268`. Verification: `test_docs_pages_through_npm_and_writes_csv_chunks`, `test_docs_stops_on_an_http_error`.
- **FR-21.** The system shall shallow-clone `https://github.com/n8n-io/n8n.git` sparsely into `n8n_temp`, check out `packages/nodes-base/nodes`, copy it into `docs/n8n/`, log the stderr of a failed `git` step, and remove `n8n_temp` before and after.
  Source: `n8n_gen.py:274-298`. Verification: `test_docs_pages_through_npm_and_writes_csv_chunks` (command text), `test_docs_reports_a_failed_git_clone_and_still_writes_the_guide`.
- **FR-22.** The system shall write the fixed guide text to `docs/n8n_docs.md` whatever the outcome of FR-18 to FR-21, unless the `git` step raises something other than `subprocess.CalledProcessError`, the only exception caught there (`n8n_gen.py:295`).
  Source: `n8n_gen.py:300-334`. Verification: `test_docs_reports_a_failed_git_clone_and_still_writes_the_guide`.

### 3.6 Install

- **FR-23.** The system shall, on Windows, write `<home>\AppData\Local\Microsoft\WindowsApps\n8n-gen.bat` containing `@echo off` and `python "<absolute path of n8n_gen.py>" %*`.
  Source: `n8n_gen.py:344-355`. Verification: `test_install_on_windows_writes_a_batch_shim`.
- **FR-24.** The system shall, on other platforms, add the owner-execute bit to `n8n_gen.py`, create `~/.local/bin`, remove an existing `n8n-gen` there with a warning, and create a symlink `~/.local/bin/n8n-gen` to the script; on an exception it shall log the error and stop.
  Source: `n8n_gen.py:356-377`. Verification: `test_install_elsewhere_links_the_script_into_local_bin`, `test_install_reports_a_failed_link`.
- **FR-25.** The system shall warn, with a hint, when the target folder is not found in `PATH` by a case-insensitive substring test.
  Source: `n8n_gen.py:379-387`. Verification: `test_install_on_windows_writes_a_batch_shim`.

### 3.7 Command line and start-up

- **FR-26.** The system shall offer the subcommands `split`, `build`, `docs` and `install`, require `--input` and `--output` for `split` and `build`, and print help when no subcommand is given.
  Source: `n8n_gen.py:391-422`. Verification: `test_main_dispatches_each_command`, `test_split_requires_input_and_output`, `test_main_without_a_command_prints_help`.
- **FR-27.** The system shall call `python-dotenv`'s `load_dotenv()` at import and continue without it when the package is not importable.
  Source: `n8n_gen.py:19-24`. Verification: no test.
- **FR-28.** The package shall install a console command `n8n-gen` bound to `n8n_gen:main`.
  Source: `pyproject.toml:29-30`. Verification: no test.

### 3.8 Repository standard

- **FR-29.** The repository shall provide the lab recipe `recipe.ps1` with the verbs `build`, `install`, `uninstall`, `clean`, `run`, `publish`, `info`, `test`, as required by the lab standard (repo-quality-template; "revision 4.0.0 of the lab requirements" with exceptions R-02, R-09, R-41, R-42).
  Source: `recipe.ps1:3`, `README.md:25-27`. Verification: `.\recipe.ps1 test`.

### 3.9 Declared but not implemented, or not verified

| Statement | Where | What the code does |
| --- | --- | --- |
| The built workflow is one "that n8n imports" | `README.md:6` | No test or fixture imports into n8n; the test workflow is synthetic (`tests/test_n8n_gen.py:17-50`) |
| The test mode means "a workflow runs without its real credentials" | `README.md:6` | Only mocked nodes lose `credentials`; disabled nodes keep them (`n8n_gen.py:122-123`, `147-148`) |
| "A database of over 8000+ community nodes" | generated guide, `n8n_gen.py:317` | Fixed text; the number of collected packages is not computed into it |
| `install` help: "(~/.local/bin/n8n-gen)" | `n8n_gen.py:409` | On Windows the target is `WindowsApps\n8n-gen.bat` (`n8n_gen.py:345-346`) |
| Docstring: "logic from n8n_node_scraber.py" | `n8n_gen.py:196` | No such file in the repository or in its history (`git log --all`) |

## 4. Interfaces

### 4.1 Command line

`n8n_gen.py <command> [options]`, or `.\recipe.ps1 run <command> [options]`
(`docs/manual.md:3-5`).

| Command | Options | Effect | Source |
| --- | --- | --- | --- |
| `split` | `--input/-i FILE` (required), `--output/-o DIR` (required) | FR-1 to FR-5 | `n8n_gen.py:395-397` |
| `build` | `--input/-i DIR` (required), `--output/-o FILE` (required), `--test/-t FILE` | FR-6 to FR-17 | `n8n_gen.py:400-403` |
| `docs` | none | FR-18 to FR-22 | `n8n_gen.py:406` |
| `install` | none | FR-23 to FR-25 | `n8n_gen.py:409` |
| (none) | - | prints help | `n8n_gen.py:421-422` |

Exit codes: 2 from argparse on missing required options
(`test_split_requires_input_and_output`); 0 otherwise, including commands
whose failure they catch themselves (`docs/manual.md:47`). Read from the code,
not run: an exception outside those handlers, such as a missing dependency at
import (`n8n_gen.py:13-17`) or a failing `os.makedirs` in `docs`
(`n8n_gen.py:201-202`), ends with a traceback and Python's exit code 1.

### 4.2 Files

| File | Format | Written by / read by | Source |
| --- | --- | --- | --- |
| `workflow_meta.json` | JSON object, top-level keys except `nodes`, `connections` | split / build | `n8n_gen.py:84-86`, `99-100` |
| `connections.json` | JSON, the workflow's `connections` | split / build | `n8n_gen.py:79-81`, `103-104` |
| `nodes/<folder>/node.json` | JSON object, the node without `jsCode` / `pythonCode` | split / build | `n8n_gen.py:75-76`, `114-115` |
| `nodes/<folder>/code.js`, `code.py` | text, the code verbatim | split / build | `n8n_gen.py:63-72`, `160-169` |
| `nodes/<folder>/test.json` | JSON, list or single value (FR-14) | user / build | `n8n_gen.py:128-140` |
| test configuration | JSON object `{ "<node name>": "disabled" \| "mock" }` | user / build | `n8n_gen.py:120-127`, `docs/manual.md:34-37` |
| `docs/n8n_community/n8n_nodes_<n>.csv` | CSV, columns `name,description,version,link` | docs | `n8n_gen.py:238-265` |
| `docs/n8n/` | copy of `packages/nodes-base/nodes` of `n8n-io/n8n` | docs | `n8n_gen.py:284-289` |
| `docs/n8n_docs.md` | Markdown, fixed text | docs | `n8n_gen.py:301-334` |
| `n8n-gen.bat` / `~/.local/bin/n8n-gen` | batch shim / symlink | install | `n8n_gen.py:345-373` |

JSON output uses 2-space indentation and keeps non-ASCII characters
(`ensure_ascii=False`) (`n8n_gen.py:76`, `81`, `86`, `189`).

### 4.3 Network

| Endpoint | Method | Use | Source |
| --- | --- | --- | --- |
| `https://registry.npmjs.org/-/v1/search` | HTTP GET, no timeout, no headers set | package list; reads `objects[].package.{name,description,version,links.npm}` and `total` | `n8n_gen.py:220-248` |
| `https://github.com/n8n-io/n8n.git` | `git clone --depth 1 --filter=blob:none --sparse` | built-in node sources | `n8n_gen.py:285` |

## 5. Data

| Entity | Fields the code uses | Storage |
| --- | --- | --- |
| Workflow | `nodes`, `connections`, all other keys passed through | input/output JSON; `workflow_meta.json` + `connections.json` + `nodes/` |
| Node | `name`, `type`, `typeVersion`, `parameters.jsCode`, `parameters.pythonCode`, `credentials`, `disabled`; other keys passed through | `node.json`, `code.js`, `code.py` |
| Test configuration | node name to mode | user JSON file |
| Mock items | n8n item list `[{"json": ...}]` | `test.json`; embedded in generated `jsCode` |
| Community package record | `name`, `description`, `version`, `link` | CSV chunks of 250 |

No database. All 16 `open()` calls in `n8n_gen.py` pass `encoding="utf-8"`;
the CSV files are written by `pandas.DataFrame.to_csv` without an explicit
encoding (`n8n_gen.py:265`).

## 6. Non-functional requirements

- **NFR-1.** Runs on CPython 3.13 only. Source: `pyproject.toml:20` (`>=3.13,<3.14`), `uv.lock:3`.
- **NFR-2.** Dependencies resolve from the lock file, never re-resolved at run or test time. Source: `recipe.ps1:61`, `99-106` (`uv run --frozen`), `docs/install.md:4`.
- **NFR-3.** The test suite makes no network or `git` calls. Source: `tests/test_n8n_gen.py:1-5`, `211-229`.
- **NFR-4.** Statement coverage of `n8n_gen` stays at or above 93 %. Source: `pyproject.toml:71`.
- **NFR-5.** `n8n_gen.py` and `tools/` pass mypy; the sources pass ruff rules `E4,E7,E9,F,I` with line length 120 and LF line endings. Source: `pyproject.toml:51-63`, `73-75`.
- **NFR-6.** Consecutive npm search requests are at least 0.5 s apart. Source: `n8n_gen.py:256`.
- **NFR-7.** Console output goes through `rich` logging at INFO level with markup. Source: `n8n_gen.py:27-34`.
- **NFR-8.** Text files in the repository use LF, except `*.ps1`, `*.bat`, `*.cmd` (CRLF). Source: `.gitattributes`.

## 7. Constraints and dependencies

| Package | Constraint (`pyproject.toml`) | Locked (`uv.lock`) |
| --- | --- | --- |
| requests | `>=2.31` (`:23`) | 2.34.2 |
| python-dotenv | `>=1.0` (`:24`) | 1.2.4 |
| rich | `>=13.0` (`:25`) | 15.0.0 |
| pandas | `>=2.2` (`:26`) | 3.1.1 (with numpy 2.5.4) |
| ruff (dev) | `==0.16.1` (`:36`) | 0.16.1 |
| mypy (dev) | `==2.3.0` (`:37`) | 2.3.0 |
| pytest (dev) | `==8.4.2` (`:38`) | 8.4.2 |
| pytest-cov (dev) | `==5.0.0` (`:39`) | 5.0.0 |
| coverage (dev) | `==7.15.2` (`:40`) | 7.15.2 |
| setuptools (build backend) | `==80.9.0` (`:10`) | - |

Other constraints: uv (version not pinned in project files); `git` on PATH
for `docs`; the clone step relies on a shell with `cd`, `&&` and `cp -rf`
(`n8n_gen.py:284-293`). The project is not installed into its own
environment by uv (`pyproject.toml:49`, `package = false`); the source tree
is run directly. Licence: MIT (`LICENSE`, `pyproject.toml:19`).

## 8. Acceptance

1. `.\recipe.ps1 test` exits with `$LASTEXITCODE` 0 (`README.md:19`, `CLAUDE.md` rule 3). This runs every test named in section 3, the coverage floor (NFR-4) and the static checks (NFR-5).
2. Requirements marked "no test" (FR-3 `Unnamed_Node`, FR-8, FR-16, FR-27, FR-28) are checked by hand: split a workflow with an unnamed node; build with a configuration that marks a Code node `disabled` and confirm its code is absent; build with an unknown mode on a non-Code node and confirm no message and no change; `.\recipe.ps1 build`, install the wheel in a scratch environment and run `n8n-gen --help`.
3. Not covered by any file in the repository: importing a built or test workflow into n8n, and running `docs` against the live registry and GitHub. Both stay open (section 9).

## 9. Open questions

1. Who the users are and which n8n versions and export formats are targeted; no real export is in the repository.
2. Whether `typeVersion` 2 for the mock Code node (`n8n_gen.py:144`) matches the n8n versions in use.
3. Whether a failed command should exit non-zero; `docs/manual.md:47` documents exit code 0 without a reason.
4. Whether node-name collisions after FR-3 (and on case-insensitive file systems) need handling; the code does not detect them.
5. Answered in part. Which folder `load_dotenv()` searches: the code passes no path (`n8n_gen.py:22`), so python-dotenv's `find_dotenv()` starts at the folder of the calling file, `n8n_gen.py`, and walks up to the root; it uses the working folder only in a REPL, under a debugger or tracer, or in a frozen build. Read in the source of the locked python-dotenv 1.2.4 (`dotenv/main.py`, `find_dotenv`). So `docs/install.md:13` ("at the working folder") holds only when the two folders coincide, as under `recipe.ps1 run`. Still open: why `.env` is loaded at all, given that only `PATH` is read (`n8n_gen.py:380`).
6. Whether the npm search API returns all packages through `from` paging, and where the guide's "over 8000+" figure came from (`n8n_gen.py:317`).
7. Whether `docs` works on Windows without a `cp` executable on PATH (`n8n_gen.py:288`); the tests replace `subprocess.run`.
8. Whether any Gitea runner has executed `.gitea/workflows/*`; `CLAUDE.md` describes protection "stage 1" until `propose` and `release-gate` have each run once.
9. What the lab exceptions R-41 (#10) and R-42 (#11) require; the issues are on a server not reachable from the public repository (`README.md:27`).
10. The origin of `n8n_node_scraber.py` named in `n8n_gen.py:196`: it has never been in this repository's history (`git log --all`), so it lived somewhere else; where is unknown.
