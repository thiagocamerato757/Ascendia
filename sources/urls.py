from django.urls import path

from . import views

app_name = 'sources'

urlpatterns = [
    path('notebook/<int:notebook_id>/panel/', views.panel, name='panel'),
    path('notebook/<int:notebook_id>/upload/', views.upload_pdf, name='upload'),
    path('notebook/<int:notebook_id>/text/', views.add_text, name='add_text'),
    path('notebook/<int:notebook_id>/reindex/', views.reindex, name='reindex'),
    path('<int:source_id>/delete/', views.delete_source, name='delete'),
    path('<int:source_id>/retry/', views.retry_source, name='retry'),
]
