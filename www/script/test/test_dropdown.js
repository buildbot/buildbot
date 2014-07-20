/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "ui.dropdown"], function ($, pd) {
    "use strict";

    var $body = $("body"),
        $dropdownButton,
        $closeButton;

    //Init the module
    pd.init();

    function addDropdownToDOM($elem) {
        $body.append($elem);
        $closeButton = $dropdownButton.find(".close-btn");
    }

    function removeDropdownFromDOM($elem) {
        $elem.remove();
        $(document).off();
        $(window).off();
    }

    function checkDocumentHasNoEvents() {
        it("has removed all events", function () {
            $dropdownButton.hideDropdown();

            var documentEvents = $._data(document, "events"),
                windowEvents = $._data(window, "events");

            if (documentEvents !== undefined && !$.isEmptyObject(documentEvents)) {
                expect(Object.keys(documentEvents).length).toEqual(0);
            }

            if (windowEvents !== undefined && !$.isEmptyObject(windowEvents)) {
                expect(Object.keys(windowEvents).length).toEqual(0);
            }
        });
    }

    function dropdownCanBeClosed() {
        it("has a close button", function () {
            expect($closeButton).toBeDefined();
        });

        it("can be closed", function (done) {
            $dropdownButton.options({
                onHide: function () {
                    var $div = $dropdownButton.find("div").first();
                    expect($div.length).toEqual(1);
                    expect($div.css("display")).toEqual("none");

                    if (!$.isEmptyObject($._data(document, "events"))) {
                        expect(Object.keys($._data(document, "events")).length).toEqual(0);
                    }
                    done();
                }
            });

            $dropdownButton.hideDropdown();
        });
    }

    describe("A basic dropdown", function () {
        beforeEach(function (done) {
            $(document).off();
            $(window).off();

            $dropdownButton = $("<div/>").dropdown({
                html: "Testing content",
                animated: false,
                onShow: function () {
                    done();
                }
            });
            addDropdownToDOM($dropdownButton);
            $dropdownButton.click();
        });

        afterEach(function () {
            removeDropdownFromDOM($dropdownButton);
            $(document).off();
        });

        it("renders correctly", function () {
            var $div = $dropdownButton.find("div").first();
            expect($div.length).toEqual(1);
            expect($div.hasClass("more-info-box")).toBeTruthy();
            expect($div.is(':visible')).toBeTruthy();
        });

        it("contains the given body", function () {
            expect($dropdownButton.html()).toContain("Testing content");
        });

        dropdownCanBeClosed();
        checkDocumentHasNoEvents();
    });

    describe("An async dropdown", function () {
        beforeEach(function (done) {
            $dropdownButton = $("<div/>").dropdown({
                url: "base/test/test_data.html",
                animated: false,
                onShow: function () {
                    done();
                }
            });
            addDropdownToDOM($dropdownButton);
            $dropdownButton.click();
        });

        afterEach(function () {
            removeDropdownFromDOM($dropdownButton);
        });

        it("renders correctly", function () {
            var $div = $dropdownButton.find("div").first();
            expect($div.length).toEqual(1);
            expect($div.hasClass("more-info-box")).toBeTruthy();
            expect($div.is(':visible')).toBeTruthy();
        });

        it("contains the given body", function () {
            var dropdownBody = '<h1>Test Header</h1><p>Test Paragraph</p>';
            expect($dropdownButton.html()).toContain(dropdownBody);
        });

        dropdownCanBeClosed();
        checkDocumentHasNoEvents();
    });
});