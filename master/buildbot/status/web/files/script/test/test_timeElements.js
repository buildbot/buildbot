/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "timeElements", "extend-moment", "moment", "helpers"], function ($, te, extend_moment, moment) {
    "use strict";

    function testElapsedTime(time, expectedText) {
        var $elem = $("<div/>");
        te.addElapsedElem($elem, time);
        te.updateTimeObjects();
        expect($elem.html()).toEqual(expectedText);
    }

    function testTimeAgo(time, expectedText) {
        var $elem = $("<div/>");
        te.addTimeAgoElem($elem, time);
        te.updateTimeObjects();
        expect($elem.html()).toEqual(expectedText);
    }

    function testProgressBar(time, eta, languageType, percent) {
        var $elem = $("<div/>").
            append($("<span/>").addClass("time-txt-js time-txt")).
            append($("<div/>").addClass("percent-inner-js percent-inner").
                append($("<div/>").addClass("progress-bar-overlay"))),
            $inner = $elem.children('.percent-inner-js');

        te.addProgressBarElem($elem, time, eta);
        te.updateTimeObjects();

        var old_lang = moment.lang();
        moment.lang(languageType);
        var etaEpoch = (moment.unix(time).startOf('second')) + (eta * 1000.0);
        expect($elem.text()).toEqual(moment(etaEpoch).startOf("second").fromServerNow());

        if (eta > 0 && percent !== undefined) {
            expect($inner.css("width")).toEqual(percent + "%");
        } else {
            expect($inner.css("width")).toEqual("100%");
        }

        moment.lang(old_lang);
    }

    // Setup the time elements
    te.init();

    describe("An elapsed time element", function () {
        beforeEach(function () {
            extend_moment.setServerTime(moment());
        });

        afterEach(function () {
            te.clearTimeObjects();
        });

        it("shows the correct time for 30 seconds", function () {
            var time = moment().subtract("seconds", 30).unix();
            testElapsedTime(time, "30 seconds");
        });

        it("shows the correct time for a minute", function () {
            var time = moment().subtract("minutes", 1).unix();
            testElapsedTime(time, "1 minute, 0 seconds");
        });

        it("shows the correct time for two minutes and 30 seconds", function () {
            var time = moment().subtract("minutes", 2).subtract("seconds", 30).unix();
            testElapsedTime(time, "2 minutes, 30 seconds");
        });

        it("shows the correct time for an hour", function () {
            var time = moment().subtract("hours", 1).unix();
            testElapsedTime(time, "1 hour, 0 minutes");
        });

        it("shows the correct time for two hours and 30 minutes", function () {
            var time = moment().subtract("hours", 2).subtract("minutes", 30).unix();
            testElapsedTime(time, "2 hours, 30 minutes");
        });

        it("shows the correct time for a day", function () {
            var time = moment().subtract("days", 1).unix();
            testElapsedTime(time, "a day");
        });

        it("shows the correct time for two days and 6 hours", function () {
            var time = moment().subtract("days", 2).subtract("hours", 6).unix();
            testElapsedTime(time, "2 days");
        });

        it("shows the correct time for two days and 12 hours", function () {
            var time = moment().subtract("days", 2).subtract("hours", 12).unix();
            testElapsedTime(time, "3 days");
        });

        it("shows the correct time for 30 seconds in the future", function () {
            var time = moment().add("seconds", 30).unix();
            testElapsedTime(time, "30 seconds");
        });
    });

    describe("A time ago time element", function () {
        beforeEach(function () {
            extend_moment.setServerTime(moment());
        });

        afterEach(function () {
            te.clearTimeObjects();
        });

        it("shows the correct time for 30 seconds", function () {
            var time = moment().subtract("seconds", 30).unix();
            testTimeAgo(time, "a few seconds ago");
        });

        it("shows the correct time for a minute", function () {
            var time = moment().subtract("minutes", 1).unix();
            testTimeAgo(time, "a minute ago");
        });

        it("shows the correct time for two minutes and 30 seconds", function () {
            var time = moment().subtract("minutes", 2).subtract("seconds", 30).unix();
            testTimeAgo(time, "3 minutes ago");
        });

        it("shows the correct time for an hour", function () {
            var time = moment().subtract("hours", 1).unix();
            testTimeAgo(time, "an hour ago");
        });

        it("shows the correct time for two hours and 30 minutes", function () {
            var time = moment().subtract("hours", 2).subtract("minutes", 30).unix();
            testTimeAgo(time, "3 hours ago");
        });

        it("shows the correct time for a day", function () {
            var time = moment().subtract("days", 1).unix();
            testTimeAgo(time, "a day ago");
        });

        it("shows the correct time for two days", function () {
            var time = moment().subtract("days", 2).unix();
            testTimeAgo(time, "2 days ago");
        });
    });


    describe("A progress bar time element", function () {
        var serverTimeOffset;
        beforeEach(function () {
            serverTimeOffset = moment().startOf("second");
            extend_moment.setServerTime(serverTimeOffset);
        });

        afterEach(function () {
            te.clearTimeObjects();
        });

        it("shows the correct time for 30 seconds without eta", function () {
            var time = serverTimeOffset.subtract("seconds", 30).unix();
            testProgressBar(time, 0, "progress-bar-no-eta-en");
        });

        it("shows the correct time for 90 seconds with eta of 180 seconds", function () {
            var time = serverTimeOffset.subtract("seconds", 90).unix();
            testProgressBar(time, 90, "progress-bar-en", 50);
        });

        it("shows the overtime for 30 seconds with eta of 30 seconds", function () {
            var time = serverTimeOffset.subtract("seconds", 60).unix();
            testProgressBar(time, -1, "progress-bar-en", 100);
        });
    });

    describe("Time elements with server time of", function () {
        afterEach(function () {
            te.clearTimeObjects();
        });

        describe("40 seconds ago", function () {
            var serverTimeOffset;

            beforeEach(function () {
                serverTimeOffset = moment().subtract("seconds", 40);
                extend_moment.setServerTime(serverTimeOffset);
            });

            it("shows the correct time for one minute ago", function (done) {
                var time = serverTimeOffset.subtract("seconds", 59).unix();
                setTimeout(function () {
                    testTimeAgo(time, "a minute ago");
                    done();
                }, 1250);
            });

            it("shows the correct time for one minute elapsed", function () {
                var time = serverTimeOffset.subtract("minute", 1).unix();
                testElapsedTime(time, "1 minute, 0 seconds");
            });

            it("shows the correct time for one minute 15 seconds elapsed", function () {
                var time = serverTimeOffset.subtract("minute", 1).subtract("seconds", 15).unix();
                testElapsedTime(time, "1 minute, 15 seconds");
            });

            it("shows the correct time for two hours and 30 minutes", function () {
                var time = serverTimeOffset.subtract("hours", 2).subtract("minutes", 30).unix();
                testTimeAgo(time, "3 hours ago");
            });

            it("shows the correct time for one minute 16 seconds elapsed", function (done) {
                var time = serverTimeOffset.subtract("minute", 1).subtract("seconds", 15).unix();
                setTimeout(function () {
                    testElapsedTime(time, "1 minute, 16 seconds");
                    done();
                }, 1001);
            });
        });

        describe("40 seconds in the future", function () {
            var serverTimeOffset;

            beforeEach(function () {
                serverTimeOffset = moment().add("seconds", 40);
                extend_moment.setServerTime(serverTimeOffset);
            });

            it("shows the correct time for one minute ago", function () {
                var time = serverTimeOffset.subtract("minute", 1).unix();
                testTimeAgo(time, "a minute ago");
            });

            it("shows the correct time for one minute elapsed", function () {
                var time = serverTimeOffset.subtract("minute", 1).unix();
                testElapsedTime(time, "1 minute, 0 seconds");
            });

            it("shows the correct time for one minute 15 seconds elapsed", function () {
                var time = serverTimeOffset.subtract("minute", 1).subtract("seconds", 15).unix();
                testElapsedTime(time, "1 minute, 15 seconds");
            });

            it("shows the correct time for two hours and 30 minutes", function () {
                var time = serverTimeOffset.subtract("hours", 2).subtract("minutes", 30).unix();
                testTimeAgo(time, "3 hours ago");
            });

            it("shows the correct time for one minute 16 seconds elapsed", function (done) {
                var time = serverTimeOffset.subtract("minute", 1).subtract("seconds", 15).unix();
                setTimeout(function () {
                    testElapsedTime(time, "1 minute, 16 seconds");
                    done();
                }, 1001);
            });
        });
    });
});