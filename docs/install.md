# Install

1. Install [uv](https://docs.astral.sh/uv/) and Python 3.13.
2. Clone this repository and run `uv sync --frozen` at its root. That installs `requests`, `python-dotenv`, `rich` and `pandas` at the versions `uv.lock` pins.
3. For `docs`, Git must be on PATH and the machine must reach `registry.npmjs.org` and `github.com`. `split` and `build` need neither.

Check the result with `.\recipe.ps1 run --help`: it lists the four commands.

To call the tool as `n8n-gen` from any folder, run `.\recipe.ps1 run install`. On Windows it writes `n8n-gen.bat` to `%LOCALAPPDATA%\Microsoft\WindowsApps`, which runs this checkout's `n8n_gen.py` with the `python` on PATH, so that Python needs the same four packages. It warns when the folder is not on PATH.

`.\recipe.ps1 build` packs the module into a wheel in `dist\`. The wheel installs an `n8n-gen` command.

A `.env` file at the working folder is read on start through `python-dotenv`. The tool itself reads no variable from it; it is gitignored.
