"""Seal facts database for welcome screen."""

import random

# Seal facts (English with emoji)
SEAL_FACTS = [
    "🦭 Seals have no external ears,\njust small openings on the\nside of their head.",
    "🦭 Seals can hold their breath\nfor up to 2 hours underwater!",
    "🦭 Harbor seals can dive down\nto 1,500 feet (450m) deep.",
    "🦭 A group of seals is called\na 'colony' or 'rookery'.",
    "🦭 Seal pups are born with\nthick fur called 'lanugo'.",
    "🦭 Seals use their whiskers\nto detect fish vibrations.",
    "🦭 Most seals can swim at\nspeeds up to 23 mph (37 km/h).",
    "🦭 Seals are highly social\nanimals and love to cuddle!",
    "🦭 Seals can sleep underwater\nby resting half their brain!",
    "🦭 A seal's thick blubber layer\nkeeps them warm in icy water.",
]


def get_random_seal_fact() -> str:
    """Get a random seal fact for display.

    Returns:
        Formatted seal fact string
    """
    return random.choice(SEAL_FACTS)
