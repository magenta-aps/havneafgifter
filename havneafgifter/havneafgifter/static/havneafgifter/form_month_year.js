$(function () {
    $("input.datetimepicker").each(function () {
        new tempusDominus.TempusDominus(this, {
            display: {
                sideBySide: false,
                calendarWeeks: false,
                buttons: {
                    clear: true,
                    today: true,
                }, components: {
                    date: false,
                    clock: false,
                    hours: false,
                    minutes: false,
                },
            }, localization: {
                hourCycle: "h23",
                startOfTheWeek: 1,
                format: "yyyy-MM"
            }
        });
    });
});
