/* eslint-disable no-unused-vars */
(function () {
    $(document).ready(function () {
        const form = $("form#main");
        const noPortOfCallCheckbox = $("#id_no_port_of_call");
        const portOfCallSelect = $("#id_port_of_call");
        const imoInput = $("#id_vessel_imo");
        const datetimeInputs = $("#id_datetime_of_arrival, #id_datetime_of_departure");
        const grossTonnageInput = $("#id_gross_tonnage");
        const vesselTypeSelect = $("#id_vessel_type");
        const shippingAgent = $("#id_shipping_agent");
        const submitButton = $("button[type=submit][value=NEW]");
        const submitDraftButton = $("button[type=submit][value=DRAFT]");

        const toggleSubmitButton = function (state) {
            if (state) {
                submitButton.addClass("d-none");
                submitDraftButton.text(gettext("Continue"));
            } else {
                submitButton.removeClass("d-none");
                submitDraftButton.text(gettext("Save as draft"));
            }
        }

        const toggleNoPortOfCallState = function (disabled) {
            portOfCallSelect.attr("disabled", disabled);
            datetimeInputs.attr("disabled", disabled);
            grossTonnageInput.attr("disabled", disabled);
            vesselTypeSelect.attr("disabled", disabled);

            if (disabled) {
                portOfCallSelect.val(null);
                datetimeInputs.val(null);
                grossTonnageInput.val(null);
                // Enforce vessel type CRUISE
                vesselTypeSelect.val("CRUISE");
            }

            toggleSubmitButton(disabled === "disabled" || vesselTypeSelect.val() === "CRUISE");
        }

        // Update text on submit buttons, depending on the selected vessel type.
        vesselTypeSelect.on("change", function () {
            const vesselType = $(this).val();
            const state = vesselType === "CRUISE";
            toggleSubmitButton(state);
        });

        // Disable "port of call", etc. inputs, if "no port of call" is selected.
        // Enforce vessel type CRUISE if "no port of call" is selected.
        // Update text on submit button depending on the selected vessel type,
        noPortOfCallCheckbox.on("change", function () {
            const disabled = $(this).is(":checked") ? "disabled" : null;
            toggleNoPortOfCallState(disabled);
        });

        // Hook form submit
        form.on("submit", function (evt) {
            // Ensure that potentially disabled fields are still POSTed to server
            portOfCallSelect.attr("disabled", null);
            imoInput.attr("disabled", null);
            datetimeInputs.attr("disabled", null);
            grossTonnageInput.attr("disabled", null);
            vesselTypeSelect.attr("disabled", null);
            shippingAgent.attr("disabled", null);
        });

        const vesselType = vesselTypeSelect.val();
        toggleSubmitButton(vesselType === "CRUISE");

        const noPortOfCall = noPortOfCallCheckbox.is(":checked") ? "disabled" : null;
        toggleNoPortOfCallState(noPortOfCall);
    });
})();
