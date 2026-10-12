from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    keywords: tuple[str, ...]
    instructions: str
    tools: tuple[str, ...]


SKILLS = (
    Skill(
        "budgeting",
        "Budget and spending trade-offs",
        ("budget", "save", "money", "cost", "salary"),
        "Separate stated facts from estimates. Do not assume risk tolerance.",
        ("simulation",),
    ),
    Skill(
        "career",
        "Career decisions",
        ("career", "job", "offer", "internship"),
        "Compare goals, growth, compensation and constraints.",
        ("research",),
    ),
    Skill(
        "education",
        "Learning and education planning",
        ("study", "learn", "exam", "course"),
        "Break goals into realistic milestones and account for available time.",
        (),
    ),
    Skill(
        "purchasing",
        "Purchase decisions",
        ("buy", "purchase", "laptop", "phone"),
        "Compare requirements, total cost and alternatives.",
        ("research", "simulation"),
    ),
    Skill(
        "travel",
        "Travel planning",
        ("travel", "trip", "move", "relocate"),
        "Clarify dates, budget and flexibility before current claims.",
        ("research", "simulation"),
    ),
    Skill(
        "time_management",
        "Time and commitment planning",
        ("schedule", "time", "prioritize", "commitment"),
        "Respect existing commitments and avoid overloading the schedule.",
        (),
    ),
)


def select_skill(text: str) -> Skill | None:
    lowered = text.lower()
    return next((s for s in SKILLS if any(word in lowered for word in s.keywords)), None)
