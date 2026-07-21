# Cookbook site infrastructure

OpenTofu configuration for the cookbook website: a private S3 bucket served
through CloudFront (Origin Access Control), with a DNS-validated ACM
certificate and Route 53 alias records. This mirrors the
`infra/modules/static-site` pattern in the celeris-apps monorepo, without the
staff gate — the cookbook is public.

## Prerequisites

- An AWS account with an existing public Route 53 hosted zone for the site's
  domain (e.g. `celeris.ai`).
- OpenTofu >= 1.10.

## Usage

```sh
cd infra
tofu init
tofu plan -var zone_name=celeris.ai            # site at cookbook.celeris.ai
tofu apply -var zone_name=celeris.ai
```

Override the hostname with `-var fqdn=cookbook.example.com` (it must be inside
the zone). After apply, note the outputs:

- `site_bucket` -> `COOKBOOK_BUCKET`
- `distribution_id` -> `COOKBOOK_DISTRIBUTION_ID`

then publish with:

```sh
COOKBOOK_BUCKET=... COOKBOOK_DISTRIBUTION_ID=... scripts/deploy-site
```

## Deploy hook

`.github/workflows/deploy-website.yaml` POSTs to the
`WEBSITE_DEPLOY_HOOK_URL` repository secret on every push to `main` (and
no-ops while the secret is unset). Point that hook at whatever runs
`scripts/deploy-site` with AWS credentials — a small endpoint on the compose
host, or a CI/CD system. Configuring the secret and applying this
configuration are deliberate manual steps.

## Remote state

The S3 backend is left commented out in `versions.tf` until the hosting
account is chosen; uncomment and fill in the account's tfstate bucket before
the first `tofu init` in a shared environment.
