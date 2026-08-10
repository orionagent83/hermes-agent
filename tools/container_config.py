"""Lossless projection of supported terminal settings into container backends."""
from __future__ import annotations
import copy
from collections.abc import Mapping
from typing import Any

_CONTAINER_CONFIG_DEFAULTS: dict[str, Any] = {
    "container_cpu": 1, "container_memory": 5120, "container_disk": 51200,
    "container_persistent": True, "vercel_runtime": "", "modal_mode": "auto",
    "docker_volumes": [], "docker_mount_cwd_to_workspace": False,
    "docker_forward_env": [], "docker_env": {}, "docker_run_as_host_user": False,
    "docker_network": True, "docker_extra_args": [], "docker_shm_size": "1g",
    "docker_persist_across_processes": True, "docker_orphan_reaper": True,
}

def project_container_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve explicit false/empty policy while supplying upstream defaults."""
    return {key: config[key] if key in config else copy.deepcopy(default)
            for key, default in _CONTAINER_CONFIG_DEFAULTS.items()}
