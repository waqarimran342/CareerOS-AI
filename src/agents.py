"""
The five core agents of CareerOS AI.

Each agent is a small class that:
  1. builds a focused prompt,
  2. calls Gemini through `GeminiClient.chat_json()`,
  3. returns a plain Python dict.

Pipeline (run by `run_full_analysis`):

    Resume Analysis Agent   -> claimed skills, experience, quality notes
    GitHub Evidence Agent   -> verified skills backed by real repositories
    Job Matching Agent      -> required skills for the target role
    Skill Gap Agent         -> gaps between required and demonstrated skills
    Master Career Agent     -> final report: readiness score, roadmap, ...

The key idea: the Master agent cross-checks what the resume CLAIMS against
what GitHub PROVES, producing verified vs unverified skill lists.
"""

import json
from typing import Any, Dict, Optional

from qwen_client import GeminiClient


# --------------------------------------------------------------------------
# Agent 1: Resume Analysis
# --------------------------------------------------------------------------
class ResumeAnalysisAgent:
    """Extracts claimed skills and experience from resume text."""

    name = "Resume Analysis Agent"

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm

    def run(self, resume_text: str, target_role: str) -> Dict[str, Any]:
        system_prompt = (
            "You are a senior technical recruiter who has reviewed thousands "
            "of software engineering resumes. You are precise and skeptical: "
            "you only report skills that are actually visible in the resume text."
        )

        user_prompt = f"""Analyze the resume below for a candidate targeting this role: {target_role}.

RESUME TEXT:
\"\"\"
{resume_text}
\"\"\"

Return a JSON object with EXACTLY this structure:
{{
  "candidate_name": "name found in the resume, or '' ",
  "summary": "1-2 sentence professional profile based only on the resume",
  "years_of_experience": "best estimate as a number, 0 for a student/fresher",
  "claimed_skills": ["up to 20 specific technical skills the resume claims, e.g. Python, React, Docker, MySQL"],
  "education": "highest education in one short line",
  "experience_highlights": ["up to 5 notable achievements or roles, one line each"],
  "resume_quality_notes": ["up to 5 short improvement notes: formatting, weak bullets, missing sections, ATS issues"]
}}"""

        return self.llm.chat_json(self.name, system_prompt, user_prompt)


# --------------------------------------------------------------------------
# Agent 2: GitHub Evidence
# --------------------------------------------------------------------------
class GitHubEvidenceAgent:
    """Derives verified skills from real GitHub activity."""

    name = "GitHub Evidence Agent"

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm

    def run(self, github_evidence_text: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an engineering manager assessing a developer using ONLY "
            "their public GitHub activity. You distinguish genuine skill "
            "evidence (real repositories, languages, consistent pushes, "
            "quality projects) from noise (forks, empty repos)."
        )

        user_prompt = f"""Assess this developer based on their GitHub profile data:

GITHUB ACTIVITY:
\"\"\"
{github_evidence_text}
\"\"\"

Return a JSON object with EXACTLY this structure:
{{
  "verified_skills": [
    {{"skill": "e.g. Python", "evidence": "which repos/languages prove it", "confidence": "high | medium | low"}}
  ] (max 12, ordered by strength of evidence),
  "activity_summary": "1-2 sentences about consistency, variety and depth of work",
  "project_quality_score": 0-100 score for the portfolio (repos, descriptions, stars, maintenance),
  "project_quality_notes": ["up to 4 short notes about the portfolio: polish, READMEs, project variety, momentum"],
  "repo_highlights": ["up to 5 standout repositories as 'name — why it matters'"]
}}"""

        return self.llm.chat_json(self.name, system_prompt, user_prompt)


