#!/usr/bin/env python3
import json
import os
import argparse
import shutil
import time
import logging
import requests
import pandas as pd
import subprocess
import sys
import stat
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.logging import RichHandler

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Rich Initialization
console = Console()
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, console=console, markup=True)]
)
log = logging.getLogger("rich")

def split_workflow(input_file, output_dir):
    """Splits an n8n workflow JSON into a directory structure."""
    log.info(f"Splitting workflow [bold cyan]{input_file}[/bold cyan] into [bold cyan]{output_dir}[/bold cyan]...")
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            workflow = json.load(f)

        output_path = Path(output_dir)
        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # 1. Extract Nodes
        nodes_path = output_path / "nodes"
        nodes_path.mkdir(exist_ok=True)

        nodes = workflow.get("nodes", [])
        for node in nodes:
            node_name = node.get("name", "Unnamed_Node").replace("/", "_").replace("\\", "_")
            node_dir = nodes_path / node_name
            node_dir.mkdir(exist_ok=True)

            # Extract code if present
            params = node.get("parameters", {})
            
            # JS Code
            if "jsCode" in params:
                code = params.pop("jsCode")
                with open(node_dir / "code.js", "w", encoding="utf-8") as f:
                    f.write(code)
            
            # Python Code
            if "pythonCode" in params:
                code = params.pop("pythonCode")
                with open(node_dir / "code.py", "w", encoding="utf-8") as f:
                    f.write(code)

            # Save the rest of the node
            with open(node_dir / "node.json", "w", encoding="utf-8") as f:
                json.dump(node, f, indent=2, ensure_ascii=False)

        # 2. Extract Connections
        connections = workflow.get("connections", {})
        with open(output_path / "connections.json", "w", encoding="utf-8") as f:
            json.dump(connections, f, indent=2, ensure_ascii=False)

        # 3. Extract Metadata/Settings
        meta = {k: v for k, v in workflow.items() if k not in ["nodes", "connections"]}
        with open(output_path / "workflow_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        log.info(f"[bold green]Successfully split workflow into {output_dir}[/bold green]")
    except Exception as e:
        log.error(f"Failed to split workflow: {e}")

def assemble_workflow_dict(input_dir):
    """Reconstructs the workflow dictionary from the directory structure."""
    input_path = Path(input_dir)
    
    # 1. Load Metadata
    with open(input_path / "workflow_meta.json", "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # 2. Load Connections
    with open(input_path / "connections.json", "r", encoding="utf-8") as f:
        workflow["connections"] = json.load(f)

    # 3. Load Nodes
    nodes = []
    nodes_path = input_path / "nodes"
    
    for node_dir in sorted(nodes_path.iterdir()):
        if not node_dir.is_dir():
            continue
            
        with open(node_dir / "node.json", "r", encoding="utf-8") as f:
            node = json.load(f)
        
        # Inject JS Code
        js_file = node_dir / "code.js"
        if js_file.exists():
            with open(js_file, "r", encoding="utf-8") as f:
                node["parameters"]["jsCode"] = f.read()

        # Inject Python Code
        py_file = node_dir / "code.py"
        if py_file.exists():
            with open(py_file, "r", encoding="utf-8") as f:
                node["parameters"]["pythonCode"] = f.read()
        
        nodes.append(node)

    workflow["nodes"] = nodes
    return workflow

def build_workflow(input_dir, output_file):
    """Assembles an n8n workflow JSON from a directory structure."""
    log.info(f"Building workflow from [bold cyan]{input_dir}[/bold cyan] into [bold cyan]{output_file}[/bold cyan]...")
    try:
        workflow = assemble_workflow_dict(input_dir)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(workflow, f, indent=2, ensure_ascii=False)
        log.info(f"[bold green]Successfully built workflow into {output_file}[/bold green]")
    except Exception as e:
        log.error(f"Failed to build workflow: {e}")

def parse_docs():
    """Parses n8n documentation (logic from n8n_node_scraber.py)."""
    base_path = "docs/n8n_community"
    docs_n8n_path = "docs/n8n"
    docs_md_path = "docs/n8n_docs.md"
    
    os.makedirs(base_path, exist_ok=True)
    os.makedirs(docs_n8n_path, exist_ok=True)

    log.info("[bold blue]Starting n8n community nodes collection from npm...[/bold blue]")
    all_nodes = []
    size = 250
    offset = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("[cyan]Fetching data...", total=None)
            
            while True:
                url = f"https://registry.npmjs.org/-/v1/search?text=keywords:n8n-community-node-package&size={size}&from={offset}"
                response = requests.get(url)
                
                if response.status_code != 200:
                    log.error(f"Failed to fetch data: HTTP {response.status_code}")
                    break
                    
                try:
                    data = response.json()
                except Exception:
                    log.error("Failed to parse JSON response. Possible rate limit or API error.")
                    break
                
                if not data.get('objects'):
                    break
                    
                for item in data['objects']:
                    pkg = item['package']
                    all_nodes.append({
                        'name': pkg.get('name'),
                        'description': pkg.get('description'),
                        'version': pkg.get('version'),
                        'link': pkg.get('links', {}).get('npm')
                    })
                
                if progress.tasks[task_id].total is None:
                    progress.update(task_id, total=data['total'])
                
                progress.update(task_id, advance=len(data['objects']))
                
                offset += size
                if offset > data['total']:
                    break
                
                time.sleep(0.5)

        if all_nodes:
            log.info(f"Saving [green]{len(all_nodes)}[/green] nodes into CSV chunks...")
            for i in range(0, len(all_nodes), 250):
                chunk = all_nodes[i:i + 250]
                df = pd.DataFrame(chunk)
                file_num = (i // 250) + 1
                file_path = os.path.join(base_path, f"n8n_nodes_{file_num}.csv")
                df.to_csv(file_path, index=False)
            log.info(f"[bold green]Collection complete![/bold green] Files saved in [underline]{base_path}[/underline]")
        else:
            log.warning("No nodes collected.")

    except Exception as e:
        log.error(f"Error during community nodes collection: {e}")

    log.info("\n[bold blue]Starting download of built-in n8n nodes from GitHub...[/bold blue]")
    temp_dir = "n8n_temp"

    def cleanup_temp():
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                log.warning(f"Could not fully clean up {temp_dir}: {e}")

    cleanup_temp()
    git_command = (
        f"git clone --depth 1 --filter=blob:none --sparse https://github.com/n8n-io/n8n.git {temp_dir} && "
        f"cd {temp_dir} && "
        f"git sparse-checkout set packages/nodes-base/nodes && "
        f"cp -rf packages/nodes-base/nodes/* ../{docs_n8n_path}/"
    )

    try:
        with console.status("[bold green]Processing Git operations...") as status:
            subprocess.run(git_command, shell=True, check=True, capture_output=True)
        log.info(f"[bold green]Built-in nodes successfully updated in {docs_n8n_path}[/bold green]")
    except subprocess.CalledProcessError as e:
        log.error(f"Git operation failed: {e.stderr.decode() if e.stderr else e}")
    finally:
        cleanup_temp()

    log.info("\n[bold blue]Generating n8n_docs.md for AI Agent...[/bold blue]")
    docs_content = f"""# n8n Documentation Guide for AI Agent

This directory contains comprehensive documentation for both built-in and community n8n nodes.

## 1. Built-in Nodes (`{docs_n8n_path}/`)
The source code for all official n8n nodes is located here. Use this to understand node parameters, API endpoints, and logic.

### How to find fields and parameters (Google Sheets Example):
- **Version 2 Nodes (Modern)**: Look in `docs/n8n/<NodeName>/v2/actions/`.
    - `*.operation.ts`: Contains fields for specific operations (e.g., `append.operation.ts`).
    - `commonDescription.ts`: Contains shared fields like Spreadsheet ID or Sheet Name.
- **Version 1 Nodes**: Look directly in `docs/n8n/<NodeName>/<NodeName>.node.ts`.
- **Dynamic Options**: Check the `methods/` folder in the node directory to see how dropdown values are loaded.
- **API Calls**: Check the `transport/` folder to see the exact HTTP requests made to external services.

## 2. Community Nodes (`{base_path}/`)
A database of over 8000+ community nodes from npm, split into CSV chunks of 250 nodes each.

### How to use:
- Search through `n8n_nodes_*.csv` files to find nodes by name or description.
- Use the `link` column to find the npm package page for installation instructions.

## 3. General Tips for the AI Agent:
- When the user asks for "fields" of a node, prioritize looking into the `.operation.ts` files in the `v2/actions` subfolder.
- The `displayName` in the code matches what the user sees in the n8n UI.
- The `name` in the code is the internal key used in JSON workflows.
"""

    try:
        with open(docs_md_path, "w", encoding="utf-8") as f:
            f.write(docs_content)
        log.info(f"[bold green]Documentation guide generated at {docs_md_path}[/bold green]")
    except Exception as e:
        log.error(f"Failed to generate n8n_docs.md: {e}")

def install_script():
    """Installs the script globally by creating a symlink or shim."""
    log.info("Installing n8n-gen globally...")
    
    script_path = Path(__file__).resolve()
    is_windows = sys.platform == "win32"
    
    if is_windows:
        bin_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        shim_path = bin_dir / "n8n-gen.bat"
        
        try:
            bin_dir.mkdir(parents=True, exist_ok=True)
            with open(shim_path, "w", encoding="utf-8") as f:
                f.write(f'@echo off\npython "{script_path}" %*')
            log.info(f"[bold green]Successfully created shim at {shim_path}[/bold green]")
        except Exception as e:
            log.error(f"Failed to create Windows shim: {e}")
            return
    else:
        bin_dir = Path.home() / ".local" / "bin"
        link_path = bin_dir / "n8n-gen"
        
        try:
            # 1. Make script executable
            st = os.stat(script_path)
            os.chmod(script_path, st.st_mode | stat.S_IEXEC)
            
            # 2. Ensure bin dir exists
            bin_dir.mkdir(parents=True, exist_ok=True)
            
            # 3. Create symlink
            if link_path.exists() or link_path.is_symlink():
                log.warning(f"Removing existing link at {link_path}")
                link_path.unlink()
                
            os.symlink(script_path, link_path)
            log.info(f"[bold green]Successfully installed n8n-gen to {link_path}[/bold green]")
        except Exception as e:
            log.error(f"Failed to install script: {e}")
            return

    # Check if bin_dir is in PATH
    path_env = os.environ.get("PATH", "")
    if str(bin_dir).lower() not in path_env.lower():
        log.warning(f"[bold yellow]Warning: {bin_dir} is not in your PATH.[/bold yellow]")
        if is_windows:
            log.info(f"Please add {bin_dir} to your User PATH environment variable.")
        else:
            log.info(f"Add this to your shell profile (e.g., ~/.bashrc or ~/.zshrc):")
            log.info(f'export PATH="$PATH:{bin_dir}"')

def main():
    parser = argparse.ArgumentParser(description="n8n Workflow Generator/Splitter & Documentation Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Split command
    split_parser = subparsers.add_parser("split", help="Split JSON into directory structure")
    split_parser.add_argument("--input", "-i", required=True, help="Input workflow JSON file")
    split_parser.add_argument("--output", "-o", required=True, help="Output directory")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build JSON from directory structure")
    build_parser.add_argument("--input", "-i", required=True, help="Input directory")
    build_parser.add_argument("--output", "-o", required=True, help="Output workflow JSON file")

    # Docs command
    subparsers.add_parser("docs", help="Parse n8n documentation from npm and GitHub")

    # Install command
    subparsers.add_parser("install", help="Install n8n-gen globally (~/.local/bin/n8n-gen)")

    args = parser.parse_args()

    if args.command == "split":
        split_workflow(args.input, args.output)
    elif args.command == "build":
        build_workflow(args.input, args.output)
    elif args.command == "docs":
        parse_docs()
    elif args.command == "install":
        install_script()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
