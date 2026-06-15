#!/usr/bin/env python3
"""
Convert .py scripts with # %% cell markers to .ipynb notebooks.
Usage: python convert_to_notebooks.py
"""
import os, re, json
import nbformat as nbf

NOTEBOOKS_DIR = os.path.dirname(os.path.abspath(__file__))

def py_to_notebook(py_path):
    with open(py_path) as f:
        content = f.read()

    # Parse cells: split on # %% or # %% [markdown]
    lines = content.split("\n")
    cells = []
    current_cell_type = "code"
    current_source = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^# %%\s*\[markdown\]\s*", line):
            if current_source:
                cells.append((current_cell_type, "\n".join(current_source)))
            current_cell_type = "markdown"
            current_source = []
        elif re.match(r"^# %%\s*", line):
            if current_source:
                cells.append((current_cell_type, "\n".join(current_source)))
            current_cell_type = "code"
            current_source = []
        else:
            # Skip cell-separator-only files
            if current_cell_type == "markdown" and line.startswith("# "):
                current_source.append(line[2:] if line.startswith("# ") else line)
            else:
                current_source.append(line)
        i += 1
    if current_source:
        cells.append((current_cell_type, "\n".join(current_source)))

    # Build notebook
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "name": "python",
            "version": "3.11.0"
        }
    }

    for cell_type, source in cells:
        source = source.strip()
        if not source:
            continue
        if cell_type == "markdown":
            cell = nbf.v4.new_markdown_cell(source)
        else:
            cell = nbf.v4.new_code_cell(source)
        nb.cells.append(cell)

    return nb


def main():
    os.makedirs(os.path.join(NOTEBOOKS_DIR, "data"), exist_ok=True)

    for fname in sorted(os.listdir(NOTEBOOKS_DIR)):
        if not fname.endswith(".py") or fname.startswith("convert") or fname == "__init__.py":
            continue
        py_path = os.path.join(NOTEBOOKS_DIR, fname)
        ipynb_path = py_path.replace(".py", ".ipynb")

        print(f"Converting {fname} → {os.path.basename(ipynb_path)}")
        nb = py_to_notebook(py_path)
        with open(ipynb_path, "w") as f:
            json.dump(nb, f, indent=1)

    print("\nDone! Created notebooks in notebooks/")


if __name__ == "__main__":
    main()
