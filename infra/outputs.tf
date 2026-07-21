output "site_bucket" {
  description = "Assets bucket; the deploy syncs site/dist into its cookbook/ prefix (COOKBOOK_BUCKET)."
  value       = aws_s3_bucket.assets.bucket
}

output "site_bucket_regional_domain_name" {
  description = "Origin domain name for the docs distribution's cookbook origin."
  value       = aws_s3_bucket.assets.bucket_regional_domain_name
}

output "deploy_role_arn" {
  description = "GitHub-OIDC role assumed by celeris-cookbook-deploy (AWS_OIDC_ROLE_ARN)."
  value       = aws_iam_role.deploy.arn
}
