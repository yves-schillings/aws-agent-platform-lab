// Run with node --test tests/browser_callback.test.cjs. No browser or real tokens.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname,
  '../src/aws_agent_platform_lab/static/auth-callback.js'), 'utf8');
function route(storage, search = '?code=synthetic&state=expected') {
  let destination, cleaned;
  const now = Date.now();
  const context = {URLSearchParams, Date,
    location: {search, pathname: '/auth/callback', replace: value => {destination = value;}},
    history: {replaceState: (_, __, value) => {cleaned = value;}},
    sessionStorage: {getItem: key => storage(key, now)}};
  vm.runInNewContext(script, context);
  assert.equal(cleaned, '/auth/callback');
  return destination;
}
test('Factory initiated sign-in returns to the five-role client with state and code', () => {
  assert.equal(route((key, now) => key === 'factory.oauth'
    ? JSON.stringify({state: 'expected', created: now}) : null), '/factory?code=synthetic&state=expected');
});
test('baseline sign-in remains explicitly in the baseline client', () => {
  assert.equal(route((key, now) => key === 'lab.oauth'
    ? JSON.stringify({state: 'expected', created: now}) : null), '/demo?code=synthetic&state=expected');
});
test('malformed, expired, wrong or unavailable storage cannot choose a destination', () => {
  for (const storage of [() => '{', () => {throw new Error('unavailable');},
    (_, now) => JSON.stringify({state: 'expected', created: now - 600001}),
    (_, now) => JSON.stringify({state: 'wrong', created: now})]) {
    assert.equal(route(storage), '/factory?code=synthetic&state=expected');
  }
  assert.equal(route(() => null, '?error=access_denied&state=expected&return_to=https://evil.example'),
    '/factory?error=access_denied&state=expected&return_to=https%3A%2F%2Fevil.example');
});
