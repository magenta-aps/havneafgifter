$(function () {
    $("[data-select]").each(function () {
        const $this = $(this);
        const field = $("[name=" + $this.data("select") + "]");
        $this.on("click", function () {
            console.log("select",$this.data(),field);
            field.find("option").prop("selected", true);
        });
    });
    $("[data-deselect]").each(function () {
        const $this = $(this);
        const field = $("[name=" + $this.data("deselect") + "]");
        $this.on("click", function () {
            console.log("deselect",$this.data(),field);
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
    $("input.datetimepicker").each(function () {
        new tempusDominus.TempusDominus(
            this,
            {
                display: {
                    sideBySide: true,
                    calendarWeeks: false,
                    buttons: {
                        clear: true,
                    },
                    components: {
                        seconds: true,

                    },
                },
                localization: {
                    hourCycle: "h23",
                    startOfTheWeek: 1,
                    format: "yyyy-MM-dd HH:mm:ss"
                }

            }
        )
    });
});
