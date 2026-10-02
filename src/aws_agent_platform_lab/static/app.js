// Baseline browser: authenticate, inspect permitted evidence and record an exact-artifact decision.
// UI state never supplies source permissions; those are derived and checked by the Python server.
'use strict';
// Access tokens stay in this closure. Only temporary OAuth state/verifier use sessionStorage.
(() => {
  const $ = id => document.getElementById(id);
  let config, token = null, principal = null, currentRun = null, currentHash = null, pollTimer;
  const activeStatuses = new Set(['queued', 'running']);
  function notice(message = '', error = false) {
    $('notice').textContent = message; $('notice').hidden = !message;
    $('notice').classList.toggle('error', error);
  }
  function textElement(tag, text, className) {
    const node = document.createElement(tag); node.textContent = text;
    if (className) node.className = className; return node;
  }
  // Keep credentials out of persistent storage and discard them after an authentication failure.
  async function api(path, options = {}) {
    const headers = {...(options.headers || {})};
    if (token) headers.Authorization = `Bearer ${token}`;
    if (config?.mode === 'offline') headers['X-Demo-User'] = $('demo-user').value;
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers, credentials: 'omit', cache: 'no-store'});
    const body = await response.json();
    if (!response.ok) {
      if (response.status === 401 && config?.mode !== 'offline') {
        token = null; principal = null; $('start-run').disabled = true;
        $('sign-in').hidden = false; $('sign-out').hidden = true;
      }
      throw new Error(typeof body.detail === 'string' ? body.detail : 'The operation could not be completed.');
    }
    return body;
  }
  const base64url = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  // Proof Key for Code Exchange and random state bind the login response to this browser session.
  async function signIn() {
    const verifier = base64url(crypto.getRandomValues(new Uint8Array(48)));
    const state = base64url(crypto.getRandomValues(new Uint8Array(32)));
    const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
    sessionStorage.setItem('lab.oauth', JSON.stringify({verifier, state, created: Date.now()}));
    const url = new URL(config.authorization_endpoint);
    url.search = new URLSearchParams({response_type: 'code', client_id: config.client_id,
      redirect_uri: config.redirect_uri, scope: config.scopes.join(' '), state,
      code_challenge_method: 'S256', code_challenge: challenge}).toString();
    location.assign(url.toString());
  }
  // Reject mismatched or expired login state before exchanging a one-time authorization code.
  async function processCallback(params) {
    if (!params.has('code') && !params.has('error')) return;
    const stored = sessionStorage.getItem('lab.oauth'); sessionStorage.removeItem('lab.oauth');
    let pending; try { pending = JSON.parse(stored); } catch { pending = null; }
    if (!pending || !params.get('state') || params.get('state') !== pending.state ||
        !Number.isFinite(pending.created) || Date.now() - pending.created > 600000 || Date.now() < pending.created) {
      throw new Error('The sign-in state is missing or expired. Start sign-in again.');
    }
    if (params.has('error')) throw new Error('Cognito sign-in did not complete. Please try again.');
    const result = await api('/auth/token', {method: 'POST', body: JSON.stringify({code: params.get('code'), code_verifier: pending.verifier})});
    token = result.access_token;
  }
  function resetRun() {
    clearTimeout(pollTimer); currentRun = null; currentHash = null;
    $('evidence').hidden = true; $('decision-panel').hidden = true; $('source-text').hidden = true;
    for (const id of ['sources', 'source-text', 'proposal', 'artifact', 'artifact-hash', 'trace-rows', 'tool-evidence', 'decision-record']) $(id).replaceChildren();
    $('tool-panel').hidden = true; $('decision-record').hidden = true;
    $('reviewed').checked = false; $('run-status').textContent = 'Ready';
    $('run-meta').textContent = 'Start a run to inspect its evidence.';
    for (const role of ['analyst', 'designer', 'reviewer']) {
      const node = $(`stage-${role}`); node.classList.remove('complete'); node.querySelector('.stage-state').textContent = 'Waiting';
    }
  }
  async function identify() {
    principal = await api('/api/me');
    $('identity').textContent = `${principal.simulated ? 'Simulated identity' : 'Signed in'}: ${principal.subject} · workspace ${principal.tenant} · ${principal.access_level} sources`;
    $('start-run').disabled = false; $('sign-in').hidden = true;
    $('sign-out').hidden = config.mode === 'offline';
  }
  // Display sources and model output using text nodes, never interpreted HTML.
  function renderRun(run) {
    $('evidence').hidden = false;
    const status = run.status || 'unknown'; $('run-status').textContent = status.replaceAll('_', ' ');
    $('start-run').disabled = !principal || activeStatuses.has(status);
    $('run-meta').textContent = `Run ${run.run_id} · ${run.mode || config.mode}${config.mode === 'offline' ? ' · Deterministic mock responses, no model call' : ''}`;
    const artifact = run.artifact || {}, trace = Array.isArray(run.trace) ? run.trace : [];
    for (const [role, key] of [['analyst','analysis'],['designer','design'],['reviewer','review']]) {
      const complete = Boolean(artifact[key]) || trace.some(event => event.role === role && event.outcome === 'validated');
      const node = $(`stage-${role}`); node.classList.toggle('complete', complete);
      node.querySelector('.stage-state').textContent = complete ? 'Recorded' : activeStatuses.has(status) ? 'In progress' : 'Waiting';
    }
    $('sources').replaceChildren();
    const sources = Array.isArray(run.sources) ? run.sources : artifact.retrieved_documents || [];
    for (const source of sources) {
      const id = source.id || source.source_id;
      const button = textElement('button', source.title || id || 'Source', 'source-button'); button.type = 'button';
      button.append(textElement('small', `Reference: ${id || 'unavailable'}${source.version ? ` · ${source.version}` : ''}`));
      button.disabled = !id;
      button.addEventListener('click', async () => {
        try {
          const doc = await api(`/api/runs/${encodeURIComponent(run.run_id)}/sources/${encodeURIComponent(id)}`);
          if (currentRun !== run.run_id) return;
          $('source-text').textContent = `${doc.title || id}\n\n${doc.text || doc.content || JSON.stringify(doc, null, 2)}`;
          $('source-text').hidden = false;
        } catch (error) { $('source-text').hidden = true; notice(error.message, true); }
      }); $('sources').append(button);
    }
    if (!sources.length) $('sources').append(textElement('p', 'Source evidence will appear when it is available.', 'caption'));
    const design = artifact.design || {}; $('proposal').replaceChildren();
    if (design.title) $('proposal').append(textElement('h3', design.title));
    if (artifact.analysis?.summary) $('proposal').append(textElement('p', artifact.analysis.summary));
    if (Array.isArray(design.steps)) {
      const list = document.createElement('ol');
      for (const step of design.steps) list.append(textElement('li', `${step.actor}: ${step.action}`));
      $('proposal').append(list);
    }
    if (!Object.keys(design).length) $('proposal').append(textElement('p', activeStatuses.has(status) ? 'The agents are preparing the result.' : 'No final proposal is available.'));
    $('artifact').textContent = JSON.stringify(artifact, null, 2);
    const tool = run.tool || artifact.tool;
    $('tool-panel').hidden = !tool;
    $('tool-evidence').textContent = tool ? JSON.stringify(tool, null, 2) : '';
    $('decision-record').hidden = !run.decision;
    if (run.decision) $('decision-record').textContent = `Decision: ${run.decision.action}. ${run.decision.identity_verified ? 'Verified Cognito identity' : 'Simulated local identity'} · Actor reference: ${run.decision.actor || 'unavailable'}`;
    if (currentHash !== run.artifact_hash) { $('reviewed').checked = false; $('approve').disabled = true; }
    currentHash = run.artifact_hash || null; $('artifact-hash').textContent = currentHash ? `SHA-256: ${currentHash}` : '';
    $('decision-panel').hidden = status !== 'waiting_approval';
    $('reject').disabled = false; $('approve').disabled = !$('reviewed').checked;
    $('trace-count').textContent = `${trace.length} events`; $('trace-rows').replaceChildren();
    for (const event of trace) {
      const row = document.createElement('tr');
      const duration = typeof event.latency_ms === 'number' ? `${event.latency_ms.toFixed(1)} ms` : '—';
      for (const value of [event.event || event.stage || 'event', event.role || event.stage || 'workflow', event.outcome || event.status || '—', duration,
                          `${event.input_tokens ?? 'unknown'} / ${event.output_tokens ?? 'unknown'}`]) row.append(textElement('td', String(value)));
      $('trace-rows').append(row);
    }
    if (run.error) notice(typeof run.error === 'string' ? run.error : 'The run failed. Inspect the safe trace.', true);
    if (status === 'approved') notice('This exact synthetic artifact has been approved and published to the configured results store.');
    if (status === 'rejected') notice('The proposal has been rejected. No publication was authorised.');
  }
  async function poll(runId) {
    try {
      const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
      if (currentRun !== runId) return;
      renderRun(run);
      if (activeStatuses.has(run.status)) pollTimer = setTimeout(() => poll(runId), 1200);
    } catch (error) { notice(error.message, true); $('start-run').disabled = !principal; }
  }
  async function decide(decision) {
    if (!currentRun || !currentHash || (decision === 'approve' && !$('reviewed').checked)) return;
    $('approve').disabled = true; $('reject').disabled = true;
    try {
      await api(`/api/runs/${encodeURIComponent(currentRun)}/decision`, {method: 'POST', body: JSON.stringify({artifact_hash: currentHash, decision})});
      await poll(currentRun);
    } catch (error) { notice(error.message, true); $('reject').disabled = false; $('approve').disabled = !$('reviewed').checked; }
  }
  $('run-form').addEventListener('submit', async event => {
    event.preventDefault(); if (!$('synthetic').checked || !principal) return;
    resetRun(); notice(); $('start-run').disabled = true;
    try {
      const result = await api('/api/runs', {method: 'POST', body: JSON.stringify({request_text: $('request-text').value,
        scenario_language: $('language').value, synthetic: true})});
      currentRun = result.run_id; await poll(currentRun);
    } catch (error) { notice(error.message, true); $('start-run').disabled = !principal; }
  });
  $('reviewed').addEventListener('change', () => { $('approve').disabled = !$('reviewed').checked; });
  $('approve').addEventListener('click', () => decide('approve'));
  $('reject').addEventListener('click', () => decide('reject'));
  $('sign-in').addEventListener('click', () => signIn().catch(error => notice(error.message, true)));
  $('sign-out').addEventListener('click', () => {
    token = null; principal = null; resetRun(); $('start-run').disabled = true;
    const url = new URL(config.logout_endpoint); url.search = new URLSearchParams({client_id: config.client_id, logout_uri: config.logout_uri});
    location.assign(url.toString());
  });
  $('demo-user').addEventListener('change', () => { resetRun(); notice(); identify().catch(error => notice(error.message, true)); });
  $('language').addEventListener('change', () => {
    $('request-text').value = $('language').value === 'nl'
      ? 'Maak een fictieve documentenchecklist. Benoem ontbrekende informatie, citeer toegestane brondocumenten en stel een workflow voor met onafhankelijke controle en een expliciete menselijke beslissing. Neem geen echte operationele beslissing.'
      : 'Prepare a fictional document checklist. Identify missing information, cite the permitted source documents, and propose a workflow with independent review and an explicit human decision. Do not make a real operational decision.';
  });
  (async () => {
    const callbackParams = new URLSearchParams(location.search);
    // Strip OAuth parameters before fetching any application configuration or resources.
    if (location.search) history.replaceState({}, '', location.pathname);
    config = await api('/auth/config');
    if (config.mode === 'offline') {
      $('mode').textContent = 'OFFLINE · Simulated models + identities'; $('mode').classList.add('offline');
      $('demo-choice').hidden = false; await identify();
    } else {
      $('mode').textContent = 'AWS mode · Cognito sign-in'; $('sign-in').hidden = false;
      await processCallback(callbackParams); if (token) await identify();
    }
  })().catch(error => { $('mode').textContent = 'Setup required'; $('mode').classList.add('blocked'); notice(error.message, true); });
})();
