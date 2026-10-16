from app.skills.registry import detect_skill, select_skill


def test_skill_selection_is_conditional():
    assert select_skill("Help me compare a laptop").name == "purchasing"
    assert select_skill("Tell me a joke") is None


def test_slash_command_skill_selection():
    skill, trigger = detect_skill("/career How should I prepare for interviews?")
    assert skill is not None and skill.name == "career"
    assert trigger == "slash_command"

    skill, trigger = detect_skill("/budgeting What should my monthly savings be?")
    assert skill is not None and skill.name == "budgeting"
    assert trigger == "slash_command"

    skill, trigger = detect_skill("/travel Best places to visit in autumn")
    assert skill is not None and skill.name == "travel"
    assert trigger == "slash_command"

    skill, trigger = detect_skill("/time-management How do I balance work and study?")
    assert skill is not None and skill.name == "time_management"
    assert trigger == "slash_command"

    skill, trigger = detect_skill("I want to buy a new phone")
    assert skill is not None and skill.name == "purchasing"
    assert trigger == "context"

