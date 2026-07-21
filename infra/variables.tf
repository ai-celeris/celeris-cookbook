variable "region" {
  description = "Primary AWS region for the site bucket."
  type        = string
  default     = "ap-southeast-2"
}

variable "zone_name" {
  description = "Existing public Route 53 hosted zone the site record is created in (e.g. celeris.ai)."
  type        = string
}

variable "fqdn" {
  description = "Fully qualified domain for the cookbook site. Defaults to cookbook.<zone_name>."
  type        = string
  default     = ""
}
