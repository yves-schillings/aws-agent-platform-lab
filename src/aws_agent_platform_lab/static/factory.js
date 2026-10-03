// Factory browser client.  Local mode sends an explicit fixture identity; an
// enabled AWS deployment exchanges Cognito PKCE credentials and sends only an
// in-memory Bearer token.  Server-side scope and approval checks remain authoritative.
"use strict";
const byId = id => document.getElementById(id);
let state = null;
let busy = false;
let configured = false;
let configuration = null;
let authConfiguration = null;
let token = null;
let principal = null;
const company = () => configuration?.simulated ? byId("factory-company").value : (principal?.subject || "signed-in-user");
const savedKey = () => `secloudis-factory-${company()}`;
function savedRun() { try { return localStorage.getItem(savedKey()); } catch { return null; } }
function notice(message, error = false) {
  const node = byId("factory-notice"); node.textContent = message;
  node.classList.toggle("error", error); node.hidden = !message;
}
function controls() {
  byId("factory-company").disabled = busy || !configured || !configuration?.simulated;
  byId("factory-start").disabled = busy || !configured;
  byId("factory-restore").disabled = busy || !configured || !savedRun();
  byId("factory-open").disabled = busy || !configured;
  const ready = !!state?.pending_gate && byId("factory-reviewed").checked && byId("factory-reason").value.trim().length > 0;
  byId("factory-approve").disabled = busy || !ready;
  byId("factory-reject").disabled = busy || !ready;
}
async function api(path, body) {
  const headers = body ? {"Content-Type": "application/json"} : {};
  if (configuration?.simulated) headers["X-Demo-User"] = company();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, {method: body ? "POST" : "GET", headers,
    credentials: "omit", cache: "no-store", ...(body ? {body: JSON.stringify(body)} : {})});
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !configuration?.simulated) { token = null; principal = null; configured = false; updateIdentity(); }
    throw new Error(result.detail || "The operation did not complete.");
  }
  return result;
}
const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function signIn() {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(48)));
  const oauthState = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem("factory.oauth", JSON.stringify({verifier, state: oauthState, created: Date.now()}));
  const url = new URL(authConfiguration.authorization_endpoint);
  url.search = new URLSearchParams({response_type: "code", client_id: authConfiguration.client_id,
    redirect_uri: authConfiguration.redirect_uri, scope: authConfiguration.scopes.join(" "), state: oauthState,
    code_challenge_method: "S256", code_challenge: base64url(new Uint8Array(digest))}).toString();
  location.assign(url.toString());
}
async function processCallback(params) {
  if (!params.has("code") && !params.has("error")) return;
  const stored = sessionStorage.getItem("factory.oauth"); sessionStorage.removeItem("factory.oauth");
  let pending; try { pending = JSON.parse(stored); } catch { pending = null; }
  if (!pending || !params.get("state") || params.get("state") !== pending.state || !Number.isFinite(pending.created)
      || Date.now() - pending.created > 600000 || Date.now() < pending.created) {
    throw new Error("The sign-in state is missing or expired. Start sign-in again.");
  }
  if (params.has("error")) throw new Error("Cognito sign-in did not complete. Please try again.");
  const response = await fetch("/auth/token", {method: "POST", headers: {"Content-Type":"application/json"},
    credentials:"omit", cache:"no-store", body: JSON.stringify({code: params.get("code"), code_verifier: pending.verifier})});
  const result = await response.json();
  if (!response.ok || typeof result.access_token !== "string") throw new Error(result.detail || "Cognito token exchange failed.");
  token = result.access_token;
}
function updateIdentity() {
  if (configuration?.simulated) {
    byId("factory-identity").textContent = "Simulated local identity. The server checks run ownership on every request.";
    return;
  }
  byId("factory-identity").textContent = principal
    ? `Signed in: ${principal.subject} · workspace ${principal.tenant} · ${principal.access_level} sources.`
    : "Sign in with Cognito to start or resume a Factory run.";
}
async function identify() {
  principal = await api("/api/me"); configured = true; updateIdentity(); controls();
  byId("factory-sign-in").hidden = true; byId("factory-sign-out").hidden = false;
}
const label = value => String(value).replaceAll("_", " ");
function showValue(value, depth = 0) {
  if (value === null || typeof value !== "object") { const span = document.createElement("span"); span.textContent = value === null ? "Not recorded" : String(value); return span; }
  if (depth > 5) { const pre = document.createElement("pre"); pre.textContent = JSON.stringify(value, null, 2); return pre; }
  if (Array.isArray(value)) { const list = document.createElement("ul"); for (const item of value) { const li = document.createElement("li"); li.append(showValue(item, depth + 1)); list.append(li); } return list; }
  const list = document.createElement("dl");
  for (const [key, item] of Object.entries(value)) { const term = document.createElement("dt"); term.textContent = label(key); const description = document.createElement("dd"); description.append(showValue(item, depth + 1)); list.append(term, description); }
  return list;
}
function render() {
  const pending = state?.pending_gate, decisions = state?.decisions || [];
  byId("factory-status").textContent = state ? label(state.status) : "Ready";
  byId("factory-meta").textContent = state ? `Run ${state.run_id} · ${label(state.company_id)} · ${state.project_id}` : "Start a workflow, or resume the last run saved for this identity.";
  for (const item of document.querySelectorAll("[data-gate]")) {
    const decision = decisions.find(d => d.gate === item.dataset.gate), active = pending?.gate === item.dataset.gate;
    item.classList.toggle("complete", decision?.decision === "approve"); item.classList.toggle("rejected", decision?.decision === "reject"); item.classList.toggle("pending", active);
    item.querySelector(".stage-state").textContent = active ? "Decision required" : decision ? (decision.decision === "approve" ? "Approved" : "Rejected") : "Not reached";
  }
  byId("factory-review").hidden = !pending; byId("factory-history").hidden = !state;
  byId("factory-reviewed").checked = false; byId("factory-reason").value = "";
  if (pending) { byId("factory-review-title").textContent = `${pending.gate} ${pending.label.replace(/^G[1-4]\s*/, "")}: decision required`; byId("factory-artifact").replaceChildren(showValue(pending.artifact)); byId("factory-json").textContent = JSON.stringify(pending.artifact, null, 2); byId("factory-hash").textContent = pending.artifact_hash; }
  byId("factory-artifacts").replaceChildren();
  for (const [name, artifact] of Object.entries(state?.artifacts || {})) { const detail = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = label(name); const content = document.createElement("div"); content.className = "artifact-fields"; content.append(showValue(artifact)); detail.append(summary, content); byId("factory-artifacts").append(detail); }
  byId("factory-decisions").textContent = JSON.stringify(decisions, null, 2); byId("factory-events").textContent = JSON.stringify(state?.events || [], null, 2); controls();
}
async function operation(work) { if (busy) return; busy = true; notice(""); controls(); try { await work(); } catch (error) { notice(error.message || "Operation failed. Resume the saved run before retrying.", true); } finally { busy = false; controls(); } }
function acceptState(result) { state = result; try { localStorage.setItem(savedKey(), state.run_id); } catch {} render(); if (state.status === "release_ready") notice("All four gates passed. The Factory records release readiness; it does not deploy an application."); if (state.status === "rejected") notice("This run stopped after rejection. Its artifacts and decision remain available."); }
byId("factory-form").addEventListener("submit", event => { event.preventDefault(); operation(async () => acceptState(await api("/api/factory/runs", {request_text: byId("factory-request").value, synthetic: byId("factory-synthetic").checked}))); });
byId("factory-decision-form").addEventListener("submit", event => { event.preventDefault(); const pending = state?.pending_gate, decision = event.submitter?.value; if (!pending || !["approve", "reject"].includes(decision)) return; operation(async () => acceptState(await api(`/api/factory/runs/${encodeURIComponent(state.run_id)}/decision`, {gate: pending.gate, artifact_hash: pending.artifact_hash, decision, reason: byId("factory-reason").value.trim()}))); });
byId("factory-restore").addEventListener("click", () => operation(async () => { const id = savedRun(); if (id) acceptState(await api(`/api/factory/runs/${encodeURIComponent(id)}`)); }));
byId("factory-open-form").addEventListener("submit", event => {
  event.preventDefault();
  operation(async () => {
    const id = byId("factory-run-id").value.trim();
    if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("Enter the 32-character run ID supplied by the requester.");
    acceptState(await api(`/api/factory/runs/${encodeURIComponent(id)}`));
  });
});
byId("factory-company").addEventListener("change", () => { state = null; notice(""); render(); }); byId("factory-reviewed").addEventListener("change", controls); byId("factory-reason").addEventListener("input", controls);
byId("factory-sign-in").addEventListener("click", () => signIn().catch(error => notice(error.message, true)));
byId("factory-sign-out").addEventListener("click", () => { token = null; principal = null; configured = false; state = null; render(); updateIdentity(); byId("factory-sign-in").hidden = false; byId("factory-sign-out").hidden = true; const url = new URL(authConfiguration.logout_endpoint); url.search = new URLSearchParams({client_id: authConfiguration.client_id, logout_uri: authConfiguration.logout_uri}); location.assign(url.toString()); });
operation(async () => {
  configuration = await api("/api/factory/config");
  if (configuration.simulated) {
    for (const identity of configuration.identities) { const option = document.createElement("option"); option.value = identity.id; option.textContent = identity.label; byId("factory-company").append(option); }
    configured = true; byId("factory-mode").textContent = "Local simulation · fixture responses"; byId("factory-mode").classList.add("offline"); byId("factory-description").textContent = "Local mode uses simulated identities and deterministic fixture responses. It does not call a remote model or deploy to AWS."; updateIdentity(); render(); return;
  }
  byId("factory-company-label").hidden = true; authConfiguration = await api("/auth/config");
  byId("factory-mode").textContent = "AWS mode · Cognito sign-in"; byId("factory-description").textContent = "AWS mode derives identity and source scope from Cognito. It stores workflow checkpoints and run ownership in shared DynamoDB tables so either healthy application task can resume a run.";
  const callback = new URLSearchParams(location.search); if (location.search) history.replaceState({}, "", location.pathname); await processCallback(callback); if (token) await identify(); else { updateIdentity(); byId("factory-sign-in").hidden = false; }
  render();
});
