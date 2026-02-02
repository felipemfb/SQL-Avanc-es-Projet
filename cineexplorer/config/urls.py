from django.contrib import admin
from django.urls import path
from movies import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),      # home page
    path('stats/', views.stats, name='stats'),  # stats page
]
