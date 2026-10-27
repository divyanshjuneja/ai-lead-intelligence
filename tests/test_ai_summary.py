"""Tests for AI summary generation (Option A).

These tests never touch the network: HTTP calls are replaced with fakes, and
error paths are simulated directly. The point is to verify prompt content,
response parsing, key lookup, and graceful failure via `AiSummaryError`.
"""

import pytest
import requests

from lead_intel import ai_summary
from lead_intel.models import CompanyInput, IcpCriteria
from lead_intel.scoring import assess_lead


def make_company_and_result():
    company = CompanyInput(
        company_name="Acme Corp",
        industry="Software",
        employee_count=200,
        description="Builds an api platform for developer teams.",
    )
    icp = IcpCriteria(
        icp_industries=["Software"], icp_min_employees=50,
        icp_keywords=["api"],
    )
    return company, assess_lead(company, icp)


class TestBuildPrompt:
    def test_prompt_contains_company_and_rule_facts(self):
        company, result = make_company_and_result()
        prompt = ai_summary.build_prompt(company, result)
        assert "Acme Corp" in prompt
        assert "Software" in prompt
        assert result.classification in prompt
        assert "Industry match" in prompt
        assert company.description in prompt

    def test_prompt_reports_missing_description(self):
        company = CompanyInput(
            company_name="Acme Corp", industry="Software", employee_count=200
        )
        icp = IcpCriteria(icp_industries=["Software"])
        prompt = ai_summary.build_prompt(company, assess_lead(company, icp))
        assert "(not provided)" in prompt


class TestExtractText:
    def test_extracts_text_from_valid_payload(self):
        payload = {
            "candidates": [{"content": {"parts": [{"text": " Looks good. "}]}}]
        }
        assert ai_summary._extract_text(payload) == "Looks good."

    def test_joins_multiple_text_parts(self):
        payload = {
            "candidates": [
                {"content": {"parts": [{"text": "Part one."}, {"text": "Part two."}]}}
            ]
        }
        assert ai_summary._extract_text(payload) == "Part one.Part two."

    def test_blocked_or_empty_candidates_raise(self):
        with pytest.raises(ai_summary.AiSummaryError):
            ai_summary._extract_text({"candidates": [{"content": {"parts": []}}]})
        with pytest.raises(ai_summary.AiSummaryError):
            ai_summary._extract_text({"candidates": []})
        with pytest.raises(ai_summary.AiSummaryError):
            ai_summary._extract_text({})


class TestPerformRequest:
    def test_network_error_raises_ai_summary_error(self, monkeypatch):
        def boom(*args, **kwargs):
            raise requests.ConnectionError("no internet")

        monkeypatch.setattr(ai_summary.requests, "post", boom)
        with pytest.raises(ai_summary.AiSummaryError, match="request failed"):
            ai_summary._perform_request(
                "prompt", "key", "gemini-x", timeout=1, attempts=1
            )

    def test_http_error_status_raises_ai_summary_error(self, monkeypatch):
        class FakeResponse:
            def raise_for_status(self):
                raise requests.HTTPError("401 Unauthorized")

            def json(self):  # pragma: no cover - raise happens first
                return {}

        monkeypatch.setattr(ai_summary.requests, "post", lambda *a, **k: FakeResponse())
        with pytest.raises(ai_summary.AiSummaryError, match="request failed"):
            ai_summary._perform_request(
                "prompt", "bad-key", "gemini-x", timeout=1, attempts=1
            )

    def test_transient_failure_is_retried_and_recovers(self, monkeypatch):
        """First call 503s, second succeeds -> the retry returns the payload."""
        calls = {"count": 0}
        sleeps = []

        def flaky_post(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise requests.HTTPError("503 Service Unavailable")

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

            return Response()

        monkeypatch.setattr(ai_summary.requests, "post", flaky_post)
        monkeypatch.setattr(ai_summary.time, "sleep", sleeps.append)
        payload = ai_summary._perform_request(
            "prompt", "key", "gemini-x", timeout=1, attempts=3
        )
        assert calls["count"] == 2
        assert sleeps == [ai_summary.RETRY_PAUSE_SECONDS]
        assert ai_summary._extract_text(payload) == "ok"


class TestGenerateSummary:
    def test_post_to_gemini_composes_request(self, monkeypatch):
        company, result = make_company_and_result()
        captured = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            captured.update(url=url, headers=headers, json=json, timeout=timeout)

            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "candidates": [
                            {"content": {"parts": [{"text": "summary text"}]}}
                        ]
                    }

            return Response()

        monkeypatch.setattr(ai_summary.requests, "post", fake_post)
        summary = ai_summary.generate_summary(company, result, api_key="secret")
        assert summary == "summary text"
        assert captured["headers"]["x-goog-api-key"] == "secret"
        assert "Acme Corp" in captured["json"]["contents"][0]["parts"][0]["text"]


class TestGetApiKey:
    def _clear_env(self, monkeypatch):
        for name in ai_summary.API_KEY_ENV_VARS:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(ai_summary, "load_dotenv", lambda *a, **k: None)

    def test_missing_key_returns_none(self, monkeypatch):
        self._clear_env(monkeypatch)
        assert ai_summary.get_api_key() is None

    def test_key_found_and_trimmed(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("GEMINI_API_KEY", "  test-key  ")
        assert ai_summary.get_api_key() == "test-key"

    def test_fallback_to_google_api_key_name(self, monkeypatch):
        self._clear_env(monkeypatch)
        monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
        assert ai_summary.get_api_key() == "google-key"
