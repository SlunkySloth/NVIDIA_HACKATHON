variable "project_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "platform" {
  type    = string
  default = "cpu-d3"
}

variable "preset" {
  type    = string
  default = "2vcpu-8gb"
}

variable "data_disk_gib" {
  type    = number
  default = 40
}

variable "domain" {
  type = string
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9.-]{0,251}[A-Za-z0-9]$", var.domain))
    error_message = "Supply the DNS hostname whose A record will point to the instance."
  }
}

variable "ssh_public_key" {
  type = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+( [^\\n]*)?$", var.ssh_public_key))
    error_message = "Provide an OpenSSH public key on one line."
  }
}

variable "git_ref" {
  type    = string
  default = "main"
  validation {
    condition     = can(regex("^[A-Za-z0-9][A-Za-z0-9._/-]*$", var.git_ref))
    error_message = "Provide a reviewed release tag or branch name."
  }
}
