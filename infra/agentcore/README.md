# Minimum AgentCore demonstration stack

- **Scope**
  - Deploy one ARM64 Factory Runtime with IAM (Identity and Access Management) inbound authentication.
  - Reuse the existing Cognito user pool, Bedrock retrieval and model resources, and DynamoDB tables.
  - Create a separate Cognito test client for password authentication of synthetic test accounts. The Runtime requires its verified access tokens and `aws.cognito.signin.user.admin` scope.
  - Retain the current ECS (Elastic Container Service) web deployment. This stack does not redirect its browser or MCP (Model Context Protocol) endpoints.
- **Restricted identities**
  - The Runtime execution role permits its image pull, logs, approved model calls, retrieval and shared state operations.
  - A separate engineering caller role can invoke only this Runtime and its DEFAULT endpoint.
  - Runtime and DEFAULT endpoint resource policies restrict ordinary IAM callers. A live test denied an unapproved IAM user even when its identity policy allowed invocation. Administrative root requests reached the handler; root isolation is not claimed.
  - The engineering role trusts only the named temporary IAM test operator. Root sessions cannot assume roles; the acceptance harness creates a role-only operator, keeps its key in memory, and deletes its key, inline policy and user afterwards. Routine production access requires a separate operator identity design.
  - Company and approval authority still comes from verified Cognito groups and server-owned policy.
- **Cost and session lifetime**
  - The Runtime uses managed on-demand sessions with a 60-second idle timeout and a 900-second maximum instance lifetime.
  - This limits idle session duration; it is not a billing cap. Image storage, logs, Cognito activity and inference can still incur charges.
  - No Microsoft tenant, dedicated EC2 instance, AgentCore memory service or gateway is created.
- **Inputs and state**
  - Supply `region`, `account_id`, exact digest-based `image_uri`, `repository_arn`, `user_pool_id`, scoped `application_permissions` and `runtime_environment` through a private `terraform.tfvars.json`.
  - Never commit variable values, Terraform state, generated passwords or access tokens.
  - Run `terraform init`, `terraform validate`, then review a saved `terraform plan` before applying that exact plan.
- **Acceptance and evidence**
  - Invoke through the restricted engineering role with real synthetic Cognito requester and approver identities.
  - Verify arrival at G1 Scope, all four gates, five agent artifacts, durable recovery, cross-company denial, self-approval denial and stale-hash denial.
  - Record Runtime readiness and exact image digest separately from successful authenticated workflow execution.
  - Keep a bounded demonstration online only for its agreed review period. Remove test accounts and destroy this separate stack when it is no longer required; the shared existing platform is outside its destruction scope.



## Portal integration

- Set `portal_task_role_arn` to the existing ECS application task role.
- Set `portal_client_id` to the existing portal Cognito client. Runtime validates
  that client's signed access tokens with the `openid` scope.
- The Runtime and DEFAULT endpoint policies allow the portal task role and the
  narrowly scoped engineering role; all other ordinary IAM callers are denied.
- `enable_test_password_auth` defaults to false. Only enable it temporarily for
  an explicitly planned engineering test, and disable it immediately afterwards.
- Set the portal environment `FACTORY_BACKEND=agentcore`,
  `AGENTCORE_RUNTIME_ARN` and `AGENTCORE_RUNTIME_QUALIFIER=DEFAULT`.
- Rebuild the portal image from the reviewed source and deploy its immutable
  digest. Preserve the existing environment, secret references and ingress.
- The deleted engineering IAM operator must be recreated with only AssumeRole
  permission for a new engineering test; delete its key, policy and user afterwards.
- The portal uses its ECS task role directly and does not need that operator.
- Recheck both identities through browser login and G1–G4 before claiming a
  verified portal integration. MCP routing remains separate.
