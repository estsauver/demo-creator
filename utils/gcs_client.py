"""
Google Cloud Storage client for demo video uploads.

Handles uploading final demo videos and metadata to GCS bucket.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False


class GCSUploader:
    """
    Handles uploading demo videos and metadata to Google Cloud Storage.

    Bucket structure: gs://{bucket}/YYYY-MM-DD/{issue}-{branch}-{timestamp}.mp4
    """

    def __init__(self, credentials_path: Optional[str] = None, bucket_name: Optional[str] = None):
        """
        Initialize GCS client.

        Args:
            credentials_path: Path to service account JSON (defaults to env var)
            bucket_name: GCS bucket name (required, or set GCS_BUCKET_NAME env var)
        """
        import os
        bucket_name = bucket_name or os.getenv("GCS_BUCKET_NAME")
        if not bucket_name:
            raise ValueError(
                "GCS bucket name required. Set GCS_BUCKET_NAME env var "
                "or pass bucket_name parameter."
            )
        if not GCS_AVAILABLE:
            raise ImportError(
                "google-cloud-storage package not installed. "
                "Install with: pip install google-cloud-storage"
            )

        if credentials_path:
            self.client = storage.Client.from_service_account_json(credentials_path)
        else:
            # Uses GOOGLE_APPLICATION_CREDENTIALS env var
            self.client = storage.Client()

        self.bucket = self.client.bucket(bucket_name)
        self.bucket_name = bucket_name

    def upload_demo(
        self,
        video_path: str,
        manifest: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Upload a demo video and its metadata to GCS.

        Args:
            video_path: Local path to the final demo video
            manifest: Complete manifest data

        Returns:
            Dict with 'video_url' and 'metadata_url'
        """
        # Extract metadata from manifest
        date_prefix = manifest["created_at"][:10]  # YYYY-MM-DD
        timestamp = int(time.time())

        # Construct filename
        linear_issue = manifest.get("linear_issue", "unknown")
        git_branch = manifest.get("git_branch", "unknown").replace("/", "-")
        filename = f"{linear_issue}-{git_branch}-{timestamp}"

        # Upload video
        video_blob_name = f"{date_prefix}/{filename}.mp4"
        video_url = self._upload_video(video_path, video_blob_name)

        # Create and upload metadata
        metadata = self._create_metadata(manifest, video_url)
        metadata_blob_name = f"{date_prefix}/{filename}.metadata.json"
        metadata_url = self._upload_metadata(metadata, metadata_blob_name)

        return {
            "video_url": video_url,
            "metadata_url": metadata_url,
        }

    def _upload_video(self, local_path: str, blob_name: str) -> str:
        """
        Upload video file to GCS.

        Args:
            local_path: Local file path
            blob_name: GCS blob name (path in bucket)

        Returns:
            Public URL to the video
        """
        blob = self.bucket.blob(blob_name)

        # Upload with content type
        blob.upload_from_filename(
            local_path,
            content_type="video/mp4",
        )

        # Set cache control (1 year)
        blob.cache_control = "public, max-age=31536000"
        blob.patch()

        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"

    def _upload_metadata(self, metadata: Dict[str, Any], blob_name: str) -> str:
        """
        Upload metadata JSON to GCS.

        Args:
            metadata: Metadata dictionary
            blob_name: GCS blob name

        Returns:
            Public URL to the metadata file
        """
        blob = self.bucket.blob(blob_name)

        # Upload as JSON
        blob.upload_from_string(
            json.dumps(metadata, indent=2),
            content_type="application/json",
        )

        return f"https://storage.googleapis.com/{self.bucket_name}/{blob_name}"

    def _create_metadata(self, manifest: Dict[str, Any], video_url: str) -> Dict[str, Any]:
        """
        Create metadata file from manifest.

        Args:
            manifest: Complete manifest data
            video_url: URL to the uploaded video

        Returns:
            Metadata dictionary
        """
        # Extract scene information from script
        stage_2_output = manifest.get("stage_outputs", {}).get("2", {})
        stage_4_output = manifest.get("stage_outputs", {}).get("4", {})

        # Build scenes array
        scenes = []
        if "scene_timings" in stage_4_output:
            for timing in stage_4_output["scene_timings"]:
                scenes.append({
                    "id": timing["scene"],
                    "start": timing["start"],
                    "end": timing["end"],
                })

        return {
            "demo_id": manifest["demo_id"],
            "linear_issue": manifest.get("linear_issue"),
            "git_branch": manifest.get("git_branch"),
            "git_sha": manifest.get("git_sha"),
            "created_at": manifest["created_at"],
            "duration_seconds": stage_4_output.get("actual_duration_seconds"),
            "scenes": scenes,
            "video_url": video_url,
            "created_by": "demo-creator-agent",
        }


def upload_demo_to_gcs(
    video_path: str,
    manifest: Dict[str, Any],
    credentials_path: Optional[str] = None,
    bucket_name: Optional[str] = None,
) -> Dict[str, str]:
    """
    Convenience function to upload a demo to GCS.

    Args:
        video_path: Local path to video file
        manifest: Complete manifest data
        credentials_path: Optional path to GCS credentials
        bucket_name: GCS bucket name (or set GCS_BUCKET_NAME env var)

    Returns:
        Dict with 'video_url' and 'metadata_url'
    """
    uploader = GCSUploader(credentials_path=credentials_path, bucket_name=bucket_name)
    return uploader.upload_demo(video_path, manifest)
