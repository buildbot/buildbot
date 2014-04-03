define(['moment', 'helpers'], function (moment) {
    "use strict";

    var momentExtend;

    var MINUTE = 60;
    var HOUR = MINUTE * 60;

    momentExtend = {
        init: function () {
            //Extend our timings to be a bit more precise
            moment.lang('progress-bar-en', {
                relativeTime: {
                    future: "ETA: %s",
                    past: "Overtime: %s",
                    s: "%d seconds",
                    m: momentExtend.parseMinutesSeconds,
                    mm: momentExtend.parseMinutesSeconds,
                    h: momentExtend.parseHoursMinutes,
                    hh: momentExtend.parseHoursMinutes,
                    d: "a day",
                    dd: "%d days",
                    M: "a month",
                    MM: "%d months",
                    y: "a year",
                    yy: "%d years"
                }
            });

            moment.lang('progress-bar-no-eta-en', {
                relativeTime: {
                    future: "%s",
                    past: "Elapsed: %s",
                    s: "%d seconds",
                    m: momentExtend.parseMinutesSeconds,
                    mm: momentExtend.parseMinutesSeconds,
                    h: momentExtend.parseHoursMinutes,
                    hh: momentExtend.parseHoursMinutes,
                    d: "a day",
                    dd: "%d days",
                    M: "a month",
                    MM: "%d months",
                    y: "a year",
                    yy: "%d years"
                }
            });

            moment.lang('en');
        },
        parseMinutesSeconds: function (number, withoutSuffix, string, isFuture, data) {
            var seconds = parseInt(data['seconds']);
            var secondsLeft = seconds % MINUTE;
            if (seconds < MINUTE) {
                return "{0} seconds".format(secondsLeft);
            }
            else if (seconds < (MINUTE * 2)) {
                return "1 minute, {0} seconds".format(secondsLeft);
            }
            else {
                var minutes = Math.floor(seconds / MINUTE);
                return "{0} minutes, {1} seconds".format(minutes, secondsLeft);
            }
        },
        parseHoursMinutes: function (number, withoutSuffix, string, isFuture, data) {
            var seconds = parseInt(data['seconds']);
            var minutesLeft = Math.floor(((seconds % HOUR)  / MINUTE));

            if (seconds < HOUR) {
                var minutes = Math.floor(seconds / MINUTE);
                var secondsLeft = seconds % MINUTE;
                return "{0} minutes, {1} seconds".format(minutes, secondsLeft);
            }
            else if (seconds < (HOUR * 2)) {
                return "1 hour, {0} minutes".format(minutesLeft);
            }
            else {
                var hours = Math.floor(seconds / HOUR);
                return "{0} hours, {1} minutes".format(hours, minutesLeft);
            }
        }
    };

    return momentExtend;
});