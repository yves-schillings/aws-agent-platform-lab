# Browser authentication and source permissions

AWS mode uses Cognito authorization code flow with PKCE (`S256`). The API verifies Cognito access tokens before resolving source and run permissions. Local demonstration mode is a separate, explicitly simulated loopback mode.

## Configure the cloud boundary

| Setting | Required value |
|---|---|
| `LOCAL_DEMO_MODE` | Absent or `false` for AWS mode |
| `AWS_REGION` | Region containing the configured Cognito pool |
| `COGNITO_USER_POOL_ID` | Pool ID matching that region |
| `COGNITO_CLIENT_ID` | Public app client with authorization code flow, no client secret |
| `COGNITO_ISSUER` | Exact `https://cognito-idp.<region>.amazonaws.com/<pool-id>` issuer |
| `COGNITO_DOMAIN` | Full HTTPS managed-login/custom-domain origin, with no path or query |
| `COGNITO_REDIRECT_URI` | Exact registered HTTPS application callback, usually `/auth/callback` |
| `COGNITO_REQUIRED_SCOPES` | Space-separated required scopes; defaults to `openid` |
| `ACCESS_POLICY_JSON` | Explicit server-owned Cognito-group to tenant/access-level mappings |

The China partition uses `amazonaws.com.cn` in the issuer. Application settings for Bedrock, Knowledge Bases and artifact storage are separate from this identity configuration. Missing authentication settings leave `/healthz` available but close sign-in configuration and authenticated endpoints with an error.

Example synthetic mapping:

```json
{
  "demo-alpha": {"tenant": "alpha", "access_level": "internal"},
  "demo-beta": {"tenant": "beta", "access_level": "internal"}
}
```

Tenant and access-level labels use lowercase letters, numbers, underscores and hyphens, with at most 64 characters. Provision the two demonstration users and groups through the identity administrator; disable public sign-up. An identity with no mapped group, or groups resolving to different scopes, is denied. There is no automatic broadest-permission selection.

## Sign-in sequence

1. The browser generates cryptographically random OAuth state and a PKCE verifier. Only this short-lived state/verifier pair is stored in `sessionStorage`; it expires after ten minutes.
2. Cognito authenticates the user and redirects with an authorization code and the original state.
3. The browser removes callback query parameters from its URL, consumes the stored state once and checks state/age before exchanging the code.
4. The API exchanges the code and verifier only at its configured Cognito token endpoint and uses its configured callback. A request cannot override either URL.
5. The API validates the returned access token. It does not return the Cognito refresh or ID token to the browser.
6. The access token stays only in JavaScript memory and is sent as a Bearer token on same-origin API requests. No authentication cookies, persistent browser token storage or refresh-token mechanism is used. Reloading requires sign-in again.

Register the configured callback as an allowed callback URL. Register the application origin's root URL (for example `https://lab.example.org/`) as the allowed logout return URL. Browser sign-out drops the in-memory access token and navigates to Cognito logout with that root return URL. It is not a global access-token revocation mechanism.

## Token and request checks

- Only `RS256` signatures using the configured pool's JWKS endpoint are accepted. The token cannot select another issuer or key URL.
- Signature, issuer, expiry, issued-at time, `token_use=access`, app `client_id`, subject, required scopes and group shape are checked.
- The group-to-source policy is controlled by the server. Request JSON cannot select a tenant, group, knowledge-base filter, tool command or model endpoint.
- Cognito user identity, source permissions, run ownership and tool permissions are distinct checks. The load balancer is not presumed to authenticate the user.
- Calls use Bearer headers rather than ambient authentication cookies. No cross-origin API permissions are enabled. PKCE state addresses login CSRF; the API independently verifies the token on every authenticated request.
- CSP disallows inline scripts, external connections, frames and object embedding. Model and source text is rendered as text, not HTML. OAuth codes, tokens and verifier values are omitted from validation errors and request access logs are disabled.

Group membership is represented by the signed token and can remain valid until that token expires. Short access-token lifetimes and a documented revocation/permission-change approach are needed before broader use. This prototype does not claim enterprise federation, immediate revocation, multi-tenant production assurance or hardened public-service abuse protection.

## Primary references

- [Cognito authorization endpoint and PKCE](https://docs.aws.amazon.com/cognito/latest/developerguide/authorization-endpoint.html)
- [Cognito token endpoint](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html)
- [Cognito JWT verification](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
- [PyJWT API](https://pyjwt.readthedocs.io/en/latest/api.html)
