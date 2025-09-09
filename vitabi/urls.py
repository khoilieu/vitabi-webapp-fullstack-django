from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.shortcuts import redirect

def redirect_to_japanese(request):
    return redirect('/jp/')

urlpatterns = [
    re_path(r'^$', redirect_to_japanese),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
