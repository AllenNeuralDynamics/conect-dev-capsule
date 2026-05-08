"""Export a notebook as expanded, no-code HTML and, when possible, PDF.

Usage from the repository root:

    python code/export_notebook_no_code.py

The script bootstraps its export-only dependencies with uv when they are not
already installed. The default input is code/dynamic_routing_tutorial.ipynb.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


EXPORT_DEPENDENCIES = ("nbconvert", "playwright")


EXPANDED_EXPORT_CSS = r"""
<style id="expanded-no-code-export-css">
@page {
  size: Letter;
  margin: 0.55in;
}

html,
body,
.jp-Notebook,
.jp-Cell,
.jp-InputArea,
.jp-OutputArea,
.jp-OutputArea-child,
.jp-OutputArea-output,
.jp-RenderedText,
.jp-RenderedHTMLCommon,
.jp-CodeCell.jp-mod-outputsScrolled .jp-Cell-outputArea,
.jp-TrimmedOutputs,
.lm-Widget,
.lm-Panel,
.p-Widget,
.p-Panel {
  height: auto !important;
  max-height: none !important;
  overflow: visible !important;
}

body {
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}

.jp-Notebook {
  padding: 0 !important;
}

.jp-InputPrompt,
.jp-OutputPrompt,
.jp-OutputArea-prompt,
.jp-OutputArea-promptOverlay,
.jp-Collapser,
.jp-CellFooter,
.jp-CellHeader,
.jp-InputArea-editor,
.jp-InputArea-prompt,
.jp-CodeMirrorEditor,
.jp-Editor,
.jp-mod-outputsScrolled .jp-OutputArea-promptOverlay,
.jp-TrimmedOutputs > a,
.jp-CodeCell.jp-mod-outputsScrolled .jp-Cell-outputArea::after {
  display: none !important;
}

pre,
code,
.jp-OutputArea-output pre,
.jp-RenderedText pre,
.jp-RenderedHTMLCommon pre {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
  max-height: none !important;
  overflow: visible !important;
}

img,
svg,
canvas {
  max-width: 100% !important;
  height: auto !important;
  break-inside: avoid !important;
  page-break-inside: avoid !important;
}

table,
thead,
tbody,
tr,
th,
td {
  max-width: 100% !important;
  overflow: visible !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
}

