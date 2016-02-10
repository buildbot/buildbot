/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(function (require) {
    "use strict";

    var $ = require("jquery"),
        moment=require("moment"),
        helpers = require('helpers'),
        rtTestReport = require("rtTestReport");


    describe("Data time is parsed respecting data-time-unit attribute", function () {
        it("time parsed if unix unit(by default)", function () {
            var time = 123456;
            var element = $("<div data-time="+time+">"+time+"</div>")
            var expected = moment.utc(time * 1000.0).format(" (HH:mm:ss)");

            rtTestReport.parseTimes([element]);

            expect($(element).text()).toContain(expected);
        });

        it("time parsed for millisecond unit - 'ms'", function () {
            var time = 123456;
            var element = $("<div data-time="+time+" data-time-unit='ms'>"+time+"</div>")
            var expected = moment.utc(time).format(" (HH:mm:ss)");

            rtTestReport.parseTimes([element]);

            expect($(element).text()).toContain(expected);
        });
    });
});
