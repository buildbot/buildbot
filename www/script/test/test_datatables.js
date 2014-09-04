/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "datatables-extend"], function ($, dTables) {
    "use strict";

    var filter,
        oSettings = {
            oPreviousSearch: {
                sSearch: "teststring123"
            }
        };

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
});