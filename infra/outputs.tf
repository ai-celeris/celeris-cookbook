output "site_url" {
  description = "Public URL of the cookbook site."
  value       = "https://${local.fqdn}"
}

output "site_bucket" {
  description = "Assets bucket to sync site/dist into (COOKBOOK_BUCKET for scripts/deploy-site)."
  value       = aws_s3_bucket.assets.bucket
}

output "distribution_id" {
  description = "CloudFront distribution id to invalidate (COOKBOOK_DISTRIBUTION_ID for scripts/deploy-site)."
  value       = aws_cloudfront_distribution.site.id
}
