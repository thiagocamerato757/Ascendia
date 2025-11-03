from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    # Note CRUD
    path('notebook/<int:notebook_id>/note/create/', views.NoteCreateView.as_view(), name='note_create'),
    path('note/<int:note_id>/', views.NoteDetailView.as_view(), name='note_detail'),
    path('note/<int:note_id>/edit/', views.NoteUpdateView.as_view(), name='note_edit'),
    path('note/<int:note_id>/delete/', views.NoteDeleteView.as_view(), name='note_delete'),
    path('note/<int:note_id>/toggle-pin/', views.NoteTogglePinView.as_view(), name='note_toggle_pin'),
    
    # Tag management
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tag/create/', views.TagCreateView.as_view(), name='tag_create'),
    path('note/<int:note_id>/tag/add/', views.NoteAddTagView.as_view(), name='note_add_tag'),
    path('note/<int:note_id>/tag/<int:tag_id>/remove/', views.NoteRemoveTagView.as_view(), name='note_remove_tag'),
]
