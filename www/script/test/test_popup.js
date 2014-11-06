/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "ui.popup"], function ($, popup) {
    "use strict";

    var $popup,
        $closeButton,
        html = "<span>Test String</span>",
        $body = $("body");

    function addPopuptoDOM($popupElem) {
        $body.append($popupElem);
        $closeButton = $popupElem.find(".close-btn");
    }

    function removePopupFromDOM($popupElem) {
        $popupElem.remove();
        $(document).off();
        $(window).off();
    }

    function checkPopupIsVisibleAndCorrect(popupBody) {
        it("contains the given body", function () {
            expect($popup.html()).toContain(popupBody);
        });

        it("is visible", function () {
            expect($popup.is(':visible')).toBeTruthy();
        });
    }

    function checkPopupCanBeClosed() {
        it("has a close button", function () {
            expect($closeButton).toBeDefined();
        });

        it("can be closed", function (done) {
            $popup.options({
                onHide: function () {
                    expect($popup.css("display")).toEqual("none");
                    done();
                }
            });

            $popup.hidePopup();
        });
    }

    function checkDocumentHasNoEvents() {
        it("has removed all events", function () {
            $popup.hidePopup();
            
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

    describe("A popup", function () {

        beforeEach(function () {
            $(document).off();
            $(window).off();
        });

        afterEach(function () {
            removePopupFromDOM($popup);
        });

        describe("with HTML", function () {

            beforeEach(function () {
                $popup = $("<div/>").popup({
                    html: html,
                    animate: false
                });

                addPopuptoDOM($popup);
            });

            checkPopupIsVisibleAndCorrect(html);
            checkPopupCanBeClosed();
            checkDocumentHasNoEvents();
        });

        describe("that is shown manually", function () {

            beforeEach(function () {
                $popup = $("<div/>").popup({
                    html: html,
                    animate: false,
                    autoShow: false
                });

                addPopuptoDOM($popup);
            });

            it("is not visible", function () {
                expect($popup.is(':visible')).toBeFalsy();
            });

            it("is visible", function () {
                $popup.showPopup();
                expect($popup.is(':visible')).toBeTruthy();
            });

            it("contains the given body", function () {
                expect($popup.html()).toContain(html);
            });

            checkPopupCanBeClosed();
            checkDocumentHasNoEvents();
        });

        describe("that is asynchronous", function () {

            beforeEach(function (done) {
                $popup = $("<div/>").popup({
                    url: "base/script/test/test_data.html",
                    animate: false,
                    onShow: function () {
                        // Wait for popup to initialize close first
                        setTimeout(done, 2);
                    }
                });

                addPopuptoDOM($popup);
            });

            var popupBody = '<h1>Test Header</h1><p>Test Paragraph</p>';
            checkPopupIsVisibleAndCorrect(popupBody);
            checkPopupCanBeClosed();
            checkDocumentHasNoEvents();
        });

        describe("that has animation", function () {

            beforeEach(function (done) {
                $popup = $("<div/>").popup({
                    html: html,
                    animate: true,
                    onShow: function () {
                        done();
                    }
                });

                addPopuptoDOM($popup);
            });

            checkPopupIsVisibleAndCorrect(html);
            checkPopupCanBeClosed();
            checkDocumentHasNoEvents();
        });

        describe("with destroyAfter", function () {

            beforeEach(function () {
                $popup = $("<div/>").popup({
                    html: html,
                    animate: false,
                    destroyAfter: true
                });

                addPopuptoDOM($popup);
            });

            checkPopupIsVisibleAndCorrect(html);
            checkPopupCanBeClosed();

            it("has been destroyed", function () {
                $popup.attr("id", "popup");
                $body.append($popup);
                var $domPopup = $("#popup");
                expect($domPopup.length).toEqual(1);
                $popup.hidePopup();
                expect($($domPopup.selector).length).toEqual(0);
            });

            checkDocumentHasNoEvents();
        });
    });
});