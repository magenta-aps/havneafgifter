"use strict";
/* eslint-disable no-unused-vars */
(function () {
    $(document).ready(function () {
        const form = $("form#main");
        const noPortOfCallCheckbox = $("#id_base-no_port_of_call");
        const portOfCallSelect = $("#id_base-port_of_call");
        const imoInput = $("#id_base-vessel_imo");
        const datetimeDepartureInput = $("#id_base-datetime_of_departure");
        const grossTonnageInput = $("#id_base-gross_tonnage");
        const vesselTypeSelect = $("#id_base-vessel_type");
        const shippingAgent = $("#id_base-shipping_agent");
        const submitButton = $("button[type=submit][value=NEW]");
        const submitDraftButton = $("button[type=submit][value=DRAFT]");
        const userTypeData = form.data("user-type");

        const isShipUserSelectingShippingAgent = function () {
            const isAgentSelected = (shippingAgent.val() !== "") && (shippingAgent.val() !== null);
            return (userTypeData === "ship") && isAgentSelected;
        }

        const isShippingAgent = function () {
            return (userTypeData === "shipping_agent");
        }

        const isNoPortOfCall = function () {
            return noPortOfCallCheckbox.is(":checked");
        }

        const isCruise = function () {
            const isCruiseShip = vesselTypeSelect.val() === "CRUISE";
            return isNoPortOfCall() || isCruiseShip;
        }

        const getDraftButtonText = function () {
            if (isShipUserSelectingShippingAgent()) {
                return gettext("Forward to agent");
            } else {
                return gettext("Save as draft");
            }
        }

        const updateButtonState = function () {
            if ((isCruise() && !isShippingAgent) || isShipUserSelectingShippingAgent()) {
                // Show only the DRAFT button (hide the NEW button)
                submitButton.addClass("d-none");
                submitDraftButton.removeClass("d-none");
            } else {
                // Show both DRAFT and NEW buttons
                submitButton.removeClass("d-none");
                submitDraftButton.removeClass("d-none");
            }

            // Update text on DRAFT button
            submitDraftButton.text(getDraftButtonText());
        }

        const updateNoPortOfCallState = function () {
            const disabled = isNoPortOfCall() ? "disabled" : null;

            if (disabled===null) { return }

            // portOfCallSelect.attr("disabled", disabled);
            datetimeDepartureInput.attr("disabled", disabled);
            grossTonnageInput.attr("disabled", disabled);
            //vesselTypeSelect.attr("disabled", disabled);

            portOfCallSelect.val(null);
            datetimeDepartureInput.val(null);
            grossTonnageInput.val(null);
            // TODO: Cleanup
            // Enforce vessel type CRUISE
            //vesselTypeSelect.val("CRUISE");

            updateButtonState();
        }

        // Update text on submit buttons, depending on the selected vessel type.
        vesselTypeSelect.on("change", function () {
            updateButtonState();
        });

        // Update text on submit buttons, depending on the selected shipping agent.
        shippingAgent.on("change", function () {
            updateButtonState();
        });

        // Hook form submit
        form.on("submit", function (evt) {
            // Ensure that potentially disabled fields are still POSTed to server
            // portOfCallSelect.attr("disabled", null);
            imoInput.attr("disabled", null);
            datetimeDepartureInput.attr("disabled", null);
            grossTonnageInput.attr("disabled", null);
            vesselTypeSelect.attr("disabled", null);
            shippingAgent.attr("disabled", null);
        });

        updateButtonState();
        updateNoPortOfCallState();
    });
})();
