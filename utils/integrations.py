"""
Integration utilities for posting demos to external services.

Supports Linear, Slack, and GitHub integrations.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class PostResult:
    """Result of posting to an external service."""

    service: str
    status: str  # success, failed
    url: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "status": self.status,
            "url": self.url,
            "error": self.error,
        }


class LinearIntegration:
    """
    Posts demo links to Linear issues.

    Uses the Linear API to add comments with demo URLs.
    """

    BASE_URL = "https://api.linear.app/graphql"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Linear integration.

        Args:
            api_key: Linear API key (defaults to LINEAR_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("LINEAR_API_KEY")

    def is_configured(self) -> bool:
        """Check if Linear is configured."""
        return bool(self.api_key)

    def post_demo_link(
        self,
        issue_id: str,
        demo_url: str,
        demo_title: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
    ) -> PostResult:
        """
        Post a demo link as a comment on a Linear issue.

        Args:
            issue_id: Linear issue ID (e.g., "ISSUE-123")
            demo_url: URL to the demo video
            demo_title: Optional title for the demo
            thumbnail_url: Optional thumbnail image URL

        Returns:
            PostResult
        """
        if not self.api_key:
            return PostResult(
                service="linear",
                status="failed",
                error="LINEAR_API_KEY not configured",
            )

        # Build comment body
        title = demo_title or "Demo Video"
        body = f"🎬 **{title}**\n\n"
        body += f"[Watch Demo]({demo_url})\n"

        if thumbnail_url:
            body += f"\n![Demo Thumbnail]({thumbnail_url})"

        # GraphQL mutation
        mutation = """
        mutation CreateComment($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
                comment {
                    id
                    url
                }
            }
        }
        """

        try:
            response = requests.post(
                self.BASE_URL,
                headers={
                    "Authorization": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "query": mutation,
                    "variables": {
                        "issueId": issue_id,
                        "body": body,
                    },
                },
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            if data.get("data", {}).get("commentCreate", {}).get("success"):
                comment_url = data["data"]["commentCreate"]["comment"].get("url")
                return PostResult(
                    service="linear",
                    status="success",
                    url=comment_url,
                )
            else:
                errors = data.get("errors", [])
                error_msg = errors[0]["message"] if errors else "Unknown error"
                return PostResult(
                    service="linear",
                    status="failed",
                    error=error_msg,
                )

        except Exception as e:
            logger.exception("Failed to post to Linear")
            return PostResult(
                service="linear",
                status="failed",
                error=str(e),
            )


class SlackIntegration:
    """
    Posts demo links to Slack channels.

    Uses Slack incoming webhooks for posting.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack integration.

        Args:
            webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def is_configured(self) -> bool:
        """Check if Slack is configured."""
        return bool(self.webhook_url)

    def post_demo_link(
        self,
        demo_url: str,
        demo_title: Optional[str] = None,
        description: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> PostResult:
        """
        Post a demo link to Slack.

        Args:
            demo_url: URL to the demo video
            demo_title: Optional title for the demo
            description: Optional description
            thumbnail_url: Optional thumbnail image URL
            channel: Optional channel override (webhook default used if not specified)

        Returns:
            PostResult
        """
        if not self.webhook_url:
            return PostResult(
                service="slack",
                status="failed",
                error="SLACK_WEBHOOK_URL not configured",
            )

        title = demo_title or "New Demo Video"

        # Build Slack message with blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎬 {title}",
                    "emoji": True,
                },
            },
        ]

        if description:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": description,
                },
            })

        # Add demo link button
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Watch Demo",
                        "emoji": True,
                    },
                    "url": demo_url,
                    "style": "primary",
                },
            ],
        })

        # Add thumbnail if provided
        if thumbnail_url:
            blocks.append({
                "type": "image",
                "image_url": thumbnail_url,
                "alt_text": "Demo thumbnail",
            })

        payload = {"blocks": blocks}
        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

            return PostResult(
                service="slack",
                status="success",
            )

        except Exception as e:
            logger.exception("Failed to post to Slack")
            return PostResult(
                service="slack",
                status="failed",
                error=str(e),
            )


