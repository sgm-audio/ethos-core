"""
Ray Cluster Infrastructure for Multi-Agent Audio Processing System (MAAPS)

This module sets up and manages a Ray cluster for distributed agent execution,
even on a single machine. Ray provides actor-based concurrency, task scheduling,
and resource management for our multi-agent system.
"""

import logging
from typing import Any

import psutil
import ray

logger = logging.getLogger(__name__)


class RayClusterManager:
    """
    Manages Ray cluster initialization, health monitoring, and shutdown.
    Optimized for both single-machine and distributed deployment.
    """

    def __init__(
        self,
        num_cpus: int | None = None,
        num_gpus: int | None = None,
        memory: int | None = None,
        object_store_memory: int | None = None,
        dashboard_host: str = "127.0.0.1",
        dashboard_port: int = 8265,
        enable_logging: bool = True,
    ):
        """
        Initialize Ray cluster manager.

        Args:
            num_cpus: Number of CPUs to allocate (defaults to system CPUs - 1)
            num_gpus: Number of GPUs to allocate (defaults to 0)
            memory: Memory in bytes (defaults to 80% of system memory)
            object_store_memory: Object store memory (defaults to 30% of system memory)
            dashboard_host: Ray dashboard host
            dashboard_port: Ray dashboard port
            enable_logging: Enable detailed logging
        """
        self.num_cpus = num_cpus or max(1, psutil.cpu_count() - 1)
        self.num_gpus = num_gpus or 0

        # Calculate memory defaults
        total_memory = psutil.virtual_memory().total
        self.memory = memory or int(total_memory * 0.8)
        self.object_store_memory = object_store_memory or int(total_memory * 0.3)

        self.dashboard_host = dashboard_host
        self.dashboard_port = dashboard_port
        self.enable_logging = enable_logging
        self.is_initialized = False

    def initialize(self, address: str | None = None) -> bool:
        """
        Initialize Ray cluster.

        Args:
            address: Ray cluster address (None for local cluster, "auto" for existing cluster)

        Returns:
            bool: True if initialization successful
        """
        if self.is_initialized:
            logger.warning("Ray cluster already initialized")
            return True

        try:
            ray_init_kwargs = {
                "ignore_reinit_error": True,
                "logging_level": logging.INFO if self.enable_logging else logging.WARNING,
                "dashboard_host": self.dashboard_host,
                "dashboard_port": self.dashboard_port,
            }

            if address is None:
                # Start local cluster
                ray_init_kwargs.update(
                    {
                        "num_cpus": self.num_cpus,
                        "num_gpus": self.num_gpus,
                        "object_store_memory": self.object_store_memory,
                        "_memory": self.memory,
                    }
                )
                logger.info(
                    f"Starting local Ray cluster: {self.num_cpus} CPUs, {self.num_gpus} GPUs"
                )
            else:
                # Connect to existing cluster
                ray_init_kwargs["address"] = address
                logger.info(f"Connecting to Ray cluster at {address}")

            ray.init(**ray_init_kwargs)
            self.is_initialized = True

            # Log cluster resources
            resources = ray.cluster_resources()
            logger.info("Ray cluster initialized successfully")
            logger.info(f"Available resources: {resources}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Ray cluster: {e}")
            return False

    def get_cluster_info(self) -> dict[str, Any]:
        """Get current cluster resource information."""
        if not self.is_initialized:
            return {"error": "Cluster not initialized"}

        return {
            "cluster_resources": ray.cluster_resources(),
            "available_resources": ray.available_resources(),
            "nodes": ray.nodes(),
            "dashboard_url": f"http://{self.dashboard_host}:{self.dashboard_port}",
        }

    def health_check(self) -> bool:
        """Check if Ray cluster is healthy."""
        try:
            return self.is_initialized and ray.is_initialized()
        except Exception:
            return False

    def shutdown(self):
        """Shutdown Ray cluster gracefully."""
        if self.is_initialized:
            logger.info("Shutting down Ray cluster...")
            ray.shutdown()
            self.is_initialized = False
            logger.info("Ray cluster shutdown complete")

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


@ray.remote
class ResourceMonitor:
    """
    Ray actor for monitoring cluster resource usage in real-time.
    Useful for load balancing and preventing resource exhaustion.
    """

    def __init__(self):
        self.monitoring = False

    def get_resources(self) -> dict[str, Any]:
        """Get current resource utilization."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "ray_cluster": ray.cluster_resources(),
            "ray_available": ray.available_resources(),
        }

    def is_resource_available(self, required_cpus: float = 1.0) -> bool:
        """Check if sufficient resources are available for new task."""
        available = ray.available_resources()
        return available.get("CPU", 0) >= required_cpus


def get_or_create_cluster(
    num_cpus: int | None = None, num_gpus: int | None = None, address: str | None = None
) -> RayClusterManager:
    """
    Convenience function to get or create Ray cluster.

    Args:
        num_cpus: Number of CPUs
        num_gpus: Number of GPUs
        address: Cluster address (None for local)

    Returns:
        RayClusterManager instance
    """
    manager = RayClusterManager(num_cpus=num_cpus, num_gpus=num_gpus)
    manager.initialize(address=address)
    return manager


def create_actor_pool(actor_class, num_actors: int, *args, **kwargs) -> list:
    """
    Create a pool of Ray actors for parallel processing.

    Args:
        actor_class: Ray actor class
        num_actors: Number of actors to create
        *args, **kwargs: Arguments for actor constructor

    Returns:
        List of actor handles
    """
    return [actor_class.remote(*args, **kwargs) for _ in range(num_actors)]


# Singleton instance for global access
_cluster_instance: RayClusterManager | None = None


def get_cluster() -> RayClusterManager | None:
    """Get the global cluster instance."""
    return _cluster_instance


def set_cluster(cluster: RayClusterManager):
    """Set the global cluster instance."""
    global _cluster_instance
    _cluster_instance = cluster


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Create and initialize cluster
    with RayClusterManager(num_cpus=4, num_gpus=0) as cluster:
        print("Cluster Info:", cluster.get_cluster_info())

        # Create resource monitor
        monitor = ResourceMonitor.remote()
        resources = ray.get(monitor.get_resources.remote())
        print("Resources:", resources)

        # Simple test task
        @ray.remote
        def test_task(x):
            return x * x

        # Run parallel tasks
        results = ray.get([test_task.remote(i) for i in range(10)])
        print("Test results:", results)
