import re
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


def detect_skill(text: str) -> tuple[Skill | None, str | None]:
    lowered = text.lower().strip()
    if not lowered:
        return None, None

    # Check for explicit slash command: /<skill_name>
    tokens = lowered.split()
    first_token = tokens[0] if tokens else ""

    for s in SKILLS:
        slash_names = [
            f"/{s.name.lower()}",
            f"/{s.name.lower().replace('_', '-')}",
        ]
        if s.name == "budgeting":
            slash_names.append("/budget")
        elif s.name == "time_management":
            slash_names.extend(["/time", "/schedule"])

        for slash_name in slash_names:
            if first_token == slash_name or first_token.startswith(slash_name + ":") or first_token.startswith(slash_name + "/"):
                return s, "slash_command"
            if re.search(r'(?:^|\s)' + re.escape(slash_name) + r'(?:\s|$|:)', lowered):
                return s, "slash_command"

    # Context-based keyword detection
    for s in SKILLS:
        for keyword in s.keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return s, "context"

    return None, None


def select_skill(text: str) -> Skill | None:
    skill, _ = detect_skill(text)
    return skill


def get_all_skills_data() -> list[dict]:
    return [
        {
            "name": s.name,
            "description": s.description,
            "keywords": list(s.keywords),
            "instructions": s.instructions,
            "tools": list(s.tools),
            "slash_command": f"/{s.name.replace('_', '-')}",
        }
        for s in SKILLS
    ]

