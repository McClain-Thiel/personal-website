const source = document.querySelector("#notebook-runtime");
const start = document.querySelector("#notebook-start");
const status = document.querySelector("#notebook-status");
const notebook = JSON.parse(source.textContent);

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
