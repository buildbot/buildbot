/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "helpers"], function ($, helpers) {
    "use strict";

    describe("A build", function () {

        var now = new Date(),
            build = {
                times: []
            };

        helpers.settings = function () {
            return {oldBuildDays: 7}
        };

        it("is old", function () {
            build.times = [new Date().setDate(now.getDate() - 8) / 1000.0];
            expect(helpers.isBuildOld(build)).toBeTruthy();

            build.times = [new Date().setDate(now.getDate() - 50) / 1000.0];
            expect(helpers.isBuildOld(build)).toBeTruthy();
        });

        it("is new", function () {
            build.times = [new Date().setDate(now.getDate() - 1) / 1000.0];
            expect(helpers.isBuildOld(build)).toBeFalsy();

            build.times = [new Date().setDate(now.getDate() - 3) / 1000.0];
            expect(helpers.isBuildOld(build)).toBeFalsy();
        });
    });


});