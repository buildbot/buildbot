/*global define, console*/
define(['moment', 'helpers'], function (moment) {
    

    var momentExtend;
    var serverOffset;
    var MINUTE = 60;
    var HOUR = MINUTE * 60;

    moment.fn.fromServerNow = function () {
        if (serverOffset !== undefined) {
            return this.subtract(serverOffset).startOf("second").fromNow();
        }
        return this.fromNow();
    };

    momentExtend = {
        init: function () {
            //Extend our timings to be a bit more precise
            var timeDict = momentExtend.getRelativeTimeDict();
            timeDict.future = "ETA: %s";
            timeDict.past = "Overtime: %s";
            moment.lang('progress-bar-en', {relativeTime: timeDict});

            timeDict = momentExtend.getRelativeTimeDict();
            timeDict.future = "%s";
            timeDict.past = "Elapsed: %s";
            moment.lang('progress-bar-no-eta-en', {relativeTime: timeDict});

            timeDict = momentExtend.getRelativeTimeDict();
            timeDict.past = "%s";
            timeDict.future = "%s";
            moment.lang('waiting-en', {relativeTime: timeDict});

            //Set default language
            moment.lang('en');
        },
        setServerTime: function (serverTime) {
            serverOffset = moment(serverTime).diff(new Date());
            console.log("Time Offset: {0}".format(serverOffset));
        },
        getRelativeTimeDict: function () {
            return {
                s: momentExtend.parseMinutesSeconds,
                ss: momentExtend.parseMinutesSeconds,
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
            };
        },
        parseMinutesSeconds: function (number, withoutSuffix, string, isFuture, data) {
            var seconds = parseInt(data.seconds, 10);
            var secondsLeft = seconds % MINUTE;
            if (seconds < MINUTE) {
                return "{0} seconds".format(secondsLeft);
            }
            if (seconds < (MINUTE * 2)) {
                return "1 minute, {0} seconds".format(secondsLeft);
            }

            var minutes = Math.floor(seconds / MINUTE);
            return "{0} minutes, {1} seconds".format(minutes, secondsLeft);
        },
        parseHoursMinutes: function (number, withoutSuffix, string, isFuture, data) {
            var seconds = parseInt(data.seconds, 10);
            var minutesLeft = Math.floor(((seconds % HOUR) / MINUTE));

            if (seconds < HOUR) {
                var minutes = Math.floor(seconds / MINUTE);
                var secondsLeft = seconds % MINUTE;
                return "{0} minutes, {1} seconds".format(minutes, secondsLeft);
            }
            if (seconds < (HOUR * 2)) {
                return "1 hour, {0} minutes".format(minutesLeft);
            }

            var hours = Math.floor(seconds / HOUR);
            return "{0} hours, {1} minutes".format(hours, minutesLeft);
        },
        getServerTime: function (time) {
            if (time === undefined) {
                return moment().add(momentExtend.getServerOffset());
            }

            return moment(time).add(momentExtend.getServerOffset());
        },
        getServerOffset: function () {
            return serverOffset;
        },
        getDateFormatted: function (unixTimeStamp) {
            return moment.unix(unixTimeStamp).format('MMMM DD, H:mm:ss');
        }
    };

    return momentExtend;
});