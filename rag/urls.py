from django.urls import path

from . import views

app_name = 'rag'

urlpatterns = [
    path('notebook/<int:notebook_id>/chat/', views.chat_panel, name='chat'),
    path('notebook/<int:notebook_id>/ask/', views.ask, name='ask'),
    path('notebook/<int:notebook_id>/clear/', views.clear, name='clear'),
    path('message/<int:message_id>/stream/', views.stream, name='stream'),
    path('message/<int:message_id>/stop/', views.stop, name='stop'),
    path('message/<int:message_id>/citation/<int:n>/', views.citation, name='citation'),
]
