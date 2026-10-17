const form = document.getElementById("audit-form");
const urlField = document.getElementById("url");
const submitButton = document.getElementById("submit");
const statusBox = document.getElementById("status");
const statusTitle = document.getElementById("status-title");
const statusMessage = document.getElementById("status-message");
const spinner = document.getElementById("spinner");
const results = document.getElementById("results");
let latestReport = null;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  })[c]);
}
function showStatus(title, message, loading) {
  statusBox.classList.remove("hidden");
  statusTitle.textContent = title;
  statusMessage.textContent = message;
  spinner.classList.toggle("done", !loading);
}
function setImage(id, base64) {
  const img = document.getElementById(id);
  if (base64) img.src = "data:image/jpeg;base64," + base64;
  else img.removeAttribute("src");
}
function priorityClass(value) {
  const v = String(value || "Low").toLowerCase();
  return ["high", "medium", "low"].includes(v) ? v : "low";
}
function renderOpportunity(item) {
  return `<article class="op-card">
    <div class="op-top"><span class="priority ${priorityClass(item.priority)}">${escapeHtml(item.priority || "Low")} priority</span><span class="effort">Effort: ${escapeHtml(item.effort || "Unknown")}</span></div>
    <h4>${escapeHtml(item.title)}</h4>
    <p>${escapeHtml(item.recommendation || "")}</p>
    <p class="evidence"><strong>Evidence:</strong> ${escapeHtml(item.evidence || "Not explicitly observed")}</p>
    <p><strong>Why it may help:</strong> ${escapeHtml(item.why_it_may_help || "")}</p>
    ${item.success_metric ? `<p class="metric"><strong>Measure:</strong> ${escapeHtml(item.success_metric)}</p>` : ""}
  </article>`;
}
function renderReport(report) {
  latestReport = report;
  results.classList.remove("hidden");
  document.getElementById("scanned-url").textContent = report.scanned_url || report.url;
  document.getElementById("summary-text").textContent = report.ai_summary || report.summary || "Audit complete.";
  const aiStatus = document.getElementById("ai-status");
  aiStatus.textContent = report.ai?.status
    ? `${report.ai.status}${report.ai.model ? " · Model: " + report.ai.model : ""}${report.ai.vision_used ? " · Screenshot vision used" : ""}`
    : "Rule-based audit only";
  aiStatus.classList.toggle("error", !report.ai?.used);
  setImage("desktop", report.screenshots?.desktop_jpeg_base64);
  setImage("mobile", report.screenshots?.mobile_jpeg_base64);

  const aiItems = report.ai_opportunities || [];
  const findings = aiItems.length ? aiItems : (report.findings || []);
  document.getElementById("opportunity-count").textContent = `${findings.length} recommendations`;
  document.getElementById("opportunities").innerHTML = findings.map(renderOpportunity).join("") ||
    `<p class="muted">No recommendations were returned. See the status above.</p>`;

  const features = report.suggested_features || [];
  document.getElementById("features").innerHTML = features.length ? features.map(f =>
    `<article class="feature"><h4>${escapeHtml(f.feature)}</h4><p>${escapeHtml(f.reason)}</p><small>Effort: ${escapeHtml(f.effort || "Unknown")}</small></article>`
  ).join("") : `<p class="muted">Gemma did not suggest additional features this time. Rule-based findings are shown above.</p>`;

  const questions = report.questions_for_owner || [];
  const qWrap = document.getElementById("questions-wrap");
  qWrap.classList.toggle("hidden", questions.length === 0);
  document.getElementById("questions").innerHTML = questions.map(q => `<li>${escapeHtml(q)}</li>`).join("");

  const warningList = report.page_signals?.warnings || [];
  const warnings = document.getElementById("warnings");
  const msgs = [...warningList];
  if (report.ai?.error) msgs.push(report.ai.error);
  warnings.classList.toggle("hidden", msgs.length === 0);
  warnings.textContent = msgs.join(" · ");
  results.scrollIntoView({behavior:"smooth", block:"start"});
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  results.classList.add("hidden");
  submitButton.disabled = true;
  submitButton.textContent = "Analyzing…";
  showStatus("Scanning website…", "Capturing screenshots and collecting page evidence. Gemma may take a little longer on the first request.", true);
  try {
    const response = await fetch("/api/audit", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        url: urlField.value.trim(),
        use_ai: document.getElementById("use-ai").checked,
        analyze_screenshots: document.getElementById("use-vision").checked
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    showStatus("Audit finished", "Review the evidence, recommendations, and suggested features below.", false);
    renderReport(data);
  } catch (err) {
    showStatus("Audit failed", err.message || "Unknown error. Check the backend terminal for details.", false);
  } finally {
    submitButton.disabled = false;
    submitButton.innerHTML = 'Audit website <span>→</span>';
  }
});

document.getElementById("download").addEventListener("click", () => {
  if (!latestReport) return;
  const safe = {...latestReport, screenshots: {
    note: "Screenshots are omitted from the export to keep the JSON file smaller."
  }};
  const blob = new Blob([JSON.stringify(safe, null, 2)], {type:"application/json"});
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = `growsight-audit-${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
});