# --------------------------------------------------------------------------
# Agent 3: Job Matching
# --------------------------------------------------------------------------
class JobMatchingAgent:
    """Matches the candidate against the target role's requirements."""

    name = "Job Matching Agent"

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm

    def run(
        self,
        target_role: str,
        job_description: Optional[str],
        resume_analysis: Dict[str, Any],
        github_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are a technical hiring manager who defines precise role "
            "requirements. When a job description is given, extract "
            "requirements from it; otherwise use current market standards "
            "for the target role."
        )

        claimed = json.dumps(resume_analysis.get("claimed_skills", []))
        verified = json.dumps(
            [
                item.get("skill", "")
                for item in github_analysis.get("verified_skills", [])
                if isinstance(item, dict)
            ]
        )

        jd_section = "None provided — infer requirements from the target role."
        if job_description and job_description.strip():
            jd_section = f'"""\n{job_description.strip()[:6000]}\n"""'

        user_prompt = f"""TARGET ROLE: {target_role}

JOB DESCRIPTION (optional):
{jd_section}

CANDIDATE'S CLAIMED SKILLS (from resume): {claimed}
CANDIDATE'S VERIFIED SKILLS (from GitHub): {verified}

Return a JSON object with EXACTLY this structure:
{{
  "required_skills": [
    {{"skill": "skill name", "importance": "must-have | nice-to-have"}}
  ] (8-15 skills typical for this role),
  "match_percentage": 0-100 overall fit for the role,
  "matched_skills": ["skills the candidate already has"],
  "missing_skills": ["required skills with no claim or evidence"],
  "role_insights": "1-2 sentences on how well this candidate fits the role"
}}"""

        return self.llm.chat_json(self.name, system_prompt, user_prompt)


# --------------------------------------------------------------------------
# Agent 4: Skill Gap
# --------------------------------------------------------------------------
class SkillGapAgent:
    """Identifies and prioritizes the candidate's skill gaps."""

    name = "Skill Gap Agent"

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm

    def run(
        self,
        job_match: Dict[str, Any],
        resume_analysis: Dict[str, Any],
        github_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are a career coach who turns skill gaps into a clear, "
            "prioritized development plan. Be specific and actionable — "
            "never generic advice."
        )

        user_prompt = f"""Compare what the role requires with what the candidate has.

ROLE REQUIREMENTS (from the Job Matching Agent):
{json.dumps(job_match, indent=2)}

CLAIMED SKILLS (from resume):
{json.dumps(resume_analysis.get('claimed_skills', []))}

VERIFIED SKILLS (from GitHub):
{json.dumps(github_analysis.get('verified_skills', []))}

Return a JSON object with EXACTLY this structure:
{{
  "critical_gaps": [
    {{"skill": "missing must-have skill", "why_it_matters": "impact on hiring chances", "current_level": "none | beginner | intermediate", "required_level": "what level the role needs"}}
  ] (up to 5, most important first),
  "moderate_gaps": [same structure] (up to 5),
  "quick_wins": ["skills that can be learned to a demonstrable level in under 2 weeks"]
}}"""

        return self.llm.chat_json(self.name, system_prompt, user_prompt)


