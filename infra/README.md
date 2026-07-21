# Cookbook site infrastructure

The cookbook website is served at **https://docs.celeris.ai/cookbook/** by the
*existing* docs.celeris.ai CloudFront distribution (defined in
diffusion-llm-service `infra/management/docs-hosting.tf`). The cookbook does
not run its own distribution, certificate, or DNS.

This root owns only the cookbook's pieces:

- **Assets bucket** (`celeris-cookbook-assets-<account>`): private S3, read
  only by the docs distribution via Origin Access Control. The built site
  lives under the `cookbook/` prefix because CloudFront forwards the full
  request path (`/cookbook/x` → `s3://bucket/cookbook/x`).
- **GitHub-OIDC deploy role** (`celeris-cookbook-deploy`): assumable only by
  workflows in `ai-celeris/celeris-cookbook-deploy`; may sync the `cookbook/`
  prefix and invalidate `/cookbook/*` on the docs distribution. No static AWS
  keys anywhere.

It must be applied in the **same AWS account** as the docs distribution
(OAC + bucket policy assume same-account), which is the diffusion-llm-service
management-plane prod account.

## Apply

```sh
cd infra
tofu init
tofu apply \
  -var docs_distribution_arn=arn:aws:cloudfront::<account>:distribution/<ID> \
  -var docs_distribution_id=<ID>
```

Get the distribution values from the diffusion-llm-service management root
(`tofu output docs_distribution_id`, or the AWS console). Pass
`-var create_github_oidc_provider=true` only if the account does not already
have the `token.actions.githubusercontent.com` provider (diffusion-llm-service
accounts already do).

Outputs feed the deploy repo's configuration:

| Output | Where it goes |
| --- | --- |
| `site_bucket` | `COOKBOOK_BUCKET` variable in celeris-cookbook-deploy |
| `deploy_role_arn` | `AWS_OIDC_ROLE_ARN` secret in celeris-cookbook-deploy |
| `site_bucket_regional_domain_name` | The docs distribution's cookbook origin (below) |

## Required change to the docs distribution

The docs distribution needs a second origin and a `/cookbook*` behavior. That
change belongs in diffusion-llm-service `infra/management/docs-hosting.tf`
(see the draft PR prepared against that repo), shaped as:

```hcl
# New variable: cookbook_assets_bucket_regional_domain_name (default "" = off).

origin {
  domain_name              = var.cookbook_assets_bucket_regional_domain_name
  origin_id                = "cookbook-s3"
  origin_access_control_id = aws_cloudfront_origin_access_control.docs_assets.id
}

ordered_cache_behavior {
  path_pattern               = "/cookbook*"
  target_origin_id           = "cookbook-s3"
  # Same policies + index-rewrite function as the default docs behavior:
  # the cookbook is also a static multi-page site with directory indexes.
  ...
}
```

The docs site's existing viewer-request index-rewrite function and 403/404 →
`/404.html` mapping apply as-is (the docs 404 page serves for unknown cookbook
paths; acceptable).

## Deploy pipeline

Pushes to celeris-cookbook `main` dispatch the deploy workflow in the private
`ai-celeris/celeris-cookbook-deploy` repo, which builds the site with
`BASE_URL=/cookbook/`, assumes `deploy_role_arn` via OIDC, syncs
`site/dist/` to `s3://<site_bucket>/cookbook/`, and invalidates
`/cookbook/*`. See that repo's README for the token/secret setup.
