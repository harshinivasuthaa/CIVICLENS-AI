// Main JavaScript for CivicLens AI
document.addEventListener("DOMContentLoaded", () => {
  // Helper to fetch CSRF token from meta header
  const getCsrfToken = () => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  };

  // Real-time Category Suggestion on Complaint Submission
  const titleInput = document.getElementById("complaint-title");
  const descInput = document.getElementById("complaint-description");
  const aiBadge = document.getElementById("ai-category-suggestion");
  const catSelect = document.getElementById("category_id");

  let debounceTimer = null;

  const triggerAiSuggestion = () => {
    const text = `${titleInput?.value || ""} ${descInput?.value || ""}`.trim();
    if (text.length < 8 || !aiBadge) return;

    aiBadge.innerHTML = `<span class="spinner-border spinner-border-sm text-primary me-1"></span><small class="text-muted">Analyzing complaint text with NLP...</small>`;

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      try {
        const response = await fetch("/api/ai/predict-category", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify({ text }),
        });
        if (response.ok) {
          const data = await response.json();
          const confPct = Math.round(data.confidence * 100);
          const badgeClass = data.is_low_confidence ? "bg-warning text-dark" : "bg-success text-white";

          aiBadge.innerHTML = `
            <div class="alert alert-light border p-2 mt-2 d-flex align-items-center justify-content-between">
              <div>
                <strong>AI Recommendation:</strong>
                <span class="badge ${badgeClass} ms-1">${data.predicted_category}</span>
                <small class="text-muted ms-2">(Confidence: ${confPct}%)</small>
                ${data.is_low_confidence ? '<small class="text-danger ms-1">• Low confidence (officer review recommended)</small>' : ''}
              </div>
              <button type="button" class="btn btn-sm btn-outline-primary" id="apply-ai-cat">Apply Suggestion</button>
            </div>
          `;

          document.getElementById("apply-ai-cat")?.addEventListener("click", () => {
            if (catSelect) {
              for (let option of catSelect.options) {
                if (option.text.toLowerCase().includes(data.predicted_category.toLowerCase())) {
                  catSelect.value = option.value;
                  break;
                }
              }
            }
          });
        }
      } catch (err) {
        console.warn("AI categorization endpoint unavailable:", err);
      }
    }, 400);
  };

  if (titleInput && descInput) {
    titleInput.addEventListener("input", triggerAiSuggestion);
    descInput.addEventListener("input", triggerAiSuggestion);
  }
});
