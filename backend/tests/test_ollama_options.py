"""Every Ollama call must carry the GPU and context settings, or Ollama chooses its own split."""
from services import ollama_client


def test_options_force_gpu_layers_and_context(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, "ollama_num_gpu", 99)
    monkeypatch.setattr(ollama_client.settings, "ollama_num_ctx", 4096)

    options = ollama_client._generation_options()

    assert options["num_gpu"] == 99
    assert options["num_ctx"] == 4096
    assert options["use_mmap"] is False


def test_num_gpu_left_to_ollama_when_unset(monkeypatch):
    monkeypatch.setattr(ollama_client.settings, "ollama_num_gpu", None)

    options = ollama_client._generation_options()
    assert "num_gpu" not in options
    assert "use_mmap" not in options
