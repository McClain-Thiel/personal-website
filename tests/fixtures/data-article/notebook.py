# /// script
# [tool.blog]
# title = "Explore a bundled dataset"
# description = "A publishing test with local CSV and JSON data and an adjustable threshold."
# date = "2026-09-10"
# tags = ["Interactive notebooks"]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="normal")


@app.cell
def _():
    import csv
    import json
    import marimo as mo

    return csv, json, mo


@app.cell
def _(csv, json, mo):
    _directory = mo.notebook_dir()
    with (_directory / "data/results.csv").open() as _file:
        results = list(csv.DictReader(_file))
    settings = json.loads((_directory / "data/scoring rules.json").read_text())
    return results, settings


@app.cell
def _(mo, results, settings):
    mo.md(f"""
    ## Explore the results

    Loaded **{len(results)} samples** from the bundled CSV and the **{settings['label']}**
    label from JSON. Adjust the threshold to filter the same data in your browser.
    """)
    return


@app.cell
def _(mo):
    threshold = mo.ui.slider(0, 100, value=50, label="Minimum score (%)", show_value=True)
    threshold
    return (threshold,)


@app.cell
def _(mo, results, threshold):
    accepted = [row for row in results if float(row["score"]) * 100 >= threshold.value]
    mo.md(f"Accepted samples: **{len(accepted)}**")
    return


if __name__ == "__main__":
    app.run()
