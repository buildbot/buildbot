/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(["jquery", "rtBuilders"], function ($, rtBuilders) {
    "use strict";

    var abvTag = [
            ["ABV"]
        ],
        abvNightlyTag = [
            ["ABV", "Nightly"]
        ],
        noTags = [
            []
        ],
        builderInfo = [
            abvTag,
            noTags,
            abvNightlyTag
        ];

    describe("Builder tags", function () {
        var filter = rtBuilders.filterByTags(0);

        it("are filtered", function () {
            rtBuilders.getSelectedTags = function () {
                return ["ABV"];
            };

            var expectedResult = [
                    abvTag, abvNightlyTag
                ],
                result = $.grep(builderInfo, function (a, b) {
                    return filter(b, a);
                });
            expect(expectedResult).toEqual(result);
        });

        it("are not filtered when no tags are selected", function () {
            rtBuilders.getSelectedTags = function () {
                return [];
            };

            var expectedResult = [
                    abvTag, noTags, abvNightlyTag
                ],
                result = $.grep(builderInfo, function (a, b) {
                    return filter(b, a);
                });
            expect(expectedResult).toEqual(result);
        });

        it("shows only builders without tags when None is given", function () {
            rtBuilders.getSelectedTags = function () {
                return [rtBuilders.noTag];
            };

            var expectedResult = [
                    noTags
                ],
                result = $.grep(builderInfo, function (a, b) {
                    return filter(b, a);
                });
            expect(expectedResult).toEqual(result);
        });

        it("filters correctly with None and a filter", function () {
            rtBuilders.getSelectedTags = function () {
                return ["Nightly", rtBuilders.noTag];
            };

            var expectedResult = [
                    noTags,
                    abvNightlyTag
                ],
                result = $.grep(builderInfo, function (a, b) {
                    return filter(b, a);
                });
            expect(expectedResult).toEqual(result);
        });
    });
});
