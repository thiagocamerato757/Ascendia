from django.apps import AppConfig


class SourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sources'

    def ready(self) -> None:
        from . import signals  # noqa: F401 - registers handlers
