from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    PassengersByCountry,
    PortTaxRate,
    ShippingAgent,
    TaxRates,
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


@admin.register(TaxRates)
class TaxRatesAdmin(admin.ModelAdmin):
    pass


@admin.register(PortTaxRate)
class PortTaxRateAdmin(admin.ModelAdmin):
    pass


@admin.register(DisembarkmentTaxRate)
class DisembarkmentTaxRateAdmin(admin.ModelAdmin):
    pass


# Unregister the provided model admin
admin.site.unregister(User)


# Register out own model admin, based on the default UserAdmin
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser
        disabled_fields = {
            "last_login",
            "date_joined",
        }

        if not is_superuser:
            # Staff users, not superadmins
            disabled_fields |= {
                "is_superuser",
                "user_permissions",
            }

            if obj is not None:
                if obj == request.user:
                    # Editing self
                    disabled_fields |= {
                        "is_staff",
                        "is_superuser",
                        "groups",
                        "user_permissions",
                    }
                elif obj.is_superuser:
                    # Editing superuser
                    disabled_fields |= {
                        "username",
                        "first_name",
                        "last_name",
                        "email",
                        "is_active",
                        "is_staff",
                        "groups",
                        "permissions",
                        "password",
                    }
                else:
                    # Editing other staff user
                    pass

        for field in disabled_fields:
            if field in form.base_fields:
                form.base_fields[field].disabled = True

        return form

    def has_change_permission(self, request, obj=None):
        if obj:
            if not request.user.is_superuser and obj.is_superuser:
                return False
        return super().has_change_permission(request, obj)
