from django.urls import path
from .views import stats_view

urlpatterns = [
    path("stats/", stats_view, name="stats"),
]
