from django.shortcuts import render

from .services.sqlite_service import get_movie_count
from .services.mongo_service import get_movie_count_mongo

def home(request):
    """Home page view."""
    try:
        total_movies = get_movie_count()
    except Exception:
        total_movies = 0

    context = {'total_movies': total_movies}
    return render(request, 'home.html', context)

def stats(request):
    """Stats page view."""
    try:
        sqlite_count = get_movie_count()
    except Exception:
        sqlite_count = 0

    try:
        mongo_count = get_movie_count_mongo()
    except Exception:
        mongo_count = 'MongoDB not connected'

    context = {
        'sqlite_count': sqlite_count,
        'mongo_count': mongo_count
    }
    return render(request, 'stats.html', context)
