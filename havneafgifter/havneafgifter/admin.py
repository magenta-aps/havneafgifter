from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    PassengersByCountry,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
    User,
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
    actions = [
        "calculate_tax",
        "send_email",
    ]

    @admin.action(description=_("Calculate tax"))
    def calculate_tax(self, request, queryset):
        for obj in queryset:
            obj.calculate_tax(save=True)

    @admin.action(description=_("Send email"))
    def send_email(self, request, queryset):
        for obj in queryset:
            obj.send_email()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(vessel_type=ShipType.CRUISE)


class PassengersByCountryInlineAdmin(admin.TabularInline):
    model = PassengersByCountry
    extra = 0


class DisembarkmentInlineAdmin(admin.TabularInline):
    model = Disembarkment
    extra = 0
    fields = [
        "disembarkment_site",
        "number_of_passengers",
    ]


@admin.register(CruiseTaxForm)
class CruiseTaxFormAdmin(HarborDuesFormAdmin):
    inlines = [PassengersByCountryInlineAdmin, DisembarkmentInlineAdmin]

    def get_queryset(self, request):
        # Skip `HarborDuesFormAdmin.get_queryset`, which excludes
        # `vessel_type=ShipType.CRUISE`.
        return super(admin.ModelAdmin, self).get_queryset(request)


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
    list_display = [
        "municipality",
        "disembarkment_site",
        "disembarkment_tax_rate",
        "tax_rates",
    ]


# Register out own model admin, based on the default UserAdmin
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "cpr",
                    "cvr",
                    "organization",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

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
