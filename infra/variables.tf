# Supply verified account, region and model values; example defaults do not prove availability or authorization.
variable "aws_region" {
  description = "Explicit region supporting the selected model, KB, S3 Vectors, Cognito and ECS Express."
  type        = string
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "Provide a verified commercial AWS region."
  }
}
variable "aws_account_id" {
  description = "Account that the operator has explicitly authorised. The provider rejects any other account."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Provide the actual 12-digit account ID."
  }
}
variable "name_prefix" {
  type    = string
  default = "aws-agent-lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.name_prefix))
    error_message = "Use 3-24 lowercase letters, digits and hyphens, beginning with a letter."
  }
}
variable "allow_paid_resources" {
  description = "Explicit operator gate after reviewing the cost estimate. Never set this during offline checks."
  type        = bool
  default     = false
}
variable "reviewed_monthly_cost_limit_usd" {
  description = "Operator's reviewed cost allowance. This is an acknowledgement, NOT an enforced billing cap."
  type        = number
  default     = 0
}
variable "expires_on" {
  description = "Planned review/teardown date, YYYY-MM-DD. A tag only; no automatic deletion."
  type        = string
  validation {
    condition     = can(formatdate("YYYY-MM-DD", "${var.expires_on}T00:00:00Z"))
    error_message = "Provide an actual review date as YYYY-MM-DD."
  }
}
variable "availability_zones" {
  description = "Two distinct, verified availability zones in aws_region."
  type        = list(string)
  validation {
    condition     = length(var.availability_zones) == 2 && length(toset(var.availability_zones)) == 2 && alltrue([for zone in var.availability_zones : startswith(zone, var.aws_region)])
    error_message = "Provide two distinct zones in the selected region."
  }
}
variable "vpc_cidr" {
  type    = string
  default = "10.73.0.0/16"
  validation {
    condition     = can(cidrsubnet(var.vpc_cidr, 8, 1))
    error_message = "Provide a CIDR that can be split into two subnets."
  }
}
variable "bedrock_model_id" {
  description = "Verified Converse model or inference-profile ID/ARN. No default model availability is assumed."
  type        = string
  validation {
    condition     = length(trimspace(var.bedrock_model_id)) > 0 && !strcontains(var.bedrock_model_id, "*")
    error_message = "Select an exact accessible model or inference profile."
  }
}
variable "bedrock_inference_resource_arns" {
  description = "Exact model/profile ARNs, including every required destination model ARN for a cross-region profile."
  type        = list(string)
  validation {
    condition     = length(var.bedrock_inference_resource_arns) > 0 && alltrue([for arn in var.bedrock_inference_resource_arns : startswith(arn, "arn:aws:bedrock:") && !strcontains(arn, "*")])
    error_message = "List exact Bedrock resource ARNs without wildcards."
  }
}
variable "embedding_model_id" {
  description = "Verify regional availability before deployment. Index dimensions must match."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}