# --------------------------------------------------------------------------
# Agent 5: Master Career Agent (final synthesis)
# --------------------------------------------------------------------------
class MasterCareerAgent:
    """Combines all agent outputs into the final career intelligence report."""

    name = "Master Career Agent"

    def __init__(self, llm: GeminiClient) -> None:
        self.llm = llm

    def run(
        self,
        target_role: str,
        resume_analysis: Dict[str, Any],
        github_analysis: Dict[str, Any],
        job_match: Dict[str, Any],
        skill_gaps: Dict[str, Any],
    ) -> Dict[str, Any]:
        system_prompt = (
            "You are the Master Career Agent of CareerOS AI. You synthesize "
            "the outputs of four specialist agents into one honest, "
            "evidence-based career report. Your core principle: a skill is "
            "VERIFIED only when the resume claims it AND GitHub activity "
            "proves it. Claims without proof are UNVERIFIED. Be realistic "
            "and encouraging, never inflated."
        )

        user_prompt = f"""Create the final career report for a candidate targeting: {target_role}

RESUME ANALYSIS:
{json.dumps(resume_analysis, indent=2)}

GITHUB EVIDENCE ANALYSIS:
{json.dumps(github_analysis, indent=2)}

JOB MATCH ANALYSIS:
{json.dumps(job_match, indent=2)}

SKILL GAP ANALYSIS:
{json.dumps(skill_gaps, indent=2)}

Return a JSON object with EXACTLY this structure:
{{
  "career_readiness_score": 0-100 overall score (weight roughly: resume quality 25%, evidence strength 25%, job match 30%, skill coverage 20%),
  "score_breakdown": {{
    "resume_quality": 0-100,
    "evidence_strength": 0-100,
    "job_match": 0-100,
    "skill_coverage": 0-100
  }},
  "verified_skills": [
    {{"skill": "claimed AND proven on GitHub", "evidence": "the GitHub proof"}}
  ] (max 12),
  "unverified_skills": [
    {{"skill": "claimed but no public proof", "reason": "e.g. no repos found using it"}}
  ] (max 12),
  "strengths": ["up to 6 genuine strengths backed by the data"],
  "skill_gaps": [
    {{"skill": "gap name", "severity": "critical | moderate | minor", "why_it_matters": "short reason"}}
  ] (max 8, most severe first),
  "evidence": [
    {{"source": "github | resume", "detail": "concrete fact supporting the assessment"}}
  ] (max 8),
  "recommendations": ["up to 6 prioritized, specific next actions"],
  "roadmap_30_days": [
    {{"week": 1, "focus": "theme of the week", "tasks": ["3-4 concrete tasks"], "outcome": "what will be true at the end of the week"}}
  ] (exactly 4 entries: weeks 1-4),
  "recommended_project": {{
    "title": "project name",
    "description": "2-3 sentences on what to build",
    "skills_practiced": ["skills it demonstrates"],
    "why_it_helps": "how it closes gaps and strengthens evidence"
  }},
  "hiring_readiness_summary": "2-3 sentence honest verdict on readiness for the target role"
}}"""

        # Generous token budget: Gemini "thinking" models spend thinking
        # tokens from the same limit, and this report is the largest JSON we build.
        return self.llm.chat_json(self.name, system_prompt, user_prompt, max_tokens=8192)


# --------------------------------------------------------------------------
# Pipeline orchestration
# --------------------------------------------------------------------------
def run_full_analysis(
    llm: GeminiClient,
    resume_text: str,
    github_profile: Dict[str, Any],
    target_role: str,
    job_description: str = "",
) -> Dict[str, Any]:
    """
    Run the complete 5-agent pipeline and return every agent's output.

    Called by the API layer in `main.py`. Keeping orchestration here (not
    in the web layer) means the whole analysis can also run from scripts
    or tests.
    """
    resume_agent = ResumeAnalysisAgent(llm)
    github_agent = GitHubEvidenceAgent(llm)
    job_agent = JobMatchingAgent(llm)
    gap_agent = SkillGapAgent(llm)
    master_agent = MasterCareerAgent(llm)

    # Stage 1 & 2 are independent analyses of the two evidence sources.
    resume_analysis = resume_agent.run(resume_text, target_role)
    github_analysis = github_agent.run(github_profile.get("evidence_text", ""))

    # Stage 3 & 4 compare the requirements against what we now know.
    job_match = job_agent.run(target_role, job_description, resume_analysis, github_analysis)
    skill_gaps = gap_agent.run(job_match, resume_analysis, github_analysis)

    # Stage 5: the Master agent synthesizes the final report.
    career_report = master_agent.run(
        target_role, resume_analysis, github_analysis, job_match, skill_gaps
    )

    return {
        "resume_analysis": resume_analysis,
        "github_analysis": github_analysis,
        "job_match": job_match,
        "skill_gaps": skill_gaps,
        "career_report": career_report,  # <- the headline result for the UI
    }
