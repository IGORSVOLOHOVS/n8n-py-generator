"""Tests for n8n_gen: split, build, the test configuration, docs and install.

Nothing here reaches the network: `requests.get` and `subprocess.run` are replaced
inside `n8n_gen`, and every file is written under pytest's tmp_path.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import n8n_gen


def sample_workflow() -> dict:
    return {
        "name": "Sample",
        "active": False,
        "settings": {"executionOrder": "v1"},
        "nodes": [
            {
                "name": "A Trigger",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "parameters": {},
            },
            {
                "name": "B Code",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "parameters": {"jsCode": "return items;\n"},
            },
            {
                "name": "C Python",
                "type": "n8n-nodes-base.code",
                "typeVersion": 2,
                "parameters": {"language": "python", "pythonCode": "return _input.all()\n"},
            },
            {
                "name": "D Http/Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4,
                "parameters": {"url": "https://example.invalid"},
                "credentials": {"httpHeaderAuth": {"id": "1", "name": "key"}},
            },
        ],
        "connections": {"A Trigger": {"main": [[{"node": "B Code", "type": "main", "index": 0}]]}},
    }


def write_workflow(path: Path, workflow: dict) -> Path:
    path.write_text(json.dumps(workflow), encoding="utf-8")
    return path


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def split_sample(tmp_path: Path) -> Path:
    source = write_workflow(tmp_path / "workflow.json", sample_workflow())
    out = tmp_path / "src"
    n8n_gen.split_workflow(str(source), str(out))
    return out


def test_split_writes_a_folder_per_node_and_extracts_the_code(tmp_path: Path) -> None:
    out = split_sample(tmp_path)
    nodes = out / "nodes"
    assert sorted(p.name for p in nodes.iterdir()) == ["A Trigger", "B Code", "C Python", "D Http_Request"]
    assert (nodes / "B Code" / "code.js").read_text(encoding="utf-8") == "return items;\n"
    assert (nodes / "C Python" / "code.py").read_text(encoding="utf-8") == "return _input.all()\n"
    node_b = read_json(nodes / "B Code" / "node.json")
    assert isinstance(node_b, dict) and "jsCode" not in node_b["parameters"]
    node_c = read_json(nodes / "C Python" / "node.json")
    assert isinstance(node_c, dict) and node_c["parameters"] == {"language": "python"}
    assert not (nodes / "A Trigger" / "code.js").exists()
    assert read_json(out / "connections.json") == sample_workflow()["connections"]
    assert read_json(out / "workflow_meta.json") == {
        "name": "Sample",
        "active": False,
        "settings": {"executionOrder": "v1"},
    }


def test_split_replaces_an_existing_output_folder(tmp_path: Path) -> None:
    out = tmp_path / "src"
    out.mkdir()
    (out / "stale.txt").write_text("old", encoding="utf-8")
    source = write_workflow(tmp_path / "workflow.json", sample_workflow())
    n8n_gen.split_workflow(str(source), str(out))
    assert not (out / "stale.txt").exists()
    assert (out / "nodes").is_dir()


def test_split_of_a_missing_file_logs_and_does_not_raise(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    n8n_gen.split_workflow(str(tmp_path / "absent.json"), str(tmp_path / "src"))
    assert "Failed to split workflow" in caplog.text


def test_split_then_build_gives_back_the_same_workflow(tmp_path: Path) -> None:
    out = split_sample(tmp_path)
    built = tmp_path / "built.json"
    n8n_gen.build_workflow(str(out), str(built))
    assert read_json(built) == sample_workflow()


def test_assemble_skips_loose_files_in_the_nodes_folder(tmp_path: Path) -> None:
    out = split_sample(tmp_path)
    (out / "nodes" / "README.txt").write_text("not a node", encoding="utf-8")
    workflow = n8n_gen.assemble_workflow_dict(str(out))
    assert [node["name"] for node in workflow["nodes"]] == ["A Trigger", "B Code", "C Python", "D Http/Request"]


def test_test_config_disables_a_node(tmp_path: Path) -> None:
    out = split_sample(tmp_path)
    workflow = n8n_gen.assemble_workflow_dict(str(out), {"A Trigger": "disabled"})
    trigger = next(node for node in workflow["nodes"] if node["name"] == "A Trigger")
    assert trigger["disabled"] is True
    assert trigger["type"] == "n8n-nodes-base.manualTrigger"


def mocked_node(tmp_path: Path, test_data: object) -> dict:
    out = split_sample(tmp_path)
    (out / "nodes" / "D Http_Request" / "test.json").write_text(json.dumps(test_data), encoding="utf-8")
    workflow = n8n_gen.assemble_workflow_dict(str(out), {"D Http/Request": "mock"})
    return next(node for node in workflow["nodes"] if node["name"] == "D Http/Request")


def mocked_items(node: dict) -> object:
    code = node["parameters"]["jsCode"]
    assert code.startswith("return ") and code.endswith(";")
    return json.loads(code[len("return ") : -1])


def test_mock_turns_a_node_into_a_code_node_without_credentials(tmp_path: Path) -> None:
    node = mocked_node(tmp_path, [{"id": 1}, {"id": 2}])
    assert node["type"] == "n8n-nodes-base.code"
    assert node["typeVersion"] == 2
    assert "credentials" not in node
    assert list(node["parameters"]) == ["jsCode"]
    assert mocked_items(node) == [{"json": {"id": 1}}, {"json": {"id": 2}}]


def test_mock_leaves_items_that_are_already_wrapped(tmp_path: Path) -> None:
    node = mocked_node(tmp_path, [{"json": {"id": 1}}])
    assert mocked_items(node) == [{"json": {"id": 1}}]


def test_mock_wraps_a_single_object(tmp_path: Path) -> None:
    node = mocked_node(tmp_path, {"id": 7})
    assert mocked_items(node) == [{"json": {"id": 7}}]


def test_mock_without_test_json_warns_and_keeps_the_node(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    out = split_sample(tmp_path)
    workflow = n8n_gen.assemble_workflow_dict(str(out), {"D Http/Request": "mock"})
    node = next(node for node in workflow["nodes"] if node["name"] == "D Http/Request")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert "credentials" in node
    assert "not found" in caplog.text


def test_build_reads_the_test_config_from_a_file(tmp_path: Path) -> None:
    out = split_sample(tmp_path)
    config = tmp_path / "test-config.json"
    config.write_text(json.dumps({"A Trigger": "disabled"}), encoding="utf-8")
    built = tmp_path / "built.json"
    n8n_gen.build_workflow(str(out), str(built), str(config))
    workflow = read_json(built)
    assert isinstance(workflow, dict)
    assert workflow["nodes"][0]["disabled"] is True


def test_build_of_a_missing_folder_logs_and_does_not_raise(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    built = tmp_path / "built.json"
    n8n_gen.build_workflow(str(tmp_path / "absent"), str(built))
    assert "Failed to build workflow" in caplog.text
    assert not built.exists()


class FakeResponse:
    def __init__(self, status_code: int, payload: object = None, broken: bool = False) -> None:
        self.status_code = status_code
        self.payload = payload
        self.broken = broken

    def json(self) -> object:
        if self.broken:
            raise ValueError("not JSON")
        return self.payload


def npm_page(start: int, count: int, total: int) -> dict:
    objects = [
        {
            "package": {
                "name": f"n8n-nodes-{i}",
                "description": f"node {i}",
                "version": "1.0.0",
                "links": {"npm": f"https://www.npmjs.com/package/n8n-nodes-{i}"},
            }
        }
        for i in range(start, start + count)
    ]
    return {"objects": objects, "total": total}


def run_docs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, responses: list[FakeResponse], git_error: bool = False):
    urls: list[str] = []
    commands: list[str] = []

    def fake_get(url: str) -> FakeResponse:
        urls.append(url)
        return responses.pop(0)

    def fake_run(command: str, **kwargs: object) -> None:
        commands.append(command)
        if git_error:
            raise subprocess.CalledProcessError(128, command, stderr=b"fatal: no network")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(n8n_gen.requests, "get", fake_get)
    monkeypatch.setattr(n8n_gen.subprocess, "run", fake_run)
    monkeypatch.setattr(n8n_gen.time, "sleep", lambda seconds: None)
    n8n_gen.parse_docs()
    return urls, commands


def test_docs_pages_through_npm_and_writes_csv_chunks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pages = [FakeResponse(200, npm_page(0, 250, 300)), FakeResponse(200, npm_page(250, 50, 300))]
    urls, commands = run_docs(monkeypatch, tmp_path, pages)
    assert [url.rsplit("from=", 1)[1] for url in urls] == ["0", "250"]
    first = (tmp_path / "docs" / "n8n_community" / "n8n_nodes_1.csv").read_text(encoding="utf-8").splitlines()
    second = (tmp_path / "docs" / "n8n_community" / "n8n_nodes_2.csv").read_text(encoding="utf-8").splitlines()
    assert first[0] == "name,description,version,link"
    assert len(first) == 251 and len(second) == 51
    assert first[1].startswith("n8n-nodes-0,node 0,1.0.0,")
    assert len(commands) == 1 and "sparse-checkout set packages/nodes-base/nodes" in commands[0]
    guide = (tmp_path / "docs" / "n8n_docs.md").read_text(encoding="utf-8")
    assert guide.startswith("# n8n Documentation Guide for AI Agent")
    assert "docs/n8n_community/" in guide


def test_docs_stops_on_an_http_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_docs(monkeypatch, tmp_path, [FakeResponse(503)])
    assert "HTTP 503" in caplog.text
    assert "No nodes collected" in caplog.text
    assert not list((tmp_path / "docs" / "n8n_community").iterdir())


def test_docs_stops_on_a_body_that_is_not_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_docs(monkeypatch, tmp_path, [FakeResponse(200, broken=True)])
    assert "Failed to parse JSON response" in caplog.text


def test_docs_stops_on_an_empty_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    urls, _ = run_docs(monkeypatch, tmp_path, [FakeResponse(200, {"objects": [], "total": 0})])
    assert len(urls) == 1


def test_docs_reports_a_failed_git_clone_and_still_writes_the_guide(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_docs(monkeypatch, tmp_path, [FakeResponse(200, npm_page(0, 3, 3))], git_error=True)
    assert "Git operation failed: fatal: no network" in caplog.text
    assert (tmp_path / "docs" / "n8n_docs.md").is_file()
    assert not (tmp_path / "n8n_temp").exists()


def test_install_on_windows_writes_a_batch_shim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(n8n_gen.sys, "platform", "win32")
    monkeypatch.setattr(n8n_gen.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setenv("PATH", "")
    n8n_gen.install_script()
    shim = tmp_path / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "n8n-gen.bat"
    script = Path(n8n_gen.__file__).resolve()
    assert shim.read_text(encoding="utf-8") == f'@echo off\npython "{script}" %*'
    assert "is not in your PATH" in caplog.text


def test_install_elsewhere_links_the_script_into_local_bin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    links: list[tuple[Path, Path]] = []
    modes: list[int] = []
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "n8n-gen").write_text("old link", encoding="utf-8")
    monkeypatch.setattr(n8n_gen.sys, "platform", "linux")
    monkeypatch.setattr(n8n_gen.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(n8n_gen.os, "chmod", lambda path, mode: modes.append(mode))
    monkeypatch.setattr(n8n_gen.os, "symlink", lambda source, target: links.append((Path(source), Path(target))))
    monkeypatch.setenv("PATH", str(bin_dir))
    n8n_gen.install_script()
    assert links == [(Path(n8n_gen.__file__).resolve(), bin_dir / "n8n-gen")]
    assert not (bin_dir / "n8n-gen").exists()
    assert modes and modes[0] & 0o100


def test_install_reports_a_failed_link(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def refuse(source: object, target: object) -> None:
        raise OSError("symlinks are not allowed")

    monkeypatch.setattr(n8n_gen.sys, "platform", "linux")
    monkeypatch.setattr(n8n_gen.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(n8n_gen.os, "chmod", lambda path, mode: None)
    monkeypatch.setattr(n8n_gen.os, "symlink", refuse)
    n8n_gen.install_script()
    assert "Failed to install script: symlinks are not allowed" in caplog.text


@pytest.mark.parametrize(
    ("argv", "called"),
    [
        (["split", "-i", "w.json", "-o", "src"], ("split_workflow", ("w.json", "src"))),
        (["build", "-i", "src", "-o", "w.json"], ("build_workflow", ("src", "w.json", None))),
        (["build", "-i", "src", "-o", "w.json", "-t", "t.json"], ("build_workflow", ("src", "w.json", "t.json"))),
        (["docs"], ("parse_docs", ())),
        (["install"], ("install_script", ())),
    ],
)
def test_main_dispatches_each_command(
    monkeypatch: pytest.MonkeyPatch, argv: list[str], called: tuple[str, tuple[object, ...]]
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []
    for name in ("split_workflow", "build_workflow", "parse_docs", "install_script"):
        monkeypatch.setattr(n8n_gen, name, lambda *args, _name=name: calls.append((_name, args)))
    monkeypatch.setattr(sys, "argv", ["n8n_gen.py", *argv])
    n8n_gen.main()
    assert calls == [called]


def test_main_without_a_command_prints_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["n8n_gen.py"])
    n8n_gen.main()
    assert "split" in capsys.readouterr().out


def test_split_requires_input_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["n8n_gen.py", "split"])
    with pytest.raises(SystemExit) as stopped:
        n8n_gen.main()
    assert stopped.value.code == 2