variable "embedding_dimensions" {
  type    = number
  default = 1024
  validation {
    condition     = contains([256, 512, 1024], var.embedding_dimensions)
    error_message = "Titan Text Embeddings V2 dimensions must be 256, 512 or 1024."
  }
}
variable "enable_service" {
  description = "False provisions the supporting resources before an ECR image exists."
  type        = bool
  default     = false
}
variable "service_min_task_count" {
  description = "Minimum number of identical application tasks maintained by ECS Express on Fargate. The production target uses two copies."
  type        = number
  default     = 2
  validation {
    condition     = var.service_min_task_count >= 2 && floor(var.service_min_task_count) == var.service_min_task_count
    error_message = "Maintain at least two whole application task copies for the production target."
  }
}
variable "service_max_task_count" {
  description = "Maximum number of identical application tasks allowed by ECS Express autoscaling."
  type        = number
  default     = 2
  validation {
    condition     = var.service_max_task_count >= var.service_min_task_count && floor(var.service_max_task_count) == var.service_max_task_count
    error_message = "service_max_task_count must be a whole number at least as large as service_min_task_count."
  }
}
variable "factory_provider" {
  description = "Bedrock adapter used by the deployed five-role Factory. aws-langchain is the target path; aws remains the direct Boto3 alternative."
  type        = string
  default     = "aws-langchain"
  validation {
    condition     = contains(["aws", "aws-langchain"], var.factory_provider)
    error_message = "factory_provider must be aws or aws-langchain."
  }
}
variable "enable_factory" {
  description = "True exposes the five-role Factory API to Cognito-authenticated users; its roles then call Bedrock with Knowledge Bases context."
  type        = bool
  default     = false
}
variable "app_image_digest" {
  description = "Exact image digest in the created ECR repository, never a mutable tag."
  type        = string
  default     = ""
  validation {
    condition     = !var.enable_service || can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9/-]+@sha256:[a-f0-9]{64}$", var.app_image_digest))
    error_message = "enable_service requires an ECR URI ending in @sha256:<64 hex characters>."
  }
}
variable "public_base_url" {
  description = "Empty for the fail-closed bootstrap; then the exact generated Express HTTPS origin, without trailing slash."
  type        = string
  default     = ""
  validation {
    condition     = var.public_base_url == "" || can(regex("^https://[a-zA-Z0-9.-]+$", var.public_base_url))
    error_message = "Provide only the HTTPS origin, or leave empty during bootstrap."
  }
}
variable "access_policy" {
  description = "Cognito group -> server-side tenant/access mapping. No users or passwords are created."
  type = map(object({
    tenant       = string
    access_level = string
  }))
  validation {
    condition     = length(var.access_policy) >= 1 && alltrue([for group, scope in var.access_policy : can(regex("^[a-zA-Z0-9_-]{1,64}$", group)) && can(regex("^[a-z0-9_-]{1,64}$", scope.tenant)) && can(regex("^[a-z0-9_-]{1,64}$", scope.access_level))])
    error_message = "Provide at least one explicit, non-empty group and access scope."
  }
}
variable "github_repository" {
  description = "Actual owner/repository used only for documentation and tags. OIDC subjects are specified separately."
  type        = string
  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", var.github_repository))
    error_message = "Provide the actual GitHub owner/repository."
  }
}
variable "github_oidc_subjects" {
  description = "Exact subject claims for approved build/deployment environments. New repositories may contain immutable numeric IDs. No wildcard."
  type        = list(string)
  validation {
    condition     = length(var.github_oidc_subjects) >= 1 && alltrue([for subject in var.github_oidc_subjects : startswith(subject, "repo:") && !strcontains(subject, "*") && !strcontains(subject, "?") && (strcontains(subject, ":environment:") || strcontains(subject, ":ref:refs/heads/"))])
    error_message = "Use exact observed OIDC subjects for an environment or branch; no wildcard or PR subject."
  }
}
variable "create_github_oidc_provider" {
  description = "Only true when this account does not already have the GitHub OIDC provider."
  type        = bool
  default     = false
}
variable "existing_github_oidc_provider_arn" {
  type    = string
  default = ""
}
variable "runtime_secret_arns" {
  description = "Optional environment name -> existing Secrets Manager ARN. Values are never stored in Terraform."
  type        = map(string)
  default     = {}
  validation {
    condition     = alltrue([for name, arn in var.runtime_secret_arns : can(regex("^[A-Z][A-Z0-9_]+$", name)) && startswith(arn, "arn:aws:secretsmanager:${var.aws_region}:${var.aws_account_id}:secret:")])
    error_message = "Use uppercase environment names and secrets in the selected account/region."
  }
}
variable "runtime_secret_kms_key_arns" {
  description = "Exact CMK ARNs for optional runtime secrets, if they are not encrypted with the AWS-managed key."
  type        = list(string)
  default     = []
}