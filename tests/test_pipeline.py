"""
Offline unit tests for CareerOS AI.

These tests need NO API key and NO network access:
  - the LLM is replaced by a FakeGemini that returns canned JSON,
  - GitHub data is a fixture, not a real API call.

Run from the project root:
    python -m unittest discover -s tests -v
"""

import io
import sys
import unittest
from pathlib import Path

# Make the src/ folder importable no matter where tests are launched from.
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import agents  # noqa: E402
from github_service import build_profile_summary  # noqa: E402
from qwen_client import GeminiClient, GeminiError, extract_json_object  # noqa: E402
from resume_service import ResumeError, extract_text_from_pdf  # noqa: E402
from pypdf import PdfWriter  # noqa: E402


# ---------------------------------------------------------------------------
# Fake LLM client: records which agents called it, returns canned answers.
# ---------------------------------------------------------------------------
class FakeGemini:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, agent_name, system_prompt, user_prompt, **kwargs):
        self.calls.append(agent_name)
        return self.responses.pop(0)


# ---------------------------------------------------------------------------
# qwen_client.extract_json_object
# ---------------------------------------------------------------------------
class TestExtractJson(unittest.TestCase):
    def test_plain_json(self):
        result = extract_json_object('{"score": 42}')
        self.assertEqual(result["score"], 42)

    def test_json_in_markdown_fence(self):
        reply = "Here is my answer:\n```json\n{\"score\": 7}\n```\nDone."
        self.assertEqual(extract_json_object(reply)["score"], 7)

    def test_json_with_chatter_around_it(self):
        reply = 'Sure! {"a": 1} hope that helps'
        self.assertEqual(extract_json_object(reply)["a"], 1)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            extract_json_object("")

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            extract_json_object("sorry, I cannot do that")


# ---------------------------------------------------------------------------
# qwen_client.GeminiClient constructor (no network involved)
# ---------------------------------------------------------------------------
class TestGeminiClientInit(unittest.TestCase):
    def test_missing_api_key_raises(self):
        with self.assertRaises(GeminiError):
            # Explicit empty key always fails, even if a real .env exists.
            GeminiClient(api_key="   ")


# ---------------------------------------------------------------------------
# github_service.build_profile_summary (pure function, fixture data)
# ---------------------------------------------------------------------------
class TestGithubSummary(unittest.TestCase):
    def setUp(self):
        self.user = {
            "login": "testdev",
            "name": "Test Developer",
            "bio": "Python enthusiast",
            "followers": 12,
            "public_repos": 3,
            "created_at": "2022-05-01T00:00:00Z",
        }
        self.repos = [
            {"name": "web-app", "language": "JavaScript", "stargazers_count": 3,
             "forks_count": 1, "fork": False, "topics": ["react"], "description": "A web app",
             "pushed_at": "2026-08-01T00:00:00Z", "html_url": "https://github.com/testdev/web-app"},
            {"name": "cool-lib", "language": "Python", "stargazers_count": 50,
             "forks_count": 9, "fork": False, "topics": ["cli", "automation"], "description": "CLI tool",
             "pushed_at": "2026-07-15T00:00:00Z", "html_url": "https://github.com/testdev/cool-lib"},
            {"name": "data-scripts", "language": "Python", "stargazers_count": 0,
             "forks_count": 0, "fork": False, "topics": [], "description": "Small scripts",
             "pushed_at": "2026-06-20T00:00:00Z", "html_url": "https://github.com/testdev/data-scripts"},
            {"name": "forked-project", "language": "Python", "stargazers_count": 999,
             "forks_count": 999, "fork": True, "topics": [], "description": "a fork",
             "pushed_at": "2026-01-01T00:00:00Z", "html_url": ""},
        ]

    def test_summary_structure(self):
        profile = build_profile_summary(self.user, self.repos)
        self.assertEqual(profile["username"], "testdev")
        # Forks must be ignored (the 999-star fork must not count).
        self.assertEqual(profile["total_stars"], 53)
        # Languages ordered by how many own repos use them (Python has 2, JS 1).
        self.assertEqual(profile["languages"], ["Python", "JavaScript"])
        # Top repo is the most starred non-fork.
        self.assertEqual(profile["top_repos"][0]["name"], "cool-lib")
        self.assertEqual(profile["topics"], ["automation", "cli", "react"])

    def test_evidence_text_mentions_username(self):
        profile = build_profile_summary(self.user, self.repos)
        self.assertIn("testdev", profile["evidence_text"])
        self.assertIn("cool-lib", profile["evidence_text"])


