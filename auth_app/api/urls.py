from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
]