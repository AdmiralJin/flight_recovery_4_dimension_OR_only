function updateGuidance() {
  const summary = document.querySelector("#solve-readiness-summary");
  const guidance = document.querySelector("#solve-guidance");
  if (!summary || !guidance) return;
  const text = summary.textContent.trim();
  guidance.classList.remove("is-ready", "is-warning");
  if (text === "READY") {
    guidance.classList.add("is-ready");
    guidance.textContent = "Solve input is READY. You may Validate / inspect the case, then click Solve. Inputs will be locked while solving.";
    return;
  }
  if (text.startsWith("NOT READY")) {
    guidance.classList.add("is-warning");
    guidance.textContent = `${text}. This case can still be inspected and validated. To solve, load a solve-ready Example or import a complete Solve Bundle.`;
    return;
  }
  guidance.textContent = "Checking whether the current case has all required solve inputs…";
}

const readinessSummary = document.querySelector("#solve-readiness-summary");
if (readinessSummary) {
  new MutationObserver(updateGuidance).observe(readinessSummary, {
    childList: true,
    characterData: true,
    subtree: true,
  });
  updateGuidance();
}

const helpDialog = document.querySelector("#workflow-help");
document.querySelector("#workflow-help-open")?.addEventListener("click", () => {
  if (helpDialog?.showModal) helpDialog.showModal();
});
