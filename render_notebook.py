"""Execute one trusted article notebook in its own Python environment."""

import ast
import asyncio
import json
import os
from pathlib import Path
import sys

from marimo import MarimoIslandGenerator


async def render(
    path: Path, output: Path, dependencies: list[str], assets: list[dict[str, str]]
) -> None:
    os.chdir(path.parent)
    tree = ast.parse(path.read_text(), filename=str(path))
    # The pinned public islands exporter drops disabled-cell and setup configuration.
    # Reject these rather than publishing results from different code in the browser.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "app"
            and node.attr == "setup"
        ):
            raise ValueError(
                f"{path}: move setup code into a normal @app.cell before publishing"
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "cell"
                ):
                    if any(
                        keyword.arg == "disabled"
                        and not (
                            isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is False
                        )
                        for keyword in decorator.keywords
                    ):
                        raise ValueError(
                            f"{path}: remove disabled cells before publishing this notebook"
                        )
    generator = MarimoIslandGenerator.from_file(str(path), display_code=False)
    if not generator.stubs:
        raise ValueError(f"{path}: no marimo cells found")
    await generator.build()
    for index, stub in enumerate(generator.stubs, start=1):
        cell_output = stub.output
        if cell_output and (
            cell_output.channel == "marimo-error"
            or cell_output.mimetype == "application/vnd.marimo+error"
        ):
            raise ValueError(f"{path}: cell {index} failed: {cell_output.data}")
    runtime_source = path.read_text()
    if dependencies or assets:
        # marimo's WASM loader strips requirement versions. Gate every cell on an
        # explicit install so browser results honor the same pins as the build.
        ready = "site_notebook_environment_ready"
        if any(ready in stub.code for stub in generator.stubs):
            raise ValueError(f"{path}: {ready} is reserved by the publisher")
        codes = [f"{ready}\n{stub.code}" for stub in generator.stubs]
        bootstrap = f"""
import sys as _sys
import importlib.metadata as _metadata
from packaging.requirements import Requirement as _Requirement
import micropip as _micropip
import marimo as _mo

for _text in {dependencies!r}:
    _requirement = _Requirement(_text)
    if _requirement.marker and not _requirement.marker.evaluate():
        continue
    try:
        _version = _metadata.version(_requirement.name)
    except _metadata.PackageNotFoundError:
        continue
    if _version not in _requirement.specifier:
        _modules = _metadata.distribution(_requirement.name).read_text("top_level.txt")
        _names = _modules.splitlines() if _modules else [_requirement.name.replace("-", "_")]
        if any(_name in _sys.modules for _name in _names):
            raise RuntimeError(f"{{_text}} conflicts with a package already loaded by Pyodide ({{_version}}). Use a compatible requirement.")
await _micropip.install({dependencies!r}, reinstall=True)
""".strip()
        if assets:
            bootstrap += f"""

import hashlib as _hashlib
import os as _os
from js import location as _location
from pyodide.http import pyfetch as _pyfetch

_directory = _mo.notebook_dir()
if _directory is None:
    raise RuntimeError("Cannot determine the notebook data directory")
for _asset in {assets!r}:
    _url = str(_location.origin) + _asset["url"] + "?v=" + _asset["sha256"][:16]
    _response = await _pyfetch(_url)
    _response.raise_for_status()
    _content = await _response.bytes()
    if _hashlib.sha256(_content).hexdigest() != _asset["sha256"]:
        raise RuntimeError(f"Bundled file {{_asset['path']}} does not match this article. Reload the page.")
    _destination = _directory / _asset["path"]
    _destination.parent.mkdir(parents=True, exist_ok=True)
    _destination.write_bytes(_content)
_os.chdir(_directory)
"""
        bootstrap += f"""

{ready} = True
_mo.Html('<span data-notebook-ready hidden></span>')
"""
        generator.add_code(bootstrap)
        codes.append(bootstrap)
        # Preserve the metadata header for marimo's initial package discovery.
        header = "\n".join(
            line for line in path.read_text().splitlines() if line.startswith("#")
        )
        cells = [
            "@app.cell\nasync def __():\n"
            + "\n".join("    " + line for line in code.splitlines())
            + "\n    return"
            for code in codes
        ]
        runtime_source = (
            header + "\nimport marimo\napp = marimo.App()\n\n" + "\n\n".join(cells)
        )
    output.write_text(
        json.dumps(
            {
                "html": generator.render_body(include_init_island=False, style=""),
                "runtime_source": runtime_source,
                "wait_for_setup": bool(dependencies or assets),
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    request = json.loads(sys.argv[3])
    asyncio.run(
        render(
            Path(sys.argv[1]),
            Path(sys.argv[2]),
            request["dependencies"],
            request["assets"],
        )
    )
