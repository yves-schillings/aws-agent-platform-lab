# Deployment candidate only: these definitions create resources only when Terraform is explicitly applied.
# Source objects, vector search and run artifacts are separate stores with separately scoped roles.
locals {
  account_arn     = "arn:aws:iam::${var.aws_account_id}:root"
  resource_prefix = "${var.name_prefix}-${var.aws_account_id}-${var.aws_region}"
  # Cognito and S3 Vectors reserve names containing "aws". Keep the workload
  # prefix for AWS resources, but use provider-safe identifiers for these two
  # globally named endpoints.
  cognito_domain_prefix = "secloudis-agent-${var.aws_account_id}-${var.aws_region}"
  vector_bucket_name    = "secloudis-agent-${var.aws_account_id}-${var.aws_region}-vectors"
  embedding_arn         = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embedding_model_id}"
  express_service_arn   = "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:service/${var.name_prefix}/${var.name_prefix}"
  github_provider_arn   = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.existing_github_oidc_provider_arn
  callback_urls         = var.public_base_url == "" ? ["http://localhost:8000/auth/callback"] : ["${var.public_base_url}/auth/callback"]
  runtime_environment = {
    LOCAL_DEMO_MODE           = "false"
    PORT                      = "8000"
    AWS_REGION                = var.aws_region
    BEDROCK_MODEL_ID          = var.bedrock_model_id
    BEDROCK_KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.main.id
    COGNITO_USER_POOL_ID      = aws_cognito_user_pool.main.id
    COGNITO_CLIENT_ID         = aws_cognito_user_pool_client.web.id
    COGNITO_ISSUER            = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
    COGNITO_DOMAIN            = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
    COGNITO_REDIRECT_URI      = var.public_base_url == "" ? "" : "${var.public_base_url}/auth/callback"
    ACCESS_POLICY_JSON        = jsonencode(var.access_policy)
    ARTIFACT_BUCKET           = aws_s3_bucket.data["artifacts"].id
    POC_TIMEOUT_SECONDS       = "45"
    POC_MAX_ATTEMPTS          = "2"
    POC_MAX_OUTPUT_TOKENS     = "2048"
    OTEL_SERVICE_NAME         = var.name_prefix
    FACTORY_ENABLED           = var.enable_factory ? "true" : "false"
    FACTORY_PROVIDER          = var.enable_factory ? var.factory_provider : "fixtures"
    FACTORY_CHECKPOINTS_TABLE = aws_dynamodb_table.factory_checkpoints.name
    FACTORY_RUNS_TABLE        = aws_dynamodb_table.factory_runs.name
    LAB_DATA_DIR              = "/app/artifacts/lab-data"
  }
}

