from app.memory.service import explicit_memory_request, identity_key_for, tokens


def test_tokens_ignore_short_words_and_normalize_case():
    assert tokens("The API key is secret but project works") == {
        "the",
        "api",
        "key",
        "secret",
        "but",
        "project",
        "works",
    }


def test_identity_key_is_stable_for_case_and_punctuation():
    assert identity_key_for("preference", "I prefer open-source tools!") == identity_key_for(
        "preference", "i PREFER open source tools"
    )


def test_explicit_memory_request_rejects_credentials():
    assert explicit_memory_request("Please remember that my password: hunter2") is None
    assert explicit_memory_request("Remember that my API key is sk-or-v1-abc123") is None


def test_explicit_memory_request_classifies_preference():
    assert explicit_memory_request("Please remember that I prefer concise answers.") == (
        "preference",
        "I prefer concise answers",
    )


def test_unrequested_statement_is_not_a_memory_request():
    assert explicit_memory_request("I prefer concise answers.") is None