.jp-RenderedHTMLCommon table {
  display: table !important;
  font-size: 8.5pt !important;
}
</style>
"""


FENCED_CODE_BLOCK = re.compile(
    r"(^|\n)[ \t]*(```|~~~)[^\n]*\n.*?(\n[ \t]*\2[ \t]*(?=\n|$)|$)",
    re.DOTALL,
)


def bootstrap_export_dependencies() -> None:
    missing = [
        dependency
        for dependency in EXPORT_DEPENDENCIES
        if importlib.util.find_spec(dependency) is None
    ]
    if not missing:
        return

    if os.environ.get("NOTEBOOK_EXPORT_BOOTSTRAPPED") == "1":
        missing_names = ", ".join(missing)
        raise SystemExit(f"Missing export dependencies after bootstrap: {missing_names}")

    uv = shutil.which("uv")
    if uv is None:
        missing_names = ", ".join(missing)
        script = Path(__file__).resolve()
        raise SystemExit(
            f"Missing export dependencies: {missing_names}\n"
            "Install uv or run this script in an environment with nbconvert and "
            f"playwright installed.\n\nSuggested command:\n"
            f"  uv run --with nbconvert --with playwright python {script}"
        )

    env = os.environ.copy()
    env["NOTEBOOK_EXPORT_BOOTSTRAPPED"] = "1"
    command = [
        uv,
        "run",
        "--with",
        "nbconvert",
        "--with",
        "playwright",
        "python",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(command, env=env))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a notebook copy and export expanded HTML plus optional PDF "
            "with code inputs hidden."
        )
    )
    parser.add_argument(
        "notebook",
        nargs="?",
        default=Path("code/dynamic_routing_tutorial.ipynb"),
        type=Path,
        help="Notebook to export. Defaults to code/dynamic_routing_tutorial.ipynb.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for exported files. Defaults to <notebook-dir>/exports.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Notebook execution timeout in seconds per cell. Defaults to 900.",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Export saved notebook outputs instead of executing a fresh copy.",
    )
    parser.add_argument(
        "--keep-markdown-code",
        action="store_true",
        help="Keep fenced code blocks that appear inside markdown cells.",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Only write the no-code HTML export.",
    )
    parser.add_argument(
        "--pdf-format",
        default="Letter",
        help="PDF paper format passed to Chromium. Defaults to Letter.",
    )
    return parser.parse_args()


def clear_folded_or_hidden_metadata(notebook) -> None:
    for cell in notebook.cells:
        cell.metadata.pop("collapsed", None)
        cell.metadata.pop("scrolled", None)
        jupyter_metadata = cell.metadata.get("jupyter")
        if isinstance(jupyter_metadata, dict):
            jupyter_metadata.pop("outputs_hidden", None)
            jupyter_metadata.pop("source_hidden", None)
        for output in cell.get("outputs", []):
            output_metadata = output.get("metadata")
            if isinstance(output_metadata, dict):
                output_metadata.pop("scrolled", None)
                output_metadata.pop("collapsed", None)


def remove_markdown_code_blocks(notebook) -> None:
    for cell in notebook.cells:
        if cell.cell_type != "markdown":
            continue
        source = "".join(cell.source) if isinstance(cell.source, list) else cell.source
        cell.source = FENCED_CODE_BLOCK.sub("\n", source).strip() + "\n"


def execute_notebook(notebook, notebook_path: Path, timeout: int):
    from nbconvert.preprocessors import ExecutePreprocessor

    processor = ExecutePreprocessor(timeout=timeout)
    resources = {"metadata": {"path": str(notebook_path.parent.resolve())}}
    processor.preprocess(notebook, resources=resources)
    return notebook


def inject_export_css(html: str) -> str:
    if "</head>" in html:
        return html.replace("</head>", f"{EXPANDED_EXPORT_CSS}</head>", 1)
    return f"{EXPANDED_EXPORT_CSS}\n{html}"


def export_html(notebook, html_path: Path) -> None:
    from nbconvert import HTMLExporter

    exporter = HTMLExporter()
    exporter.exclude_input = True
    exporter.exclude_input_prompt = True
    exporter.exclude_output_prompt = True
    body, _resources = exporter.from_notebook_node(notebook)
    html_path.write_text(inject_export_css(body), encoding="utf-8")


def find_browser_executable() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def export_pdf(html_path: Path, pdf_path: Path, pdf_format: str) -> bool:
    from playwright.sync_api import sync_playwright

    launch_options = {"headless": True, "args": ["--allow-file-access-from-files"]}
    browser_executable = find_browser_executable()
    if browser_executable:
        launch_options["executable_path"] = browser_executable

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page(
                viewport={"width": 1200, "height": 1600},
                device_scale_factor=1,
            )
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(pdf_path),
                format=pdf_format,
                print_background=True,
                margin={
                    "top": "0.55in",
                    "right": "0.55in",
                    "bottom": "0.55in",
                    "left": "0.55in",
                },
                prefer_css_page_size=True,
            )
            browser.close()
        return True
    except Exception as exc:  # noqa: BLE001 - PDF is optional; report and continue.
        print(f"PDF export skipped: {exc}", file=sys.stderr)
        return False


def main() -> int:
    bootstrap_export_dependencies()

    import nbformat

    args = parse_args()
    notebook_path = args.notebook.resolve()
    if not notebook_path.exists():
        print(f"Notebook not found: {notebook_path}", file=sys.stderr)
        return 2

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = notebook_path.stem
    executed_path = output_dir / f"{stem}_executed.ipynb"
    html_path = output_dir / f"{stem}_no_code.html"
    pdf_path = output_dir / f"{stem}_no_code_expanded.pdf"

    notebook = nbformat.read(notebook_path, as_version=4)
    clear_folded_or_hidden_metadata(notebook)
    if not args.keep_markdown_code:
        remove_markdown_code_blocks(notebook)

    if args.no_execute:
        print(f"Exporting saved outputs from {notebook_path}")
    else:
        print(f"Executing {notebook_path}")
        execute_notebook(notebook, notebook_path, timeout=args.timeout)

    nbformat.write(notebook, executed_path)
    print(f"Wrote executed notebook copy: {executed_path}")

    export_html(notebook, html_path)
    print(f"Wrote expanded no-code HTML: {html_path}")

    if args.skip_pdf:
        return 0

    if export_pdf(html_path, pdf_path, args.pdf_format):
        print(f"Wrote expanded no-code PDF: {pdf_path}")
    else:
        print("HTML export is ready even though PDF export was not available.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
