from app.skills.registry import select_skill


def test_skill_selection_is_conditional():
    assert select_skill("Help me compare a laptop").name == "purchasing"
    assert select_skill("Tell me a joke") is None