resource "terraform_data" "deployment_gate" {
  lifecycle {
    precondition {
      condition     = var.allow_paid_resources && var.reviewed_monthly_cost_limit_usd > 0
      error_message = "Cloud resources require explicit allow_paid_resources=true and a reviewed positive cost allowance. Offline validate does not require this."
    }
    precondition {
      condition     = var.create_github_oidc_provider != (var.existing_github_oidc_provider_arn != "")
      error_message = "Either create the GitHub provider or provide its existing ARN, not both/neither."
    }
    precondition {
      condition     = var.existing_github_oidc_provider_arn == "" || var.existing_github_oidc_provider_arn == "arn:aws:iam::${var.aws_account_id}:oidc-provider/token.actions.githubusercontent.com"
      error_message = "The existing GitHub OIDC provider must belong to the selected account."
    }
    precondition {
      condition     = length(setintersection(toset(keys(var.runtime_secret_arns)), toset(["LOCAL_DEMO_MODE", "PORT", "AWS_REGION", "BEDROCK_MODEL_ID", "BEDROCK_KNOWLEDGE_BASE_ID", "COGNITO_USER_POOL_ID", "COGNITO_CLIENT_ID", "COGNITO_ISSUER", "COGNITO_DOMAIN", "COGNITO_REDIRECT_URI", "ACCESS_POLICY_JSON", "ARTIFACT_BUCKET", "POC_TIMEOUT_SECONDS", "POC_MAX_ATTEMPTS", "POC_MAX_OUTPUT_TOKENS", "OTEL_SERVICE_NAME", "FACTORY_ENABLED", "FACTORY_PROVIDER", "FACTORY_CHECKPOINTS_TABLE", "FACTORY_RUNS_TABLE", "LAB_DATA_DIR"]))) == 0
      error_message = "Secrets cannot override the application's identity, access policy or safety configuration."
    }
  }
}

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  depends_on           = [terraform_data.deployment_gate]
}
resource "aws_subnet" "public" {
  for_each                = { for index, zone in var.availability_zones : zone => index }
  vpc_id                  = aws_vpc.main.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, each.value)
  map_public_ip_on_launch = false
}
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_kms_key" "data" {
  description             = "Synthetic lab document and artifact encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnableAccountAdministration"
        Effect    = "Allow"
        Principal = { AWS = local.account_arn }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowS3VectorsBackgroundIndexing"
        Effect    = "Allow"
        Principal = { Service = "indexing.s3vectors.amazonaws.com" }
        Action    = ["kms:Decrypt"]
        Resource  = "*"
        Condition = {
          ArnLike = {
            "aws:SourceArn" = "arn:aws:s3vectors:${var.aws_region}:${var.aws_account_id}:bucket/*"
          }
          StringEquals = {
            "aws:SourceAccount" = var.aws_account_id
          }
        }
      }
    ]
  })
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_kms_alias" "data" {
  name          = "alias/${var.name_prefix}-data"
  target_key_id = aws_kms_key.data.key_id
}
resource "aws_s3_bucket" "data" {
  for_each      = toset(["corpus", "artifacts"])
  bucket        = "${local.resource_prefix}-${each.key}"
  force_destroy = false
  depends_on    = [terraform_data.deployment_gate]
}
resource "aws_s3_bucket_public_access_block" "data" {
  for_each                = aws_s3_bucket.data
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  rule { object_ownership = "BucketOwnerEnforced" }
}
resource "aws_s3_bucket_versioning" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  rule {
    bucket_key_enabled = true
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}
resource "aws_s3_bucket_policy" "tls" {
  for_each = aws_s3_bucket.data
  bucket   = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*"
      Resource  = [each.value.arn, "${each.value.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

# Two Fargate application tasks cannot share a local SQLite file.  The Factory
# stores LangGraph checkpoints and run ownership in these encrypted, shared
# DynamoDB tables so either healthy task can resume a gate decision.
resource "aws_dynamodb_table" "factory_checkpoints" {
  name         = "${local.resource_prefix}-factory-checkpoints"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }
  point_in_time_recovery { enabled = true }
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
  depends_on = [terraform_data.deployment_gate]
}

resource "aws_dynamodb_table" "factory_runs" {
  name         = "${local.resource_prefix}-factory-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }
  point_in_time_recovery { enabled = true }
  depends_on = [terraform_data.deployment_gate]
}

resource "aws_s3vectors_vector_bucket" "main" {
  vector_bucket_name = local.vector_bucket_name
  force_destroy      = false
  encryption_configuration {
    sse_type    = "aws:kms"
    kms_key_arn = aws_kms_key.data.arn
  }
}
resource "aws_s3vectors_index" "documents" {
  index_name         = "documents"
  vector_bucket_name = aws_s3vectors_vector_bucket.main.vector_bucket_name
  data_type          = "float32"
  dimension          = var.embedding_dimensions
  distance_metric    = "cosine"
  metadata_configuration {
    non_filterable_metadata_keys = ["AMAZON_BEDROCK_TEXT_CHUNK", "AMAZON_BEDROCK_METADATA"]
  }
}

resource "aws_iam_role" "knowledge_base" {
  name = "${var.name_prefix}-knowledge-base"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "bedrock.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:bedrock:${var.aws_region}:${var.aws_account_id}:knowledge-base/*" }
      }
    }]
  })
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_iam_role_policy" "knowledge_base" {
  role = aws_iam_role.knowledge_base.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [
      { Effect = "Allow", Action = ["bedrock:InvokeModel"], Resource = [local.embedding_arn] },
      { Effect = "Allow", Action = ["s3:ListBucket"], Resource = [aws_s3_bucket.data["corpus"].arn], Condition = { StringLike = { "s3:prefix" = ["documents", "documents/*"] } } },
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.data["corpus"].arn}/documents/*"] },
      { Effect = "Allow", Action = ["s3vectors:PutVectors", "s3vectors:GetVectors", "s3vectors:DeleteVectors", "s3vectors:QueryVectors", "s3vectors:GetIndex"], Resource = [aws_s3vectors_index.documents.index_arn] },
      { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"], Resource = [aws_kms_key.data.arn] }
    ]
  })
}
resource "aws_bedrockagent_knowledge_base" "main" {
  name     = var.name_prefix
  role_arn = aws_iam_role.knowledge_base.arn
  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = local.embedding_arn
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = var.embedding_dimensions
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }
  storage_configuration {
    type = "S3_VECTORS"
    s3_vectors_configuration { index_arn = aws_s3vectors_index.documents.index_arn }
  }
  depends_on = [aws_iam_role_policy.knowledge_base, aws_s3_bucket_server_side_encryption_configuration.data]
}
resource "aws_bedrockagent_data_source" "corpus" {
  name                 = "synthetic-documents"
  knowledge_base_id    = aws_bedrockagent_knowledge_base.main.id
  data_deletion_policy = "RETAIN"
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.data["corpus"].arn
      inclusion_prefixes = ["documents/"]
    }
  }
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 10
      }
    }
  }
}

resource "aws_cognito_user_pool" "main" {
  name                     = var.name_prefix
  deletion_protection      = "ACTIVE"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"
  admin_create_user_config { allow_admin_create_user_only = true }
  software_token_mfa_configuration { enabled = true }
  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 1
  }
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_cognito_user_pool_domain" "main" {
  domain                = local.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.main.id
  managed_login_version = 1 # Classic hosted sign-in; no managed-login branding dependency.
}
resource "aws_cognito_user_pool_client" "web" {
  name                                 = "${var.name_prefix}-web"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = local.callback_urls
  logout_urls                          = var.public_base_url == "" ? ["http://localhost:8000/"] : ["${var.public_base_url}/"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
resource "aws_cognito_user_group" "scope" {
  for_each     = var.access_policy
  name         = each.key
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Synthetic tenant ${each.value.tenant}, access ${each.value.access_level}"
}

resource "aws_ecr_repository" "app" {
  name                 = var.name_prefix
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/lab/${var.name_prefix}/application"
  retention_in_days = 14
  depends_on        = [terraform_data.deployment_gate]
}
resource "aws_ecs_cluster" "main" {
  name = var.name_prefix
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-execution"
  assume_role_policy = local.task_trust
  depends_on         = [terraform_data.deployment_gate]
}
resource "aws_iam_role" "application" {
  name               = "${var.name_prefix}-application"
  assume_role_policy = local.task_trust
  depends_on         = [terraform_data.deployment_gate]
}
locals {
  task_trust = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" }
    Condition = { StringEquals = { "aws:SourceAccount" = var.aws_account_id }, ArnLike = { "aws:SourceArn" = "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:*" } }
  }] })
}
resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = concat([
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.app.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
    ], length(var.runtime_secret_arns) == 0 ? [] : [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = values(var.runtime_secret_arns) }
    ], length(var.runtime_secret_kms_key_arns) == 0 ? [] : [
    { Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.runtime_secret_kms_key_arns }
  ]) })
}
resource "aws_iam_role_policy" "application" {
  role = aws_iam_role.application.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["bedrock:InvokeModel"], Resource = var.bedrock_inference_resource_arns },
    { Effect = "Allow", Action = ["bedrock:Retrieve"], Resource = aws_bedrockagent_knowledge_base.main.arn },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query", "dynamodb:BatchGetItem", "dynamodb:BatchWriteItem"], Resource = [aws_dynamodb_table.factory_checkpoints.arn, aws_dynamodb_table.factory_runs.arn] },
    # GetObject must distinguish a missing lease/state key (404) from denied
    # access (403). A GetObject request carries no ListObjects prefix condition.
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.data["artifacts"].arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = ["${aws_s3_bucket.data["artifacts"].arn}/runs/*", "${aws_s3_bucket.data["artifacts"].arn}/principals/*"] },
    { Effect = "Allow", Action = ["kms:Decrypt", "kms:GenerateDataKey"], Resource = aws_kms_key.data.arn }
  ] })
}
resource "aws_iam_role" "express" {
  name = "${var.name_prefix}-express"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs.amazonaws.com" }
  }] })
  depends_on = [terraform_data.deployment_gate]
}
resource "aws_iam_role_policy_attachment" "express" {
  role       = aws_iam_role.express.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}
resource "aws_iam_service_linked_role" "ecs_application_autoscaling" {
  # Provision this before the first Express revision so its auto-scaling
  # policy can be created without an IAM propagation race.
  aws_service_name = "ecs.application-autoscaling.amazonaws.com"
  lifecycle { ignore_changes = [description, tags, tags_all] }
}
resource "aws_iam_service_linked_role" "elastic_load_balancing" {
  # The first Express revision creates an Application Load Balancer.
  aws_service_name = "elasticloadbalancing.amazonaws.com"
  lifecycle { ignore_changes = [description, tags, tags_all] }
}
resource "aws_ecs_express_gateway_service" "app" {
  count                   = var.enable_service ? 1 : 0
  cluster                 = aws_ecs_cluster.main.name
  service_name            = var.name_prefix
  execution_role_arn      = aws_iam_role.execution.arn
  infrastructure_role_arn = aws_iam_role.express.arn
  task_role_arn           = aws_iam_role.application.arn
  cpu                     = "512"
  memory                  = "1024"
  health_check_path       = "/healthz"
  wait_for_steady_state   = true
  primary_container {
    image          = var.app_image_digest
    container_port = 8000
    aws_logs_configuration {
      log_group         = aws_cloudwatch_log_group.app.name
      log_stream_prefix = "app"
    }
    dynamic "environment" {
      for_each = local.runtime_environment
      content {
        name  = environment.key
        value = environment.value
      }
    }
    dynamic "secret" {
      for_each = var.runtime_secret_arns
      content {
        name       = secret.key
        value_from = secret.value
      }
    }
  }
  network_configuration { subnets = [for subnet in aws_subnet.public : subnet.id] }
  scaling_target {
    min_task_count            = var.service_min_task_count
    max_task_count            = var.service_max_task_count
    auto_scaling_metric       = "AVERAGE_CPU"
    auto_scaling_target_value = 70
  }
  lifecycle {
    ignore_changes = [primary_container[0].image]
    precondition {
      condition     = startswith(var.app_image_digest, "${aws_ecr_repository.app.repository_url}@sha256:")
      error_message = "The bootstrap image must belong to this lab's exact ECR repository."
    }
  }
  depends_on = [aws_iam_role_policy.execution, aws_iam_role_policy.application,
    aws_iam_role_policy_attachment.express, aws_iam_service_linked_role.ecs_application_autoscaling,
  aws_iam_service_linked_role.elastic_load_balancing, aws_route_table_association.public]
}

resource "aws_cloudwatch_log_metric_filter" "errors" {
  name           = "${var.name_prefix}-errors"
  log_group_name = aws_cloudwatch_log_group.app.name
  pattern        = "{ $.outcome = \"error\" }"
  metric_transformation {
    name          = "WorkflowErrors"
    namespace     = "Lab/${var.name_prefix}"
    value         = "1"
    default_value = "0"
  }
}
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.name_prefix}-workflow-errors"
  namespace           = "Lab/${var.name_prefix}"
  metric_name         = "WorkflowErrors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  period              = 60
  statistic           = "Sum"
  threshold           = 3
  treat_missing_data  = "notBreaching"
  alarm_description   = "Demonstration alarm only. No notification destination or automatic rollback is configured."
  depends_on          = [aws_cloudwatch_log_metric_filter.errors]
}
