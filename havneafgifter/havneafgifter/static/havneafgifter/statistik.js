$(function () {
    $("[data-select]").each(function () {
        const $this = $(this);
        const field = $("[name=" + $this.data("select") + "]");
        $this.on("click", function () {
            field.find("option").prop("selected", true);
        });
    });
    $("[data-deselect]").each(function () {
        const $this = $(this);
        const field = $("[name=" + $this.data("deselect") + "]");
        $this.on("click", function () {
            field.find("option").prop("selected", false);
        });
    });
    $("[data-clear]").each(function () {
        const $this = $(this);
        const names = $this.data("clear").split(",");
        const selector = [];
        for (name of names) {
            selector.push(`[name=${name}]`);
        }
        const field = $(selector.join(","));
        $this.on("click", function () {
            field.val("");
        });
    });
});
