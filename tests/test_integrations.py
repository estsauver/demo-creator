"""Tests for integration utilities."""

from unittest.mock import MagicMock, patch

import pytest

from utils.integrations import (
    DemoPublisher,
    GitHubIntegration,
    LinearIntegration,
    PostResult,
    SlackIntegration,
    post_demo,
)


class TestPostResult:
    """Tests for PostResult dataclass."""

    def test_success_result(self):
        """Should represent successful post."""
        result = PostResult(
            service="linear",
            status="success",
            url="https://linear.app/comment/123",
        )

        assert result.status == "success"
        assert result.url is not None

    def test_failed_result(self):
        """Should represent failed post."""
        result = PostResult(
            service="slack",
            status="failed",
            error="Webhook not found",
        )

        assert result.status == "failed"
        assert result.error == "Webhook not found"

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = PostResult(
            service="github",
            status="success",
            url="https://github.com/org/repo/pull/1#issuecomment-123",
        )

        d = result.to_dict()

        assert d["service"] == "github"
        assert d["status"] == "success"
        assert d["url"] is not None


class TestLinearIntegration:
    """Tests for LinearIntegration class."""

    def test_not_configured(self, monkeypatch):
        """Should report not configured without API key."""
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)

        integration = LinearIntegration()

        assert integration.is_configured() is False

    def test_configured(self, monkeypatch):
        """Should report configured with API key."""
        monkeypatch.setenv("LINEAR_API_KEY", "test_key")

        integration = LinearIntegration()

        assert integration.is_configured() is True

    def test_post_without_key(self, monkeypatch):
        """Should fail without API key."""
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)

        integration = LinearIntegration()
        result = integration.post_demo_link(
            issue_id="ISSUE-123",
            demo_url="https://example.com/demo.mp4",
        )

        assert result.status == "failed"
        assert "not configured" in result.error.lower()

    @patch("requests.post")
    def test_post_success(self, mock_post, monkeypatch):
        """Should post demo link successfully."""
        monkeypatch.setenv("LINEAR_API_KEY", "test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "commentCreate": {
                    "success": True,
                    "comment": {
                        "id": "comment-123",
                        "url": "https://linear.app/comment/123",
                    }
                }
            }
        }
        mock_post.return_value = mock_response

        integration = LinearIntegration()
        result = integration.post_demo_link(
            issue_id="ISSUE-123",
            demo_url="https://example.com/demo.mp4",
            demo_title="My Demo",
        )

        assert result.status == "success"
        assert result.url is not None
        mock_post.assert_called_once()


class TestSlackIntegration:
    """Tests for SlackIntegration class."""

    def test_not_configured(self, monkeypatch):
        """Should report not configured without webhook."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        integration = SlackIntegration()

        assert integration.is_configured() is False

    def test_configured(self, monkeypatch):
        """Should report configured with webhook."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/...")

        integration = SlackIntegration()

        assert integration.is_configured() is True

    def test_post_without_webhook(self, monkeypatch):
        """Should fail without webhook URL."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        integration = SlackIntegration()
        result = integration.post_demo_link(
            demo_url="https://example.com/demo.mp4",
        )

        assert result.status == "failed"
        assert "not configured" in result.error.lower()

    @patch("requests.post")
    def test_post_success(self, mock_post, monkeypatch):
        """Should post demo link successfully."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        integration = SlackIntegration()
        result = integration.post_demo_link(
            demo_url="https://example.com/demo.mp4",
            demo_title="My Demo",
            description="Check out this demo!",
        )

        assert result.status == "success"
        mock_post.assert_called_once()


class TestGitHubIntegration:
    """Tests for GitHubIntegration class."""

    def test_not_configured(self, monkeypatch):
        """Should report not configured without token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        integration = GitHubIntegration()

        assert integration.is_configured() is False

    def test_configured(self, monkeypatch):
        """Should report configured with token."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        integration = GitHubIntegration()

        assert integration.is_configured() is True

    def test_post_without_token(self, monkeypatch):
        """Should fail without GitHub token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        integration = GitHubIntegration()
        result = integration.post_demo_link(
            repo="org/repo",
            pr_number=123,
            demo_url="https://example.com/demo.mp4",
        )

        assert result.status == "failed"
        assert "not configured" in result.error.lower()

    @patch("requests.post")
    def test_post_success(self, mock_post, monkeypatch):
        """Should post demo link successfully."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 123,
            "html_url": "https://github.com/org/repo/pull/1#issuecomment-123",
        }
        mock_post.return_value = mock_response

        integration = GitHubIntegration()
        result = integration.post_demo_link(
            repo="org/repo",
            pr_number=1,
            demo_url="https://example.com/demo.mp4",
            demo_title="My Demo",
        )

        assert result.status == "success"
        assert result.url is not None
        mock_post.assert_called_once()


class TestDemoPublisher:
    """Tests for DemoPublisher class."""

    def test_publish_to_configured_services(self, monkeypatch):
        """Should publish to configured services only."""
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        publisher = DemoPublisher()
        results = publisher.publish(
            demo_url="https://example.com/demo.mp4",
        )

        # No services configured, no results
        assert len(results) == 0

    @patch("requests.post")
    def test_publish_to_slack(self, mock_post, monkeypatch):
        """Should publish to Slack when configured."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        publisher = DemoPublisher()
        results = publisher.publish(
            demo_url="https://example.com/demo.mp4",
            demo_title="Test Demo",
        )

        assert "slack" in results
        assert results["slack"].status == "success"


class TestPostDemo:
    """Tests for post_demo convenience function."""

    def test_creates_publisher(self, monkeypatch):
        """Should use DemoPublisher internally."""
        monkeypatch.delenv("LINEAR_API_KEY", raising=False)
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        results = post_demo(
            demo_url="https://example.com/demo.mp4",
        )

        # No services configured
        assert len(results) == 0
