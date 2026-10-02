# Publish resource identifiers needed by operators; never output secret values or tokens.
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "github_deploy_role_arn" { value = aws_iam_role.github_deploy.arn }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.main.id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.web.id }
output "cognito_domain" { value = local.runtime_environment.COGNITO_DOMAIN }
output "knowledge_base_id" { value = aws_bedrockagent_knowledge_base.main.id }
output "data_source_id" { value = aws_bedrockagent_data_source.corpus.data_source_id }
output "corpus_bucket" { value = aws_s3_bucket.data["corpus"].id }
output "artifact_bucket" { value = aws_s3_bucket.data["artifacts"].id }
output "service_arn" { value = try(aws_ecs_express_gateway_service.app[0].service_arn, null) }
output "service_ingress_paths" { value = try(aws_ecs_express_gateway_service.app[0].ingress_paths, []) }
output "reviewed_cost_allowance_usd" {
  description = "Operator acknowledgement only. This does not prevent AWS charges beyond this amount."
  value       = var.reviewed_monthly_cost_limit_usd
}
