define(['moment'], function (moment) {
    "use strict";

    var momentExtend;

    momentExtend = {
        init: function() {
            //Extend our timings to be a bit more precise
            moment.lang('progress-bar-en', {
                relativeTime : {
                    future: "ETA: %s",
                    past:   "Overtime: %s",
                    s:  "%d seconds",
                    m:  "%d minute",
                    mm: "%d minutes",
                    h:  "%d hour",
                    hh: "%d hours",
                    d:  "a day",
                    dd: "%d days",
                    M:  "a month",
                    MM: "%d months",
                    y:  "a year",
                    yy: "%d years"
                }
            });

            moment.lang('en');
        }
    };

    return momentExtend;
});