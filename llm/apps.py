from django.apps import AppConfig


class LlmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'llm'
    verbose_name = 'LLM providers, credentials and style'

    def ready(self) -> None:
        # Load LiteLLM once, at startup, in the main thread. Imported lazily on first
        # use, it was first loaded inside an answer-generation thread while another
        # thread touched it, and Python's import lock raised _DeadlockError (~2 s,
        # one-off, per process).
        import litellm  # noqa: F401

        litellm.suppress_debug_info = True
