// Local Factory inspection harness: three simulated companies, five roles and four gates.
// Only run identifiers are remembered locally. The server checks ownership and exact hashes.
// All proposal content is rendered as text; it must never become HTML or executable code.
"use strict";
const byId = id => document.getElementById(id);
let state = null;
let busy = false;
let configured = false;
const company = () => byId("factory-company").value;
const savedKey = () => `secloudis-factory-${company()}`;
function savedRun() { try { return localStorage.getItem(savedKey()); } catch { return null; } }
function notice(message, error = false) {
  const node = byId("factory-notice"); node.textContent = message;
  node.classList.toggle("error", error); node.hidden = !message;
}
// These controls improve review usability; backend validation remains authoritative.
function controls() {
  byId("factory-company").disabled = busy || !configured;
  byId("factory-start").disabled = busy || !configured;
  byId("factory-restore").disabled = busy || !configured || !savedRun();
  const ready = !!state?.pending_gate && byId("factory-reviewed").checked && byId("factory-reason").value.trim().length > 0;
  byId("factory-approve").disabled = busy || !ready;
  byId("factory-reject").disabled = busy || !ready;
}
// The fixture header is accepted only by the server's explicit loopback-only local mode.
async function api(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {
    "X-Demo-User": company(), ...(body ? {"Content-Type": "application/json"} : {})
  }, ...(body ? {body: JSON.stringify(body)} : {})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail || "The operation did not complete.");
  return result;
}
const label = value => String(value).replaceAll("_", " ");
// Construct DOM text nodes recursively so model-like proposals remain inert data.
function showValue(value, depth = 0) {
  if (value === null || typeof value !== "object") {
    const span = document.createElement("span"); span.textContent = value === null ? "Not recorded" : String(value); return span;
  }
  if (depth > 5) { const pre = document.createElement("pre"); pre.textContent = JSON.stringify(value, null, 2); return pre; }
  if (Array.isArray(value)) {
    const list = document.createElement("ul");
    for (const item of value) { const li = document.createElement("li"); li.append(showValue(item, depth + 1)); list.append(li); }
    return list;
  }
  const list = document.createElement("dl");
  for (const [key, item] of Object.entries(value)) {
    const term = document.createElement("dt"); term.textContent = label(key);
    const description = document.createElement("dd"); description.append(showValue(item, depth + 1));
    list.append(term, description);
  }
  return list;
}
// Every new snapshot clears the review acknowledgement; a prior click approves nothing new.
function render() {
  const pending = state?.pending_gate;
  const decisions = state?.decisions || [];
  byId("factory-status").textContent = state ? label(state.status) : "Ready";
  byId("factory-meta").textContent = state ? `Run ${state.run_id} · ${label(state.company_id)} · ${state.project_id}` : "Start a workflow, or resume the last run saved for this company.";
  for (const item of document.querySelectorAll("[data-gate]")) {
    const decision = decisions.find(d => d.gate === item.dataset.gate);
    const active = pending?.gate === item.dataset.gate;
    item.classList.toggle("complete", decision?.decision === "approve");
    item.classList.toggle("rejected", decision?.decision === "reject");
    item.classList.toggle("pending", active);
    item.querySelector(".stage-state").textContent = active ? "Your decision" : decision ? (decision.decision === "approve" ? "Approved" : "Rejected") : "Not reached";
  }
  byId("factory-review").hidden = !pending;
  byId("factory-history").hidden = !state;
  byId("factory-reviewed").checked = false;
  byId("factory-reason").value = "";
  if (pending) {
    byId("factory-review-title").textContent = `${pending.gate} ${pending.label.replace(/^G[1-4]\s*/, "")}: your decision`;
    byId("factory-artifact").replaceChildren(showValue(pending.artifact));
    byId("factory-json").textContent = JSON.stringify(pending.artifact, null, 2);
    byId("factory-hash").textContent = pending.artifact_hash;
  }
  byId("factory-artifacts").replaceChildren();
  for (const [name, artifact] of Object.entries(state?.artifacts || {})) {
    const detail = document.createElement("details");
    const summary = document.createElement("summary"); summary.textContent = label(name);
    const content = document.createElement("div"); content.className = "artifact-fields";
    content.append(showValue(artifact)); detail.append(summary, content); byId("factory-artifacts").append(detail);
  }
  byId("factory-decisions").textContent = JSON.stringify(decisions, null, 2);
  byId("factory-events").textContent = JSON.stringify(state?.events || [], null, 2);
  controls();
}
// Serialize browser actions and restore controls on success or failure.
async function operation(work) {
  if (busy) return;
  busy = true; notice(""); controls();
  try { await work(); } catch (error) { notice(error.message || "Operation failed. Resume the saved run before retrying.", true); }
  finally { busy = false; controls(); }
}
function acceptState(result) {
  state = result;
  try { localStorage.setItem(savedKey(), state.run_id); } catch { /* Persistence on the server still works. */ }
  render();
  if (state.status === "release_ready") notice("All four gates passed in the simulation. No application was generated, executed or deployed. Inspect the retained proposals below.");
  if (state.status === "rejected") notice("This run stopped after your rejection. Its artifacts and decision remain available. Start a new run to propose a changed version.");
}
byId("factory-form").addEventListener("submit", event => {
  event.preventDefault();
  operation(async () => acceptState(await api("/api/factory/runs", {
    request_text: byId("factory-request").value, synthetic: byId("factory-synthetic").checked
  })));
});
byId("factory-decision-form").addEventListener("submit", event => {
  event.preventDefault();
  const pending = state?.pending_gate;
  const decision = event.submitter?.value;
  if (!pending || !["approve", "reject"].includes(decision)) return;
  const runId = state.run_id;
  // Bind this deliberate button action to the gate and exact artifact currently displayed.
  const body = {gate: pending.gate, artifact_hash: pending.artifact_hash, decision, reason: byId("factory-reason").value.trim()};
  operation(async () => acceptState(await api(`/api/factory/runs/${encodeURIComponent(runId)}/decision`, body)));
});
byId("factory-restore").addEventListener("click", () => operation(async () => {
  const id = savedRun(); if (id) acceptState(await api(`/api/factory/runs/${encodeURIComponent(id)}`));
}));
byId("factory-company").addEventListener("change", () => { state = null; notice(""); render(); });
byId("factory-reviewed").addEventListener("change", controls);
byId("factory-reason").addEventListener("input", controls);
operation(async () => {
  const configuration = await api("/api/factory/config");
  for (const identity of configuration.identities) {
    const option = document.createElement("option"); option.value = identity.id; option.textContent = identity.label;
    byId("factory-company").append(option);
  }
  configured = configuration.simulated === true; render();
});
