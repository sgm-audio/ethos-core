"""
Unit tests for ethos.agents.infra:
- RayClusterManager configuration, resource calculation, and management.
"""

import psutil

from ethos.agents.infra.ray_cluster import RayClusterManager


def test_ray_cluster_manager_defaults():
    """Verify RayClusterManager CPU/Memory resource calculations."""
    manager = RayClusterManager(num_cpus=2, num_gpus=0, enable_logging=False)
    assert manager.num_cpus == 2
    assert manager.num_gpus == 0
    assert manager.memory > 0
    assert manager.object_store_memory > 0
    assert manager.is_initialized is False


def test_ray_cluster_auto_detection():
    """Verify dynamic system resource detection."""
    manager = RayClusterManager()
    system_cpus = psutil.cpu_count()
    assert manager.num_cpus == max(1, system_cpus - 1)
    assert manager.is_initialized is False
