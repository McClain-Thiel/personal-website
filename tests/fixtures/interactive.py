# /// script
# dependencies = ["marimo==0.24.2", "humanize==4.12.3"]
# [tool.blog]
# title = "An interactive research note"
# description = "A publishing test: adjust a value and see the result change."
# date = "2026-09-10"
# tags = ["Interactive notebooks"]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="normal")


@app.cell
def _():
    import marimo as mo
    import humanize

    return mo, humanize


@app.cell
def _(mo):
    mo.md("""
    # An interactive research note

    ## A small experiment

    This is a test of the publishing pipeline. The explanation and saved results
    appear immediately; the control below recalculates the result in your browser.
    """)
    return


@app.cell
def _(mo):
    count = mo.ui.slider(1, 10, value=2, label="Sample count", show_value=True)
    count
    return (count,)


@app.cell
def _(count, mo):
    mo.md(f"The expected count is **{count.value * 2}**.")
    return


@app.cell
def _(mo):
    mo.md("""
    ## What this shows

    One notebook supplies the prose, the calculation, and the interactive control.
    The published article uses the same reading layout as an ordinary Markdown file.
    """)
    return


@app.cell
def _(mo, humanize):
    mo.md(f"Dependency version: **{humanize.__version__}**")
    return


if __name__ == "__main__":
    app.run()
