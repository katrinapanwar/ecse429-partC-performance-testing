"""Random data for the performance experiments: random todo payloads for create and change."""
import string

WORDS = ["report", "lab", "exam", "email", "groceries", "project", "review",
         "meeting", "assignment", "invoice", "workout", "reading", "budget", "plan"]


def random_text(rng, word_count):
    chosen = [rng.choice(WORDS) for _ in range(word_count)]
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
    return " ".join(chosen) + " " + suffix


def random_todo(rng):
    return {
        "title": random_text(rng, 3),
        "doneStatus": rng.choice([True, False]),
        "description": random_text(rng, 8),
    }


def random_change(rng):
    return {
        "title": random_text(rng, 3),
        "description": random_text(rng, 8),
    }
