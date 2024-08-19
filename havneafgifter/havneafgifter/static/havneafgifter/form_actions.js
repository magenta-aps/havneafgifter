(function () {
    $(document).ready(function () {
        const onSaveModal = new bootstrap.Modal(document.getElementById("#informShipUserOnSaveModal"), {});
        const onSubmitModal = new bootstrap.Modal(document.getElementById("#informShipUserOnSubmitModal"), {});
        const forms = $("form");
        const mainForm = $("form#main");
        const hiddenStatus = $("input[name=status]", mainForm);
        const userType = mainForm.data("user-type");
        let name;
        let value;

        // Hook buttons submitting form
        $("form button[type=submit]").on("click", function (evt) {
            // Save button name (can be 'status' or 'confirm') as well as button value
            // (can be DRAFT or NEW), so we can read them in the form submit handler.
            name = $(this).attr("name");
            value = $(this).val();
        });

        // Hook form submit
        forms.on("submit", function (evt) {
            // Bail early if user is not a ship user, or we are on step 1 and user is
            // creating a draft cruise tax form. In that case, they should only see the
            // modals on step 3.
            const vesselType = $("#id_vessel_type", mainForm);
            if ((userType !== "ship") || (vesselType.val() === "CRUISE")) {
                hiddenStatus.remove();
                return;
            }

            // If a "ship user" is clicking "Submit" or "Save as draft", show a
            // confirmation popup (modal.) The "ship user" must then either confirm
            // or abort the action.
            if ((name === "status") && (userType === "ship")) {
                let modal;

                if (value === "DRAFT") {
                    modal = onSaveModal;
                } else if (value === "NEW") {
                    modal = onSubmitModal;
                }

                if (modal !== undefined) {
                    evt.preventDefault();
                    modal.show();
                }
            }

            // Check if a "ship user" is confirming their choice (i.e., they are
            // returning from the confirmation modal.)
            if (name === "confirm") {
                // Check if we are currently already submitting the "main" form
                const formId = $(evt.target).attr("id");
                if (formId === "main") {
                    // We are already submitting the "main" form.
                    // Let the form submission proceed as normal, setting the hidden
                    // `status` field to either `DRAFT` or `NEW`.
                    hiddenStatus.val(value);
                    return true;
                } else {
                    // Don't submit *this* form (which lives on the modal), but rather
                    // the "main" form on the page itself.
                    mainForm.submit();
                    return false;
                }
            }
        });
    });
})();
