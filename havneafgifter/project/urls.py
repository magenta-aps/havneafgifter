from django.urls import include, path

urlpatterns = [
    path("havneafgifter/", include("havneafgifter.urls")),
]
