"""Tests for graceful recording utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.graceful_recorder import (
    GracefulRecorder,
    RecordingStrategy,
    check_kubernetes_available,
    get_recommended_strategy,
    record_demo,
)
from utils.local_recorder import RecordingResult


class TestRecordingStrategy:
    """Tests for RecordingStrategy dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        strategy = RecordingStrategy()

        assert strategy.prefer_kubernetes is False
        assert strategy.fallback_to_local is True
        assert strategy.kubernetes_namespace == "infra"
        assert strategy.kubernetes_timeout == 600

    def test_custom_values(self):
        """Should accept custom values."""
        strategy = RecordingStrategy(
            prefer_kubernetes=True,
            fallback_to_local=False,
            kubernetes_namespace="prod",
            kubernetes_timeout=1200,
        )

        assert strategy.prefer_kubernetes is True
        assert strategy.fallback_to_local is False
        assert strategy.kubernetes_namespace == "prod"
        assert strategy.kubernetes_timeout == 1200


class TestGracefulRecorder:
    """Tests for GracefulRecorder class."""

    def test_init_with_defaults(self):
        """Should initialize with default strategy."""
        recorder = GracefulRecorder()

        assert recorder.strategy is not None
        assert recorder.strategy.prefer_kubernetes is False

    def test_init_with_custom_strategy(self):
        """Should accept custom strategy."""
        strategy = RecordingStrategy(prefer_kubernetes=True)
        recorder = GracefulRecorder(strategy=strategy)

        assert recorder.strategy.prefer_kubernetes is True

    @patch("utils.graceful_recorder.LocalRecorder")
    def test_local_recording(self, mock_local_recorder_class, tmp_path):
        """Should use local recording when kubernetes not preferred."""
        mock_recorder = MagicMock()
        mock_recorder.record_script.return_value = RecordingResult(
            status="success",
            video_path=tmp_path / "video.webm",
        )
        mock_local_recorder_class.return_value = mock_recorder

        recorder = GracefulRecorder()
        result = recorder.record(
            script_path=tmp_path / "script.py",
            output_dir=tmp_path,
        )

        assert result.status == "success"
        mock_recorder.record_script.assert_called_once()

    @patch("utils.graceful_recorder.LocalRecorder")
    def test_fallback_to_local_on_k8s_failure(self, mock_local_recorder_class, tmp_path):
        """Should fall back to local when K8s fails."""
        mock_recorder = MagicMock()
        mock_recorder.record_script.return_value = RecordingResult(
            status="success",
            video_path=tmp_path / "video.webm",
        )
        mock_local_recorder_class.return_value = mock_recorder

        strategy = RecordingStrategy(
            prefer_kubernetes=True,
            fallback_to_local=True,
        )
        recorder = GracefulRecorder(strategy=strategy)

        # K8s will fail because screenenv_job isn't importable in test
        result = recorder.record(
            script_path=tmp_path / "script.py",
            output_dir=tmp_path,
        )

        # Should have fallen back to local
        assert result.status == "success"
        mock_recorder.record_script.assert_called_once()

    def test_no_fallback_when_disabled(self, tmp_path):
        """Should not fall back when fallback is disabled."""
        strategy = RecordingStrategy(
            prefer_kubernetes=True,
            fallback_to_local=False,
        )
        recorder = GracefulRecorder(strategy=strategy)

        result = recorder.record(
            script_path=tmp_path / "script.py",
            output_dir=tmp_path,
        )

        # Should fail without fallback
        assert result.status == "failed"

    @patch("utils.graceful_recorder.LocalRecorder")
    def test_validate_uses_local(self, mock_local_recorder_class, tmp_path):
        """Should always use local for validation."""
        mock_recorder = MagicMock()
        mock_recorder.validate_script.return_value = RecordingResult(
            status="success",
        )
        mock_local_recorder_class.return_value = mock_recorder

        strategy = RecordingStrategy(prefer_kubernetes=True)
        recorder = GracefulRecorder(strategy=strategy)

        result = recorder.validate(
            script_path=tmp_path / "script.py",
            base_url="http://localhost:3000",
        )

        assert result.status == "success"
        mock_recorder.validate_script.assert_called_once()


class TestRecordDemo:
    """Tests for record_demo convenience function."""

    @patch("utils.graceful_recorder.GracefulRecorder")
    def test_creates_recorder(self, mock_recorder_class, tmp_path):
        """Should create GracefulRecorder internally."""
        mock_recorder = MagicMock()
        mock_recorder.record.return_value = RecordingResult(status="success")
        mock_recorder_class.return_value = mock_recorder

        record_demo(
            script_path=tmp_path / "script.py",
            output_dir=tmp_path,
        )

        mock_recorder_class.assert_called_once()
        mock_recorder.record.assert_called_once()

    @patch("utils.graceful_recorder.GracefulRecorder")
    def test_passes_kubernetes_preference(self, mock_recorder_class, tmp_path):
        """Should pass kubernetes preference."""
        mock_recorder = MagicMock()
        mock_recorder.record.return_value = RecordingResult(status="success")
        mock_recorder_class.return_value = mock_recorder

        record_demo(
            script_path=tmp_path / "script.py",
            output_dir=tmp_path,
            prefer_kubernetes=True,
        )

        call_args = mock_recorder_class.call_args
        strategy = call_args[0][0]
        assert strategy.prefer_kubernetes is True


class TestCheckKubernetesAvailable:
    """Tests for check_kubernetes_available function."""

    @patch("subprocess.run")
    def test_returns_true_when_available(self, mock_run):
        """Should return True when kubectl succeeds."""
        mock_run.return_value = MagicMock(returncode=0)

        result = check_kubernetes_available()

        assert result is True

    @patch("subprocess.run")
    def test_returns_false_when_unavailable(self, mock_run):
        """Should return False when kubectl fails."""
        mock_run.return_value = MagicMock(returncode=1)

        result = check_kubernetes_available()

        assert result is False

    @patch("subprocess.run")
    def test_returns_false_on_exception(self, mock_run):
        """Should return False on exception."""
        mock_run.side_effect = Exception("kubectl not found")

        result = check_kubernetes_available()

        assert result is False


class TestGetRecommendedStrategy:
    """Tests for get_recommended_strategy function."""

    @patch("utils.graceful_recorder.check_kubernetes_available")
    def test_prefers_k8s_when_available(self, mock_check):
        """Should prefer K8s when available."""
        mock_check.return_value = True

        strategy = get_recommended_strategy()

        assert strategy.prefer_kubernetes is True
        assert strategy.fallback_to_local is True

    @patch("utils.graceful_recorder.check_kubernetes_available")
    def test_uses_local_when_k8s_unavailable(self, mock_check):
        """Should use local when K8s unavailable."""
        mock_check.return_value = False

        strategy = get_recommended_strategy()

        assert strategy.prefer_kubernetes is False
        assert strategy.fallback_to_local is True
