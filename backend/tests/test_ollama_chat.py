"""RAG generation must use chat roles, report why generation stopped, and flag a cut-off answer."""
import logging

from services import llm_client, ollama_client


def test_rag_messages_use_roles_and_no_template_markers():
    messages = llm_client._rag_messages("[1] (GDPR)\nArticle 6 text", "What is lawful processing?")
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "Article 6 text" in messages[0]["content"]
    assert not any("<|" in m["content"] for m in messages)


def test_chat_payload_carries_options_and_keep_alive(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, "ollama_keep_alive", "30m")
    payload = ollama_client._chat_payload([{"role": "user", "content": "q"}], model="m", stream=False)
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_ctx"] == ollama_client.settings.ollama_num_ctx


def test_reply_text_is_read_from_the_message():
    data = {"message": {"role": "assistant", "content": " Answer. "}, "done_reason": "stop", "eval_count": 3}
    assert ollama_client._read_chat_reply(data) == "Answer."


def test_hitting_the_token_cap_is_logged(caplog):
    data = {"message": {"content": "cut off"}, "done_reason": "length", "eval_count": 1024, "prompt_eval_count": 900}
    with caplog.at_level(logging.WARNING):
        ollama_client._read_chat_reply(data)
    assert "token cap" in caplog.text


def test_a_full_context_window_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(ollama_client.settings, "ollama_num_ctx", 4096)
    data = {"message": {"content": "ok"}, "done_reason": "stop", "eval_count": 10, "prompt_eval_count": 4096}
    with caplog.at_level(logging.WARNING):
        ollama_client._read_chat_reply(data)
    assert "context window" in caplog.text
