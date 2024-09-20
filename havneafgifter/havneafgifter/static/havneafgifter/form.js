$(function () {
    $("input.datetimepicker").each(function () {
        new tempusDominus.TempusDominus(this, {
            display: {
                sideBySide: true,
                calendarWeeks: false,
                buttons: {
                    clear: true,
                }, components: {
                    seconds: true,
                },
            }, localization: {
                hourCycle: "h23",
                startOfTheWeek: 1,
                format: "yyyy-MM-dd HH:mm:ss"
            }
        });
    });
});