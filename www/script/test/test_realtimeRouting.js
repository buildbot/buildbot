/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(function (require) {
    "use strict";

    var $ = require("jquery"),
        helpers = require('helpers'),
        realtimerouting = require("realtimerouting"),
        rtGlobal = require("rtGlobal");


    describe("Add page init handler", function () {
        it("page init handler has been executed", function (done) {
            var page_id = "test_handler";
            realtimerouting.addPageInitHandler(page_id, done);

            helpers.getCurrentPage = function() { return page_id; }
            realtimerouting.init();
        });

        it("rtGlobal init handler has been executed", function (done) {
            rtGlobal.init  = done;

            helpers.getCurrentPage = function() { return ""; }
            realtimerouting.init();
        });
    });
});
