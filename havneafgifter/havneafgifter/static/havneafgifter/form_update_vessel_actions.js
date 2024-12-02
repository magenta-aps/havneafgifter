/* eslint-disable no-unused-vars */
(function () {
  $(document).ready(function () {
    const onSaveVesselUpdateModal = new bootstrap.Modal(
      document.getElementById("#informShipUserOnSaveVesselChangeModal"), {}
    );

    const forms = $("form");
    const mainForm = $("form#main");

    let name;

    // Hook buttons submitting form
    $("form button[type=submit]").on("click", function (evt) {
      // Save button name (can be 'status' or 'confirm') as well as button value
      // (can be DRAFT or NEW), so we can read them in the form submit handler.
      name = $(this).attr("name");
    });

    // Hook form submit
    forms.on("submit", function (evt) {
      if (name === "status") {
        onSaveVesselUpdateModal.show()
        evt.preventDefault();
      }

      // Check if a "ship user" is confirming their choice (i.e., they are
      // returning from the confirmation modal.)
      if (name === "confirm") {
        // Check if we are currently already submitting the "main" form
        const formId = $(evt.target).attr("id");
        if (formId === "main") {
          // We are already submitting the "main" form.
          // Let the form submission proceed as normal, setting the hidden
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
