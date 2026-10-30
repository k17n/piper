from piper_jobs.insights import (
    PROMPT_VERSION, build_facts, build_messages, facts_hash, is_grounded, numbers_in,
)


def test_facts_describe_pace_mix_and_conversion(sample_analytics):
    facts = build_facts(sample_analytics())
    assert facts[0] == "Applications from 2026-10-01 to 2026-10-30: 24 (previous period of the same length: 18)"
    assert "Role types: Product 58% (14), Design 25% (6), Other 17% (4)" in facts
    assert "Sources: LinkedIn 67% (16), Company site / ATS 33% (8)" in facts
    assert "Source LinkedIn: 16 applied, 6% replied, 0% interviewed" in facts
    assert "Highest reply rate by source: Company site / ATS; lowest: LinkedIn" in facts
    assert "Median time to a first reply: 4.5 days" in facts
    assert "The most recent 1 week of applications may still be waiting for replies" in facts
    assert "Open applications quiet for over two weeks: 4" in facts


def test_small_groups_are_left_out_of_conversion(sample_analytics):
    facts = build_facts(sample_analytics())
    assert not any(f.startswith("Role type Design") for f in facts)  # only 4 applications
    assert any(f.startswith("Role type Product") for f in facts)
    assert not any(f.startswith("Highest reply rate by role type") for f in facts)  # needs two big groups


def test_facts_skip_what_does_not_apply(sample_analytics):
    a = sample_analytics(response_time={"buckets": [], "median": None}, cohorts=[], open_by_age=[])
    a["summary"]["previous_total"] = None
    facts = build_facts(a)
    assert facts[0] == "Applications from 2026-10-01 to 2026-10-30: 24"
    assert not any(f.startswith(("Median", "The most recent", "Open applications")) for f in facts)


def test_facts_hash_depends_on_facts_model_and_prompt_version(sample_analytics):
    facts = build_facts(sample_analytics())
    key = facts_hash(facts, "qwen")
    assert key == facts_hash(list(facts), "qwen")
    assert key != facts_hash(facts, "llama")
    assert key != facts_hash(facts, "qwen", PROMPT_VERSION + 1)
    assert key != facts_hash([*facts, "one more"], "qwen")


def test_numbers_in():
    assert numbers_in("58% of 24, median 4.5 days") == {"58", "24", "4.5"}


def test_is_grounded_accepts_only_numbers_from_the_facts(sample_analytics):
    facts = build_facts(sample_analytics())
    assert is_grounded("You sent 24 applications, 58% of them Product.", facts)
    assert not is_grounded("You sent 26 applications.", facts)  # 25 is in the facts (Design 25%)
    assert not is_grounded("   ", facts)


def test_messages_list_every_fact():
    messages = build_messages(["first 1", "second 2"])
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "- first 1\n- second 2" in messages[1]["content"]
