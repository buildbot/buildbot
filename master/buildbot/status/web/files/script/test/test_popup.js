/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "popup"], function ($, popup) {
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

    describe("A basic popup", function () {

        beforeEach(function () {
            $popup = $("<div/>").popup({
                html: html,
                animate: false
            });

            addPopuptoDOM($popup);
        });

        afterEach(function () {
            removePopupFromDOM($popup);
        });

        checkPopupIsVisibleAndCorrect(html);
        checkPopupCanBeClosed();
    });

    describe("A manual showing popup", function () {

        beforeEach(function () {
            $popup = $("<div/>").popup({
                html: html,
                animate: false,
                autoShow: false
            });

            addPopuptoDOM($popup);
        });

        afterEach(function () {
            removePopupFromDOM($popup);
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
    });

    describe("An async popup", function () {

        beforeEach(function (done) {
            $popup = $("<div/>").popup({
                url: "base/test/test_data.html",
                animate: false,
                onShow: function () {
                    done();
                }
            });

            addPopuptoDOM($popup);
        });

        afterEach(function () {
            removePopupFromDOM($popup);
        });

        var popupBody = '<h1>Test Header</h1><p>Test Paragraph</p>';
        checkPopupIsVisibleAndCorrect(popupBody);
        checkPopupCanBeClosed();
    });

    describe("An animated popup", function () {

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

        afterEach(function () {
            removePopupFromDOM($popup);
        });

        checkPopupIsVisibleAndCorrect(html);
        checkPopupCanBeClosed();

    });

    describe("A destructive popup", function () {

        beforeEach(function () {
            $popup = $("<div/>").popup({
                html: html,
                animate: false,
                destroyAfter: true
            });

            addPopuptoDOM($popup);
        });

        afterEach(function () {
            removePopupFromDOM($popup);
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
    });
});