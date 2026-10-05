terraform {
  required_version = ">= 1.12.2, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 6.66.0" }
  }
}
provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  default_tags {
    tags = { Project = "secloudis-agentcore", DataClass = "synthetic-only", ManagedBy = "Terraform" }
  }
}
variable "region" { type = string }
variable "account_id" { type = string }
variable "image_uri" { type = string }
variable "repository_arn" { type = string }
variable "user_pool_id" { type = string }
variable "application_permissions" { type = any }
variable "runtime_environment" {
  type      = map(string)
  sensitive = true
}

# Existing user pool, retrieval sources and DynamoDB tables are reused.
# A separate test client avoids changing the deployed web client's auth flows.
resource "aws_cognito_user_pool_client" "test" {
  name                          = "secloudis-agentcore-synthetic-test"
  user_pool_id                  = var.user_pool_id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
}
resource "aws_iam_role" "runtime" {
  name = "secloudis-agentcore-runtime"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "bedrock-agentcore.amazonaws.com" },
    Condition = {
      StringEquals = { "aws:SourceAccount" = var.account_id }
      ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock-agentcore:${var.region}:${var.account_id}:*" }
    }
  }] })
}
resource "aws_iam_role_policy" "runtime" {
  role = aws_iam_role.runtime.id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat(var.application_permissions, [
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"], Resource = var.repository_arn },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken", "logs:DescribeLogGroups"], Resource = "*" },
    { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:DescribeLogStreams"], Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/bedrock-agentcore/runtimes/secloudis_factory_*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/bedrock-agentcore/runtimes/secloudis_factory_*:log-stream:*" }
  ]) })
}
# Root sessions cannot assume roles. The acceptance harness creates this narrowly
# scoped IAM operator temporarily, then removes its key, policy and user.
resource "aws_iam_role" "caller" {
  name = "secloudis-agentcore-engineering-caller"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Action = "sts:AssumeRole", Principal = { AWS = "arn:aws:iam::${var.account_id}:root" },
    Condition = { ArnEquals = { "aws:PrincipalArn" = "arn:aws:iam::${var.account_id}:user/secloudis-agentcore-test-operator" } }
  }] })
}
resource "aws_bedrockagentcore_agent_runtime" "factory" {
  agent_runtime_name = "secloudis_factory_minimum"
  description        = "Synthetic five-agent Factory; verified Cognito identities; engineering demonstration"
  role_arn           = aws_iam_role.runtime.arn
  agent_runtime_artifact {
    container_configuration { container_uri = var.image_uri }
  }
  network_configuration { network_mode = "PUBLIC" }
  protocol_configuration { server_protocol = "HTTP" }
  lifecycle_configuration = [{ idle_runtime_session_timeout = 60, max_lifetime = 900 }]
  environment_variables = merge(var.runtime_environment, {
    LOCAL_DEMO_MODE         = "false"
    AGENTCORE_LOCAL_TEST    = "false"
    AGENTCORE_INBOUND_AUTH  = "iam"
    COGNITO_CLIENT_ID       = aws_cognito_user_pool_client.test.id
    COGNITO_REQUIRED_SCOPES = "aws.cognito.signin.user.admin"
    LAB_DATA_DIR            = "/tmp/factory"
  })
  depends_on = [aws_iam_role_policy.runtime]
}
resource "aws_iam_role_policy" "caller" {
  role = aws_iam_role.caller.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "bedrock-agentcore:InvokeAgentRuntime",
    Resource = [aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn,
    "${aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn}/runtime-endpoint/DEFAULT"]
  }] })
}
resource "aws_bedrockagentcore_resource_policy" "caller_only" {
  resource_arn = aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Principal = { AWS = aws_iam_role.caller.arn }, Action = "bedrock-agentcore:InvokeAgentRuntime", Resource = aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn },
    { Effect = "Deny", Principal = "*", Action = "bedrock-agentcore:InvokeAgentRuntime", Resource = aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn,
    Condition = { ArnNotEquals = { "aws:PrincipalArn" = aws_iam_role.caller.arn } } }
  ] })
}
# Invocation targets an endpoint as well as its Runtime. Apply the same boundary
# to DEFAULT so an identity policy cannot bypass the designated caller there.
resource "aws_bedrockagentcore_resource_policy" "endpoint_caller_only" {
  resource_arn = "${aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn}/runtime-endpoint/DEFAULT"
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Principal = { AWS = aws_iam_role.caller.arn }, Action = "bedrock-agentcore:InvokeAgentRuntime", Resource = "${aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn}/runtime-endpoint/DEFAULT" },
    { Effect = "Deny", Principal = "*", Action = "bedrock-agentcore:InvokeAgentRuntime", Resource = "${aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn}/runtime-endpoint/DEFAULT",
    Condition = { ArnNotEquals = { "aws:PrincipalArn" = aws_iam_role.caller.arn } } }
  ] })
}
output "runtime_arn" { value = aws_bedrockagentcore_agent_runtime.factory.agent_runtime_arn }
output "runtime_id" { value = aws_bedrockagentcore_agent_runtime.factory.agent_runtime_id }
output "caller_role_arn" { value = aws_iam_role.caller.arn }
output "test_client_id" { value = aws_cognito_user_pool_client.test.id }

