terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    nebius = {
      source  = "nebius/nebius"
      version = "= 0.6.69"
    }
  }
}

# Authentication comes from NEBIUS_IAM_TOKEN in the calling environment.
# Application inference/Sandbox credentials are supplied separately on the host.
provider "nebius" {}

resource "nebius_compute_v1_disk" "data" {
  parent_id      = var.project_id
  name           = "replaylab-data"
  type           = "NETWORK_SSD"
  size_gibibytes = var.data_disk_gib
  lifecycle {
    prevent_destroy = true
  }
}

resource "nebius_compute_v1_instance" "app" {
  parent_id = var.project_id
  name      = "replaylab-demo"
  resources = {
    platform = var.platform
    preset   = var.preset
  }
  recovery_policy = "RECOVER"
  boot_disk = {
    attach_mode = "READ_WRITE"
    managed_disk = {
      name = "replaylab-boot"
      spec = {
        type           = "NETWORK_SSD"
        size_gibibytes = 40
        source_image_family = {
          image_family = "ubuntu24.04"
        }
      }
    }
  }
  secondary_disks = [{
    attach_mode = "READ_WRITE"
    device_id   = "replaylab-data"
    existing_disk = {
      id = nebius_compute_v1_disk.data.id
    }
  }]
  network_interfaces = [{
    name              = "eth0"
    subnet_id         = var.subnet_id
    ip_address        = {}
    public_ip_address = { static = true }
  }]
  cloud_init_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    ssh_public_key = var.ssh_public_key
    git_ref        = var.git_ref
    domain         = var.domain
  })
}

output "instance_id" {
  value = nebius_compute_v1_instance.app.id
}

output "data_disk_id" {
  value = nebius_compute_v1_disk.data.id
}
