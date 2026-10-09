"""Focused tests for optional Gemini assessment and evidence validation."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from modules.gemini_assessor import assess_unresolved_with_gemini


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.models = self
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"text": json.dumps(self.response)})()


def _inputs():
    reqs = [{"id": "R01", "text": "The bidder shall provide a technical plan.", "category": "Technical"}]
    candidates = {"R01": [{"document": "bid.pdf", "page": 2, "text": "Technical plan attached.", "score": 0.42}]}
    results = [{"req_id": "R01", "status": "Needs Manual Review", "reason": "Requires a person.",
                "document": "bid.pdf", "evidence_page": 2, "evidence": "Technical plan attached.",
                "evidence_strength": 0.42}]
    return reqs, candidates, results


def test_gemini_assesses_only_manual_review_and_uses_source_evidence():
    reqs, candidates, results = _inputs()
    client = FakeClient({"assessments": [{"req_id": "R01", "status": "Compliant",
                                         "reason": "The submitted plan addresses this requirement.",
                                         "evidence_index": 0}]})
    updated = assess_unresolved_with_gemini(reqs, candidates, results, "test-key", "gemini-test", client)
    assert updated[0]["status"] == "Compliant"
    assert updated[0]["assessment_method"] == "Gemini-assisted review"
    assert updated[0]["document"] == "bid.pdf"
    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "gemini-test"


def test_invalid_evidence_reference_keeps_offline_result():
    reqs, candidates, results = _inputs()
    client = FakeClient({"assessments": [{"req_id": "R01", "status": "Compliant",
                                         "reason": "Unsupported assertion.", "evidence_index": 9}]})
    updated = assess_unresolved_with_gemini(reqs, candidates, results, "test-key", "gemini-test", client)
    assert updated[0]["status"] == "Needs Manual Review"
    assert "assessment_method" not in updated[0]


def test_definitive_offline_results_are_not_sent_to_gemini():
    reqs, candidates, results = _inputs()
    results[0]["status"] = "Compliant"
    client = FakeClient({"assessments": []})
    updated = assess_unresolved_with_gemini(reqs, candidates, results, "test-key", "gemini-test", client)
    assert updated[0]["status"] == "Compliant"
    assert client.calls == []


def test_deadlines_are_never_sent_to_gemini():
    reqs, candidates, results = _inputs()
    reqs[0]["category"] = "Deadline"
    client = FakeClient({"assessments": []})
    updated = assess_unresolved_with_gemini(reqs, candidates, results, "test-key", "gemini-test", client)
    assert updated[0]["status"] == "Needs Manual Review"
    assert client.calls == []


if __name__ == "__main__":
    test_gemini_assesses_only_manual_review_and_uses_source_evidence()
    test_invalid_evidence_reference_keeps_offline_result()
    test_definitive_offline_results_are_not_sent_to_gemini()
    test_deadlines_are_never_sent_to_gemini()
    print("ALL GEMINI ASSESSOR TESTS PASSED")