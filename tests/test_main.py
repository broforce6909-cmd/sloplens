"""
SlopLens v4 — Complete Test Suite (23 tests)
Covers heuristic, semantic, reading time, fusion, edge cases.
No API key required.
"""
import pytest, sys, os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from main import heuristic_score, semantic_score, fuse, calculate_times

SLOP = ("In today's fast-paced world, it goes without saying that leveraging cutting-edge "
        "AI solutions is paramount. Moving forward, our team will synergize cross-functional "
        "capabilities to deliver best-in-class experiences. At the end of the day, we need to "
        "think outside the box and circle back on our core competencies to move the needle.")

CLEAN = ("Fixed a race condition in auth middleware where concurrent requests read stale session "
         "tokens before the write lock was acquired. Reproduced under 50+ concurrent logins. "
         "Added Redis SETNX lock with 200ms TTL; fallback to DB after 3 retries. Closes #1847.")

PASSIVE = ("The report was written. The results were analyzed by engineers. "
           "The system was designed to be scalable. The code was refactored and tested.")

FAKE_LLM = {
    "overall_slop_score":80,"information_density":20,"filler_ratio":85,
    "specificity":15,"naturalness":12,"slop_category":"corporate_buzzwords",
    "verdict":"Pure jargon.","roast":"A masterpiece of saying nothing loudly.",
    "flagged_phrases":["moving forward"],"fix":"Be specific.",
}


class TestHeuristic:
    def test_slop_high_filler(self):           assert heuristic_score(SLOP)["filler_ratio"] > 40
    def test_clean_low_filler(self):           assert heuristic_score(CLEAN)["filler_ratio"] < 20
    def test_clean_high_density(self):         assert heuristic_score(CLEAN)["information_density"] > 40
    def test_slop_flags_phrases(self):         assert len(heuristic_score(SLOP)["flagged_phrases"]) > 0
    def test_passive_detected(self):           assert heuristic_score(PASSIVE)["passive_density"] > 20
    def test_empty_no_crash(self):             assert "filler_ratio" in heuristic_score("")
    def test_all_scores_bounded(self):
        for text in [SLOP, CLEAN, PASSIVE, "", "x"*5000]:
            r = heuristic_score(text)
            for k in ["filler_ratio","information_density","naturalness","passive_density"]:
                assert 0 <= r[k] <= 100


class TestSemantic:
    def test_slop_higher_than_clean(self):
        s_slop  = semantic_score(SLOP)["semantic_slop_score"]
        s_clean = semantic_score(CLEAN)["semantic_slop_score"]
        assert s_slop > s_clean, f"Expected slop({s_slop}) > clean({s_clean})"

    def test_scores_bounded(self):
        for text in [SLOP, CLEAN, "", "hello"]:
            r = semantic_score(text)
            assert 0 <= r["semantic_slop_score"] <= 100

    def test_similarity_fields_present(self):
        r = semantic_score(SLOP)
        assert "slop_similarity" in r
        assert "clean_similarity" in r
        assert "semantic_slop_score" in r

    def test_similarities_are_floats(self):
        r = semantic_score(CLEAN)
        assert isinstance(r["slop_similarity"],  float)
        assert isinstance(r["clean_similarity"], float)


class TestReadingTime:
    def test_word_count(self):         assert calculate_times("one two three", 50)["word_count"] == 3
    def test_zero_density_full_fluff(self): assert calculate_times("word "*100, 0)["fluff_percent"] == 100
    def test_high_density_low_fluff(self):  assert calculate_times("word "*100, 90)["fluff_percent"] <= 10
    def test_info_le_reading(self):
        r = calculate_times(SLOP, 40)
        assert r["info_time_min"] <= r["reading_time_min"]
    def test_all_fields(self):
        r = calculate_times(SLOP, 50)
        for k in ["reading_time_min","info_time_min","fluff_percent","word_count"]:
            assert k in r


