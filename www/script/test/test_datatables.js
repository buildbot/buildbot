/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "datatables-extend", "helpers"], function ($, dTables, helpers) {
    "use strict";

    var filter,
        oSettings = {
            oPreviousSearch: {
                sSearch: "teststring123"
            }
        },
        buildResults = helpers.cssClassesEnum;

    function setupFilter(index, searchString) {
        // Init the single column searching
        dTables.initSingleColumnFilter(index);
        filter = $.fn.dataTableExt.afnFiltering[0];
        oSettings.oPreviousSearch.sSearch = searchString;
    }

    describe("Filtering a single column", function () {
        var data = [
            ["testfail", "moo", "12three"],
            ["teststring123", "moo", "three"],
            ["asdasdteststring123saddaa", "moo", "five"],
            ["testfail", "teststring123", "six"]
        ];

        afterEach(function afterEach() {
            $.fn.dataTableExt.afnFiltering = [];
        });

        it("filters the correct results on column 0", function () {
            setupFilter(0, "teststring123");
            var results = [false, true, true, false];

            $.each(data, function testFilter(i, obj) {
                expect(filter(oSettings, obj)).toEqual(results[i]);
            });
        });

        it("filters the correct results on column 2", function () {
            setupFilter(2, "ee");
            var results = [true, true, false, false];

            $.each(data, function testFilter(i, obj) {
                expect(filter(oSettings, obj)).toEqual(results[i]);
            });
        });

        it("filters HTML elements correctly", function () {
            setupFilter(0, "fail");
            var results = [true, false, false, true],
                testHTML = [];

            $.each(data, function createTestHTMLData(i, obj) {
                testHTML.push([]);
                $.each(obj, function (y, o) {
                    testHTML[i].push("<p>" + o + "</p>");
                });
            });

            $.each(testHTML, function testFilter(i, obj) {
                expect(filter(oSettings, obj)).toEqual(results[i]);
            });
        });
    });

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