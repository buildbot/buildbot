/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "project/datatables-extend", "helpers"], function ($, dTables, helpers) {
    "use strict";

    var filter,
        oSettings = {
            oPreviousSearch: {
                sSearch: "teststring123"
            }
        },
        buildResults = helpers.cssClassesEnum;

    describe("Sorting by the status column", function () {
        var sortFunc = dTables.initBuilderStatusSort(),
            data = [],
            expectedResult = [
                {results: buildResults.FAILURE},
                {results: buildResults.DEPENDENCY_FAILURE},
                {results: buildResults.SUCCESS},
                {results: buildResults.NOT_REBUILT},
                {results: buildResults.CANCELED},
                {results: buildResults.RETRY},
                {results: buildResults.SKIPPED},
                {results: buildResults.EXCEPTION},
                {},
                null
            ],
            reversedExpectedResult = [
                {results: buildResults.EXCEPTION},
                {results: buildResults.SKIPPED},
                {results: buildResults.RETRY},
                {results: buildResults.CANCELED},
                {results: buildResults.NOT_REBUILT},
                {results: buildResults.SUCCESS},
                {results: buildResults.DEPENDENCY_FAILURE},
                {results: buildResults.FAILURE},
                {},
                null
            ];

        beforeEach(function beforeEach() {
            data = [
                null,
                {results: buildResults.SUCCESS},
                {results: buildResults.FAILURE},
                {results: buildResults.CANCELED},
                {results: buildResults.EXCEPTION},
                {},
                {results: buildResults.NOT_REBUILT},
                {results: buildResults.RETRY},
                {results: buildResults.SKIPPED},
                {results: buildResults.DEPENDENCY_FAILURE}
            ];
        });

        afterEach(function afterEach() {
            $.fn.dataTableExt.afnFiltering = [];
        });

        it("sorts correctly", function () {
            var result = data.sort(function (a, b) {
                return sortFunc(a, b, false);
            });

            expect(result).toEqual(expectedResult);
        });

        it("sorts correctly in reverse", function () {
            var result = data.sort(function (a, b) {
                return sortFunc(a, b, true);
            });

            expect(result).toEqual(reversedExpectedResult);
        });

    });

    describe("Sorting by the status column", function () {
        var sortFunc = dTables.initBuilderNameSort(),
            data = [],
            expectedResult = [
                "[ABV] ABuildVerification",
                "ACuildVerification [ABV]",
                "[ABV] Build Things",
                "[ABV] Test This",
                "ZEnd [ABV]",
                "Test That",
                "ZEnd",
                "[Nightly] Woof",
                "zEnd"
            ];

        beforeEach(function beforeEach() {
            data = [
                "Test That",
                "ACuildVerification [ABV]",
                "[ABV] ABuildVerification",
                "ZEnd [ABV]",
                "zEnd",
                "[ABV] Build Things",
                "[Nightly] Woof",
                "ZEnd",
                "[ABV] Test This"
            ];
        });

        afterEach(function afterEach() {
            $.fn.dataTableExt.afnFiltering = [];
        });

        it("sorts correctly", function () {
            var result = data.sort(function (a, b) {
                return sortFunc(a, b, false);
            });

            expect(result).toEqual(expectedResult);
        });

        it("sorts correctly in reverse", function () {
            var result = data.sort(function (a, b) {
                return sortFunc(a, b, true);
            });

            expect(result).toEqual(expectedResult.reverse());
        });

    });
});