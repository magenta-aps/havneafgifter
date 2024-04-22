from typing import List

from django.urls import URLPattern, URLResolver, include, path

urlpatterns: List[URLResolver | URLPattern] = [
    path(
        "havneafgifter/",
        include(
            "havneafgifter.urls",
            namespace="havneafgifter",
        ),
    ),

]