class GitHubIntegration:
    """
    Posts demo links to GitHub PRs or issues.

    Uses the GitHub API to add comments.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub integration.

        Args:
            token: GitHub token (defaults to GITHUB_TOKEN env var)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")

    def is_configured(self) -> bool:
        """Check if GitHub is configured."""
        return bool(self.token)

    def post_demo_link(
        self,
        repo: str,
        pr_number: int,
        demo_url: str,
        demo_title: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
    ) -> PostResult:
        """
        Post a demo link as a comment on a GitHub PR.

        Args:
            repo: Repository in format "owner/repo"
            pr_number: PR number
            demo_url: URL to the demo video
            demo_title: Optional title for the demo
            thumbnail_url: Optional thumbnail image URL

        Returns:
            PostResult
        """
        if not self.token:
            return PostResult(
                service="github",
                status="failed",
                error="GITHUB_TOKEN not configured",
            )

        title = demo_title or "Demo Video"

        # Build comment body
        body = f"## 🎬 {title}\n\n"
        body += f"**[Watch Demo]({demo_url})**\n"

        if thumbnail_url:
            body += f"\n[![Demo Thumbnail]({thumbnail_url})]({demo_url})"

        body += "\n\n---\n*Generated by demo-creator*"

        try:
            response = requests.post(
                f"{self.BASE_URL}/repos/{repo}/issues/{pr_number}/comments",
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={"body": body},
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            return PostResult(
                service="github",
                status="success",
                url=data.get("html_url"),
            )

        except Exception as e:
            logger.exception("Failed to post to GitHub")
            return PostResult(
                service="github",
                status="failed",
                error=str(e),
            )


class DemoPublisher:
    """
    Publishes demo links to configured integrations.

    Handles posting to multiple services based on configuration.
    """

    def __init__(
        self,
        linear_api_key: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        github_token: Optional[str] = None,
    ):
        """
        Initialize demo publisher.

        Args:
            linear_api_key: Linear API key
            slack_webhook_url: Slack webhook URL
            github_token: GitHub token
        """
        self.linear = LinearIntegration(linear_api_key)
        self.slack = SlackIntegration(slack_webhook_url)
        self.github = GitHubIntegration(github_token)

    def publish(
        self,
        demo_url: str,
        demo_title: Optional[str] = None,
        description: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        linear_issue_id: Optional[str] = None,
        slack_channel: Optional[str] = None,
        github_repo: Optional[str] = None,
        github_pr: Optional[int] = None,
    ) -> Dict[str, PostResult]:
        """
        Publish demo to all configured integrations.

        Args:
            demo_url: URL to the demo video
            demo_title: Optional title
            description: Optional description
            thumbnail_url: Optional thumbnail
            linear_issue_id: Linear issue ID to post to
            slack_channel: Slack channel override
            github_repo: GitHub repo (owner/repo)
            github_pr: GitHub PR number

        Returns:
            Dict mapping service name to PostResult
        """
        results = {}

        # Post to Linear
        if linear_issue_id and self.linear.is_configured():
            results["linear"] = self.linear.post_demo_link(
                issue_id=linear_issue_id,
                demo_url=demo_url,
                demo_title=demo_title,
                thumbnail_url=thumbnail_url,
            )

        # Post to Slack
        if self.slack.is_configured():
            results["slack"] = self.slack.post_demo_link(
                demo_url=demo_url,
                demo_title=demo_title,
                description=description,
                thumbnail_url=thumbnail_url,
                channel=slack_channel,
            )

        # Post to GitHub
        if github_repo and github_pr and self.github.is_configured():
            results["github"] = self.github.post_demo_link(
                repo=github_repo,
                pr_number=github_pr,
                demo_url=demo_url,
                demo_title=demo_title,
                thumbnail_url=thumbnail_url,
            )

        return results


def post_demo(
    demo_url: str,
    demo_title: Optional[str] = None,
    linear_issue_id: Optional[str] = None,
    slack_channel: Optional[str] = None,
    github_repo: Optional[str] = None,
    github_pr: Optional[int] = None,
) -> Dict[str, PostResult]:
    """
    Convenience function to post demo to all configured integrations.

    Args:
        demo_url: URL to the demo video
        demo_title: Optional title
        linear_issue_id: Linear issue ID
        slack_channel: Slack channel
        github_repo: GitHub repo
        github_pr: GitHub PR number

    Returns:
        Dict mapping service name to PostResult
    """
    publisher = DemoPublisher()
    return publisher.publish(
        demo_url=demo_url,
        demo_title=demo_title,
        linear_issue_id=linear_issue_id,
        slack_channel=slack_channel,
        github_repo=github_repo,
        github_pr=github_pr,
    )