# ---------------------------------------------------------------------------
# resume_service (error paths with generated PDFs — no fixtures needed)
# ---------------------------------------------------------------------------
class TestResumeService(unittest.TestCase):
    def test_not_a_pdf_raises(self):
        with self.assertRaises(ResumeError):
            extract_text_from_pdf(b"this is definitely not a pdf")

    def test_blank_pdf_raises(self):
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buffer = io.BytesIO()
        writer.write(buffer)
        with self.assertRaises(ResumeError):
            extract_text_from_pdf(buffer.getvalue())


# ---------------------------------------------------------------------------
# agents.run_full_analysis with the FakeGemini (full pipeline, no network)
# ---------------------------------------------------------------------------
class TestAgentPipeline(unittest.TestCase):
    def _fake_responses(self):
        return [
            # Resume Analysis Agent
            {"candidate_name": "Test Developer", "claimed_skills": ["Python", "React"],
             "years_of_experience": 2, "summary": "Dev", "education": "BS CS",
             "experience_highlights": [], "resume_quality_notes": []},
            # GitHub Evidence Agent
            {"verified_skills": [{"skill": "Python", "evidence": "12 repos", "confidence": "high"}],
             "activity_summary": "active", "project_quality_score": 60,
             "project_quality_notes": [], "repo_highlights": []},
            # Job Matching Agent
            {"required_skills": [{"skill": "Python", "importance": "must-have"}],
             "match_percentage": 70, "matched_skills": ["Python"],
             "missing_skills": ["Docker"], "role_insights": "good fit"},
            # Skill Gap Agent
            {"critical_gaps": [{"skill": "Docker", "why_it_matters": "needed",
                                "current_level": "none", "required_level": "intermediate"}],
             "moderate_gaps": [], "quick_wins": []},
            # Master Career Agent
            {"career_readiness_score": 68,
             "score_breakdown": {"resume_quality": 70, "evidence_strength": 60,
                                 "job_match": 70, "skill_coverage": 65},
             "verified_skills": [{"skill": "Python", "evidence": "12 repos"}],
             "unverified_skills": [{"skill": "React", "reason": "no repos found"}],
             "strengths": ["strong Python"], "skill_gaps": [{"skill": "Docker", "severity": "critical",
                                                            "why_it_matters": "needed"}],
             "evidence": [{"source": "github", "detail": "12 Python repos"}],
             "recommendations": ["learn Docker"],
             "roadmap_30_days": [{"week": 1, "focus": "Docker basics", "tasks": [],
                                  "outcome": "containerize an app"}],
             "recommended_project": {"title": "API", "description": "build one",
                                     "skills_practiced": ["Docker"], "why_it_helps": "evidence"},
             "hiring_readiness_summary": "almost ready"},
        ]

    def test_pipeline_runs_all_agents_in_order(self):
        fake = FakeGemini(self._fake_responses())
        github_profile = {"evidence_text": "GitHub username: testdev"}

        result = agents.run_full_analysis(
            llm=fake,
            resume_text="Test Developer resume text",
            github_profile=github_profile,
            target_role="Backend Developer",
        )

        # All five agents ran, in pipeline order.
        self.assertEqual(fake.calls, [
            "Resume Analysis Agent",
            "GitHub Evidence Agent",
            "Job Matching Agent",
            "Skill Gap Agent",
            "Master Career Agent",
        ])
        # The final result exposes every agent's output.
        self.assertEqual(
            sorted(result.keys()),
            ["career_report", "github_analysis", "job_match", "resume_analysis", "skill_gaps"],
        )
        # The headline report contains the readiness score.
        self.assertEqual(result["career_report"]["career_readiness_score"], 68)


if __name__ == "__main__":
    unittest.main()
