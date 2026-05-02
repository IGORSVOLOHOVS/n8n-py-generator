# n8n Python Workflow Generator

A powerful utility to split large n8n workflow JSON files into a manageable directory structure, rebuild them, and parse node documentation. This makes it easier to work with custom JavaScript/Python code and understand node parameters.

## Features

- **Split**: Decomposes an n8n `.json` file into separate folders for each node.
- **Code Extraction**: Automatically extracts `jsCode` and `pythonCode` into separate `.js` or `.py` files.
- **Build**: Reassembles the directory structure back into a valid n8n workflow JSON.
- **Docs**: Automatically parses and downloads documentation for both built-in and community n8n nodes.
- **Rich Output**: Beautiful console logging and progress bars.
- **Global Install**: Can be installed as a global command `n8n-gen`.

## Installation

1. Clone the repository and install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Install globally:
```bash
python3 n8n_gen.py install
```
After this, you can use `n8n-gen` from anywhere.

## Usage

### Splitting a Workflow
```bash
n8n-gen split --input path/to/workflow.json --output ./src
```

### Building a Workflow
```bash
n8n-gen build --input ./src --output workflow_generated.json
```

### Parsing Documentation
Fetches community nodes from npm and clones built-in nodes from the n8n GitHub repository:
```bash
n8n-gen docs
```
This generates a comprehensive `docs/n8n_docs.md` guide and saves node data in `docs/n8n_community/`.

## Development

The project uses:
- `rich`: For beautiful console output.
- `pandas`: For handling node data.
- `requests`: For API interactions.
- `python-dotenv`: For environment variable management.
