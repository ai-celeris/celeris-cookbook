variable "region" {
  description = "AWS region for the cookbook assets bucket. Must match the docs distribution's account region conventions."
  type        = string
  default     = "us-west-2"
}

variable "docs_distribution_arn" {
  description = "ARN of the existing docs.celeris.ai CloudFront distribution (diffusion-llm-service infra/management, aws_cloudfront_distribution.docs). Grants it OAC read access to the cookbook bucket."
  type        = string
}

variable "docs_distribution_id" {
  description = "ID of the docs.celeris.ai CloudFront distribution. The deploy role may create invalidations on it."
  type        = string
}

variable "github_org" {
  description = "GitHub org the deploy workflow runs in."
  type        = string
  default     = "ai-celeris"
}

variable "deploy_github_repo" {
  description = "Repository whose GitHub Actions workflow may assume the deploy role."
  type        = string
  default     = "celeris-cookbook-deploy"
}

variable "create_github_oidc_provider" {
  description = "Create the token.actions.githubusercontent.com OIDC provider. Leave false when the account already has one (an account can only have one per URL)."
  type        = bool
  default     = false
}
