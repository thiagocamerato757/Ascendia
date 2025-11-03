from django.urls import path
from . import views

app_name = 'workspace'

urlpatterns = [
    path('', views.WorkspaceHomeView.as_view(), name='home'),
    path('notebook/<int:notebook_id>/', views.NotebookDetailView.as_view(), name='notebook_detail'),
    path('notebook/create/', views.NotebookCreateView.as_view(), name='notebook_create'),
    path('notebook/<int:notebook_id>/edit/', views.NotebookUpdateView.as_view(), name='notebook_edit'),
    path('notebook/<int:notebook_id>/delete/', views.NotebookDeleteView.as_view(), name='notebook_delete'),
    path('notebook/<int:notebook_id>/toggle-favorite/', views.NotebookToggleFavoriteView.as_view(), name='notebook_toggle_favorite'),
]
