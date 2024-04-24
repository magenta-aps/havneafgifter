from django.contrib import admin

from .models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    HarborDuesForm,
    PassengersByCountry,
    ShippingAgent,
)


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
        "datetime_of_arrival",
        "datetime_of_departure",
    ]


class PassengersByCountryInlineAdmin(admin.TabularInline):
    model = PassengersByCountry
    extra = 0


class DisembarkmentInlineAdmin(admin.TabularInline):
    model = Disembarkment
    extra = 0


@admin.register(CruiseTaxForm)
class CruiseTaxFormAdmin(HarborDuesFormAdmin):
    inlines = [PassengersByCountryInlineAdmin, DisembarkmentInlineAdmin]


@admin.register(DisembarkmentSite)
class DisembarkmentSiteAdmin(admin.ModelAdmin):
    pass


@admin.register(ShippingAgent)
class ShippingAgentAdmin(admin.ModelAdmin):
    pass
