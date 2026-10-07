from django.urls import path

from . import views

app_name = 'llm'

urlpatterns = [
    # Account: API keys and local endpoints, one card per provider.
    path('api-keys/', views.ApiKeysView.as_view(), name='api_keys'),
    path('api-keys/set/', views.CredentialSetView.as_view(), name='credential_set'),
    path('api-keys/base-url/', views.BaseUrlSetView.as_view(), name='base_url_set'),
    path('api-keys/<str:provider>/delete/', views.CredentialDeleteView.as_view(), name='credential_delete'),
    path('api-keys/<str:provider>/test/', views.TestProviderView.as_view(), name='test_provider'),
    path('api-keys/<str:provider>/refresh/', views.RefreshModelsView.as_view(), name='refresh_models'),
    # Dependent model select (used by the notebook settings page).
    path('settings/models/', views.ModelOptionsView.as_view(), name='model_options'),
    # Per-notebook provider, model and answer style.
    path('notebook/<int:notebook_id>/settings/', views.NotebookSettingsView.as_view(), name='notebook_settings'),
]
