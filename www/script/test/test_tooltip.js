/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "helpers"], function ($, helpers) {
    "use strict";

    var $body = $("body"),
        $tooltip,
        msg = "Testing tooltip 1 2 3 <h4>Moo</h4>";

    describe("A tooltip", function () {
        beforeEach(function () {
            $tooltip = $("<div/>").attr("title", msg);
            helpers.tooltip($tooltip);
        });

        afterEach(function (done) {
            $tooltip.trigger('mouseout');
            $tooltip.remove();
            setTimeout(done, 250);
        });

        it("is visible when the mouse is over it", function () {
            expect($tooltip.attr("data-title")).toBeUndefined();
            expect($tooltip.attr("title")).toEqual(msg);
            expect($tooltip.html()).toEqual("");

            $tooltip.trigger('mouseover');

            var div = $body.find("div.tooltip-cont");
            expect($tooltip.attr("title")).toBeUndefined();
            expect($tooltip.attr("data-title")).toEqual(msg);
            expect(div.length).toEqual(1);
            expect(div.html()).toEqual(msg);
        });

        it("is not visible when the mouse is no longer over it", function (done) {
            $tooltip.trigger('mouseover');
            $tooltip.trigger('mouseout');

            setTimeout(function () {
                var div = $body.find("div.tooltip-cont");
                expect(div.length).toEqual(0);
                done();
            }, 250);

        });
    });
});