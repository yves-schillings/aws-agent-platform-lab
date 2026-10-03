// Both clients share one registered Cognito callback. Return to the client
// whose pending state matches; it alone validates PKCE and exchanges the code.
// Only fixed same-origin destinations are allowed. Never persist the code.
"use strict";
(() => {
  const params = new URLSearchParams(location.search);
  const state = params.get("state");
  function matches(key) {
    try {
      const pending = JSON.parse(sessionStorage.getItem(key));
      return !!state && pending?.state === state && Number.isFinite(pending.created)
        && Date.now() >= pending.created && Date.now() - pending.created <= 600000;
    } catch { return false; }
  }
  const destination = matches("factory.oauth") ? "/factory"
    : matches("lab.oauth") ? "/demo" : "/factory";
  // Remove parameters from this history entry before navigating to the client.
  history.replaceState({}, "", location.pathname);
  location.replace(destination + (params.size ? "?" + params.toString() : ""));
})();
