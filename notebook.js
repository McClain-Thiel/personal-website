const source = document.querySelector("#notebook-runtime");
const start = document.querySelector("#notebook-start");
const status = document.querySelector("#notebook-status");
const notebook = JSON.parse(source.textContent);

async function renderSavedMath() {
  const elements = document.querySelectorAll("[data-notebook-math]");
  if (!elements.length) return;
  const { default: katex } = await import("https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.mjs");
  for (const element of elements) {
    katex.render(element.dataset.notebookMath, element, {
      displayMode: element.dataset.displayMath === "true",
      throwOnError: true,
      trust: false,
    });
  }
}

async function renderSavedDiagrams() {
  const elements = [...document.querySelectorAll("[data-notebook-diagram]")];
  if (!elements.length) return;
  const { default: mermaid } = await import("https://cdn.jsdelivr.net/npm/mermaid@11.12.3/dist/mermaid.esm.min.mjs");
  await document.fonts.ready;
  const render = async () => {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: document.documentElement.dataset.theme === "dark" ? "dark" : "default",
      fontFamily: getComputedStyle(document.body).fontFamily,
    });
    for (const [index, element] of elements.entries()) {
      if (!element.isConnected) continue;
      const { svg } = await mermaid.render(`saved-diagram-${index}`, element.dataset.notebookDiagram);
      element.innerHTML = svg;
    }
  };
  await render();
  let pending = Promise.resolve();
  new MutationObserver(() => {
    pending = pending.then(render).catch(reportDisplayError);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
}

function reportDisplayError(error) {
  console.error("Could not render saved notebook output:", error);
  status.textContent = "Some equations or diagrams could not load. Reload the page, or enable interactivity to retry.";
}

// Display libraries can render saved results without downloading or running Python.
void renderSavedMath().catch(reportDisplayError);
void renderSavedDiagrams().catch(reportDisplayError);

start.hidden = false;
start.addEventListener("click", async () => {
  start.disabled = true;
  status.textContent = "Loading interactive controls and article data. The first load can take a little while.";
  try {
    // marimo 0.24.2 reads the prepared notebook here, including its dependency gate.
    // Keep this together with the Python pin and verify it on runtime upgrades.
    window.__MARIMO_EXPORT_CONTEXT__ = {
      trusted: true,
      notebookCode: notebook.runtime_source,
    };
    const runtime = await import(source.dataset.runtime);
    let timeout;
    let setupObserver;
    try {
      await Promise.race([
        (async () => {
          await runtime.initialize();
          if (notebook.wait_for_setup && !document.querySelector("[data-notebook-ready]")) {
            await new Promise((resolve) => {
              setupObserver = new MutationObserver(() => {
                if (document.querySelector("[data-notebook-ready]")) {
                  setupObserver.disconnect();
                  resolve();
                }
              });
              setupObserver.observe(document.querySelector(".post-content"), {childList: true, subtree: true});
            });
          }
        })(),
        new Promise((_, reject) => {
          timeout = setTimeout(() => reject(new Error("Notebook initialization timed out")), 120000);
        }),
      ]);
    } finally {
      clearTimeout(timeout);
      setupObserver?.disconnect();
    }
    status.textContent = "Interactive controls are ready. Changes stay in your browser.";
    start.hidden = true;
  } catch (error) {
    console.error("Could not initialize this notebook:", error);
    status.textContent = "Interactive controls could not load. Reload the page to retry, or download the notebook. The saved article is still available below.";
    start.textContent = "Reload to retry";
    start.disabled = false;
    start.addEventListener("click", () => location.reload(), { once: true });
  }
}, { once: true });
