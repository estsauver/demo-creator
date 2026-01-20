"""
Kubernetes Job utilities for screenenv recording.

Handles creating and monitoring screenenv recording jobs in k8s.
"""

import os
import subprocess
import time
import json
from typing import Optional, Dict, Any
from pathlib import Path


class ScreenenvJobManager:
    """
    Manages screenenv recording jobs in Kubernetes.

    Creates Helm-based Jobs for isolated screen recordings.
    """

    def __init__(
        self,
        namespace: str = "infra",
        helm_chart_path: str = "k8s/infra/charts/screenenv-job",
        context: Optional[str] = None,
    ):
        """
        Initialize job manager.

        Args:
            namespace: Kubernetes namespace
            helm_chart_path: Path to screenenv-job Helm chart
            context: Kubernetes context (or set KUBE_CONTEXT env var, defaults to current context)
        """
        self.namespace = namespace
        self.helm_chart_path = helm_chart_path
        self.context = context or os.getenv("KUBE_CONTEXT")

    def _kubectl_cmd(self, *args) -> list:
        """Build kubectl command with optional context."""
        cmd = ["kubectl"] + list(args)
        if self.context:
            cmd.extend(["--context", self.context])
        cmd.extend(["--namespace", self.namespace])
        return cmd

    def create_job(
        self,
        demo_id: str,
        script_url: str,
        target_url: Optional[str] = None,
        resolution: str = "1920x1080",
        frame_rate: str = "30",
        timeout_minutes: int = 10,
    ) -> Dict[str, Any]:
        """
        Create a screenenv recording job.

        Args:
            demo_id: Demo identifier
            script_url: URL to the script YAML file
            target_url: Base URL of the application (or set DEMO_TARGET_URL env var)
            resolution: Video resolution (default: 1920x1080)
            frame_rate: Frame rate (default: 30)
            timeout_minutes: Job timeout in minutes

        Returns:
            Dict with job status
        """
        target_url = target_url or os.getenv("DEMO_TARGET_URL", "http://localhost:3000")
        release_name = f"screenenv-{demo_id}"

        # Install Helm chart
        cmd = [
            "helm", "install",
            release_name,
            self.helm_chart_path,
            "--namespace", self.namespace,
            "--set", f"demoId={demo_id}",
            "--set", f"scriptUrl={script_url}",
            "--set", f"targetUrl={target_url}",
            "--set", f"resolution={resolution}",
            "--set", f"frameRate={frame_rate}",
            "--wait",
            "--timeout", f"{timeout_minutes}m",
        ]
        if self.context:
            cmd.insert(3, "--kube-context")
            cmd.insert(4, self.context)

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            return {
                "status": "success",
                "release_name": release_name,
                "demo_id": demo_id,
            }

        except subprocess.CalledProcessError as e:
            return {
                "status": "failed",
                "error": e.stderr,
                "demo_id": demo_id,
            }

    def wait_for_completion(
        self,
        demo_id: str,
        poll_interval: int = 5,
        max_wait: int = 600,
    ) -> Dict[str, Any]:
        """
        Wait for a job to complete.

        Args:
            demo_id: Demo identifier
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait

        Returns:
            Dict with completion status
        """
        job_name = f"screenenv-{demo_id}"
        elapsed = 0

        while elapsed < max_wait:
            # Check job status
            cmd = self._kubectl_cmd("get", "job", job_name, "-o", "jsonpath={.status.succeeded}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.stdout == "1":
                return {
                    "status": "completed",
                    "demo_id": demo_id,
                }

            # Check for failures
            cmd_failed = self._kubectl_cmd("get", "job", job_name, "-o", "jsonpath={.status.failed}")

            result_failed = subprocess.run(
                cmd_failed,
                capture_output=True,
                text=True,
            )

            if result_failed.stdout and int(result_failed.stdout) > 0:
                # Get logs for debugging
                logs = self.get_job_logs(demo_id)

                return {
                    "status": "failed",
                    "demo_id": demo_id,
                    "logs": logs,
                }

            time.sleep(poll_interval)
            elapsed += poll_interval

        return {
            "status": "timeout",
            "demo_id": demo_id,
        }

    def get_job_logs(self, demo_id: str) -> str:
        """
        Get logs from a job pod.

        Args:
            demo_id: Demo identifier

        Returns:
            Job logs as string
        """
        job_name = f"screenenv-{demo_id}"

        cmd = self._kubectl_cmd("logs", f"job/{job_name}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        return result.stdout

    def retrieve_recording(
        self,
        demo_id: str,
        output_path: str,
    ) -> bool:
        """
        Retrieve recording from job's PVC.

        Args:
            demo_id: Demo identifier
            output_path: Local path to save recording

        Returns:
            True if successful
        """
        # Get pod name
        cmd_get_pod = self._kubectl_cmd(
            "get", "pods",
            "-l", f"job-name=screenenv-{demo_id}",
            "-o", "jsonpath={.items[0].metadata.name}",
        )

        result = subprocess.run(
            cmd_get_pod,
            capture_output=True,
            text=True,
        )

        pod_name = result.stdout.strip()
        if not pod_name:
            return False

        # Copy file from pod
        remote_path = f"/recordings/{demo_id}/raw_recording.mp4"

        cmd_cp = ["kubectl", "cp", f"{self.namespace}/{pod_name}:{remote_path}", output_path]
        if self.context:
            cmd_cp.extend(["--context", self.context])

        try:
            subprocess.run(cmd_cp, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def cleanup_job(self, demo_id: str) -> None:
        """
        Clean up a job and its resources.

        Args:
            demo_id: Demo identifier
        """
        release_name = f"screenenv-{demo_id}"

        cmd = ["helm", "uninstall", release_name, "--namespace", self.namespace]
        if self.context:
            cmd.extend(["--kube-context", self.context])

        subprocess.run(cmd, capture_output=True)


def create_and_run_recording(
    demo_id: str,
    script_url: str,
    output_path: str,
    target_url: Optional[str] = None,
    context: Optional[str] = None,
    cleanup: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to create a recording job, wait for completion,
    and retrieve the recording.

    Args:
        demo_id: Demo identifier
        script_url: URL to script YAML
        output_path: Local path to save recording
        target_url: Application URL (or set DEMO_TARGET_URL env var)
        context: Kubernetes context (or set KUBE_CONTEXT env var)
        cleanup: Whether to cleanup job after completion

    Returns:
        Dict with status and paths
    """
    manager = ScreenenvJobManager(context=context)

    # Create job
    create_result = manager.create_job(
        demo_id=demo_id,
        script_url=script_url,
        target_url=target_url,
    )

    if create_result["status"] != "success":
        return create_result

    # Wait for completion
    wait_result = manager.wait_for_completion(demo_id)

    if wait_result["status"] != "completed":
        return wait_result

    # Retrieve recording
    success = manager.retrieve_recording(demo_id, output_path)

    if not success:
        return {
            "status": "failed",
            "error": "Failed to retrieve recording",
            "demo_id": demo_id,
        }

    # Cleanup
    if cleanup:
        manager.cleanup_job(demo_id)

    return {
        "status": "success",
        "demo_id": demo_id,
        "recording_path": output_path,
    }
