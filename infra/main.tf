# Cookbook site hosting pieces the cookbook OWNS:
#
#   1. A private S3 bucket holding the built site under the cookbook/ prefix.
#   2. A GitHub-OIDC deploy role for ai-celeris/celeris-cookbook-deploy that
#      may sync that prefix and invalidate /cookbook/* on the docs
#      distribution.
#
# The cookbook does NOT own a CloudFront distribution: the site is served at
# https://docs.celeris.ai/cookbook/ by the EXISTING docs distribution
# (diffusion-llm-service infra/management/docs-hosting.tf), which needs a
# second origin pointing at this bucket and an ordered /cookbook* cache
# behavior. That change lives in the diffusion-llm-service repo; see README.md
# here for the exact shape. This root must be applied first so the bucket
# exists for the distribution to reference.
#
# CloudFront forwards the full request path to the origin, so /cookbook/x
# resolves to s3://<bucket>/cookbook/x — which is why the deploy syncs into
# the cookbook/ prefix instead of the bucket root.

locals {
  name = "celeris-cookbook"
}

data "aws_caller_identity" "current" {}

# --- Assets bucket ------------------------------------------------------------

resource "aws_s3_bucket" "assets" {
  bucket        = "${local.name}-assets-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Only the docs distribution (via OAC) may read objects.
data "aws_iam_policy_document" "assets" {
  statement {
    sid       = "AllowDocsCloudFrontRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.assets.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [var.docs_distribution_arn]
    }
  }
}

resource "aws_s3_bucket_policy" "assets" {
  bucket = aws_s3_bucket.assets.id
  policy = data.aws_iam_policy_document.assets.json

  depends_on = [aws_s3_bucket_public_access_block.assets]
}

# --- GitHub OIDC deploy role --------------------------------------------------
# Same shape as diffusion-llm-service infra/modules/github-oidc: federated
# trust on the exact repo subject claim, no static keys. The account can hold
# only one provider per URL, so creation is opt-in.

locals {
  oidc_host         = "token.actions.githubusercontent.com"
  oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://${local.oidc_host}"
}

data "aws_iam_policy_document" "assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Any ref in the deploy repo may deploy; tighten to an environment claim
    # if the deploy repo adopts GitHub environments.
    condition {
      test     = "StringLike"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_org}/${var.deploy_github_repo}:*"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${local.name}-deploy"
  assume_role_policy   = data.aws_iam_policy_document.assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "ListCookbookPrefix"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.assets.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["cookbook/*", "cookbook", ""]
    }
  }

  statement {
    sid    = "WriteCookbookPrefix"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = ["${aws_s3_bucket.assets.arn}/cookbook/*"]
  }

  statement {
    sid       = "InvalidateDocsDistribution"
    effect    = "Allow"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = ["arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${var.docs_distribution_id}"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "deploy-cookbook-site"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
