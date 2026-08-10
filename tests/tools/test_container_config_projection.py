from tools.container_config import project_container_config


def test_container_projection_preserves_every_supported_runtime_field():
    declared = {
        "container_cpu": 3, "container_memory": 4096, "container_disk": 8192,
        "container_persistent": False, "vercel_runtime": "python3.12",
        "modal_mode": "ephemeral", "docker_volumes": ["/host/task:/workspace"],
        "docker_mount_cwd_to_workspace": True, "docker_forward_env": ["LANG"],
        "docker_env": {"MODE": "review"}, "docker_run_as_host_user": True,
        "docker_network": False, "docker_extra_args": ["--read-only"],
        "docker_shm_size": "2g", "docker_persist_across_processes": False,
        "docker_orphan_reaper": False,
    }
    assert project_container_config(declared) == declared


def test_container_projection_preserves_existing_defaults_and_copies_mutables():
    first = project_container_config({})
    second = project_container_config({})
    assert first["docker_persist_across_processes"] is True
    assert first["docker_network"] is True
    assert first["docker_mount_cwd_to_workspace"] is False
    first["docker_volumes"].append("x")
    assert second["docker_volumes"] == []
