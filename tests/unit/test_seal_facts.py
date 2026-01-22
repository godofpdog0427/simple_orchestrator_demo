"""Unit tests for seal facts."""

import pytest

from orchestrator.cli.seal_facts import get_random_seal_fact, SEAL_FACTS


class TestSealFacts:
    """Tests for seal facts database."""

    def test_get_random_seal_fact_returns_string(self):
        """Test get_random_seal_fact returns a string."""
        fact = get_random_seal_fact()
        assert isinstance(fact, str)
        assert len(fact) > 0

    def test_fact_is_from_database(self):
        """Test returned fact is from SEAL_FACTS."""
        fact = get_random_seal_fact()
        assert fact in SEAL_FACTS

    def test_all_facts_have_seal_emoji(self):
        """Test all facts contain seal emoji."""
        for fact in SEAL_FACTS:
            assert "🦭" in fact

    def test_all_facts_are_multiline(self):
        """Test all facts have multiple lines."""
        for fact in SEAL_FACTS:
            assert "\n" in fact

    def test_randomness(self):
        """Test that multiple calls can return different facts."""
        # Call 20 times and collect results
        results = {get_random_seal_fact() for _ in range(20)}

        # With 10+ facts, we should get at least 3 different ones in 20 tries
        # (This is a probabilistic test, but with >80% certainty)
        assert len(results) >= 3

    def test_seal_facts_not_empty(self):
        """Test SEAL_FACTS contains at least some facts."""
        assert len(SEAL_FACTS) >= 5  # Should have at least 5 facts
