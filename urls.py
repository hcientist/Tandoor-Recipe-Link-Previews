from django.urls import path

from . import views

urlpatterns = [
    path('slug/<int:pk>/', views.slug, name='link_preview_slug'),
]