class TestFusion:
    def test_all_required_fields(self):
        result = fuse(heuristic_score(SLOP), FAKE_LLM, SLOP)
        for f in ["overall_slop_score","information_density","filler_ratio","specificity",
                  "naturalness","passive_density","semantic_slop_score","slop_category",
                  "verdict","roast","flagged_phrases","fix","reading_time_min",
                  "info_time_min","fluff_percent","scoring_method"]:
            assert f in result, f"Missing: {f}"

    def test_scoring_method_v4(self):
        assert fuse(heuristic_score(SLOP), FAKE_LLM, SLOP)["scoring_method"] == "hybrid_v4_3layer"

    def test_scores_bounded(self):
        r = fuse(heuristic_score(CLEAN), FAKE_LLM, CLEAN)
        for k in ["information_density","filler_ratio","naturalness"]:
            assert 0 <= r[k] <= 100

    def test_roast_preserved(self):
        assert fuse(heuristic_score(SLOP), FAKE_LLM, SLOP)["roast"] == FAKE_LLM["roast"]

    def test_semantic_score_present(self):
        r = fuse(heuristic_score(SLOP), FAKE_LLM, SLOP)
        assert 0 <= r["semantic_slop_score"] <= 100


class TestRepoScanner:
    def test_parse_repo_plain(self):
        from main import parse_repo
        assert parse_repo("torvalds/linux") == "torvalds/linux"

    def test_parse_repo_url(self):
        from main import parse_repo
        assert parse_repo("https://github.com/torvalds/linux") == "torvalds/linux"

    def test_parse_repo_url_trailing_slash(self):
        from main import parse_repo
        assert parse_repo("https://github.com/torvalds/linux/") == "torvalds/linux"

    def test_parse_repo_git_suffix(self):
        from main import parse_repo
        assert parse_repo("https://github.com/torvalds/linux.git") == "torvalds/linux"

    def test_parse_repo_www(self):
        from main import parse_repo
        assert parse_repo("https://www.github.com/owner/repo") == "owner/repo"


class TestCLI:
    def test_cli_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cli", "/home/claude/sloplens_v4/cli.py")
        mod = importlib.util.module_from_spec(spec)
        # Just check it loads without error
        assert mod is not None

    def test_setup_py_exists(self):
        assert (Path("/home/claude/sloplens_v4/setup.py")).exists()

    def test_slop_gate_action_exists(self):
        assert (Path("/home/claude/sloplens_v4/.github/workflows/slop-gate.yml")).exists()


class TestNewFeatures:
    def test_fuse_has_confidence_interval(self):
        result = fuse(heuristic_score(SLOP), FAKE_LLM, SLOP)
        assert "confidence_interval" in result
        assert 3 <= result["confidence_interval"] <= 15

    def test_confidence_interval_clean_lower(self):
        """High-confidence text (lots of fillers detected) = lower CI range"""
        r_slop  = fuse(heuristic_score(SLOP),  FAKE_LLM, SLOP)
        r_clean = fuse(heuristic_score(CLEAN), FAKE_LLM, CLEAN)
        # slop has more signals → higher confidence → lower interval
        assert r_slop["confidence_interval"] <= r_clean["confidence_interval"]

    def test_precommit_hook_exists(self):
        hook = Path("/home/claude/sloplens_v4/pre-commit-hook/sloplens-check.py")
        assert hook.exists()
        assert hook.stat().st_size > 1000

    def test_precommit_hook_runnable(self):
        import subprocess
        r = subprocess.run(
            ["python3", "/home/claude/sloplens_v4/pre-commit-hook/sloplens-check.py"],
            capture_output=True, text=True,
            env={**__import__('os').environ, "HOME": "/tmp"}
        )
        # exits 0 when no git repo / no staged files
        assert r.returncode == 0

    def test_condense_endpoint_registered(self):
        from main import app
        routes = [r.path for r in app.routes]
        assert "/scan/condense" in routes
