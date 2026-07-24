"""Tests for Docker container config propagation in execute_code."""

import threading
from unittest.mock import MagicMock, patch

from tools.code_execution_tool import _get_or_create_env


def test_execute_code_passes_docker_runtime_and_reuse_options():
    config = {
        "env_type": "docker",
        "docker_image": "test-image:latest",
        "singularity_image": "docker://test",
        "modal_image": "test",
        "daytona_image": "test",
        "cwd": "/workspace",
        "host_cwd": "/host/project",
        "timeout": 180,
        "container_cpu": 2,
        "container_memory": 4096,
        "container_disk": 20480,
        "container_persistent": False,
        "docker_volumes": [],
        "docker_mount_cwd_to_workspace": True,
        "docker_forward_env": ["API_KEY"],
        "docker_env": {"SAFE_FLAG": "1"},
        "docker_run_as_host_user": True,
        "docker_extra_args": ["--read-only"],
        "docker_network": False,
        "docker_persist_across_processes": False,
        "docker_orphan_reaper": False,
    }
    captured = {}
    mock_env = MagicMock()

    def fake_create_env(**kwargs):
        captured.update(kwargs)
        return mock_env

    with (
        patch("tools.terminal_tool._get_env_config", return_value=config),
        patch("tools.terminal_tool._task_env_overrides", {}),
        patch("tools.terminal_tool._active_environments", {}),
        patch("tools.terminal_tool._last_activity", {}),
        patch("tools.terminal_tool._creation_locks", {}),
        patch("tools.terminal_tool._creation_locks_lock", threading.Lock()),
        patch("tools.terminal_tool._create_environment", side_effect=fake_create_env),
        patch("tools.terminal_tool._start_cleanup_thread"),
    ):
        env, env_type = _get_or_create_env("review-task")

    assert env is mock_env
    assert env_type == "docker"
    assert captured["host_cwd"] == "/host/project"
    assert captured["container_config"] == {
        "container_cpu": 2,
        "container_memory": 4096,
        "container_disk": 20480,
        "container_persistent": False,
        "docker_volumes": [],
        "docker_mount_cwd_to_workspace": True,
        "docker_forward_env": ["API_KEY"],
        "docker_env": {"SAFE_FLAG": "1"},
        "docker_run_as_host_user": True,
        "docker_extra_args": ["--read-only"],
        "docker_network": False,
        "docker_persist_across_processes": False,
        "docker_orphan_reaper": False,
    }
