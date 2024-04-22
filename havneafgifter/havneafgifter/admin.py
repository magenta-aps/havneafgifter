from django.contrib import admin

from .models import HarborDuesForm


@admin.register(HarborDuesForm)
class HarborDuesFormAdmin(admin.ModelAdmin):
    list_filter = [
        "port_of_call",
        "nationality",
        "shipping_agent",
        "vessel_type",
    ]
    search_fields = [
        "vessel_name",
        "vessel_imo",
        "vessel_owner",
        "vessel_master",
    ]
    list_display = [
        "vessel_name",
        "vessel_imo",
        "vessel_type",
        "port_of_call",
        "date_of_arrival",
        "date_of_departure",
    ]
