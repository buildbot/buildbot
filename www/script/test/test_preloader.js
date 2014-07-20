/*global define, describe, it, expect, beforeEach, afterEach*/
define(["jquery", "ui.preloader"], function ($, pd) {
    "use strict";

    var $body = $("body"),
        $preloader;

    function rendersCorrectly(visible) {
        it("renders correctly", function () {
            var $bowl_ringG = $preloader.find("div#bowl_ringG"),
                $ball_holderG = $bowl_ringG.find("div.ball_holderG"),
                $ballG = $ball_holderG.find("div.ballG");

            expect($bowl_ringG.length).toEqual(1);
            expect($ball_holderG.length).toEqual(1);
            expect($ballG.length).toEqual(1);
            expect($preloader.is(':visible')).toEqual(visible);
        });
    }

    describe("A preloader", function () {
        describe("with default options", function () {
            beforeEach(function () {
                $preloader = $("<div/>").preloader({
                    autoShow: false
                });
                $body.append($preloader);
            });

            afterEach(function () {
                $preloader.remove();
            });

            rendersCorrectly(false);

            it("is visible when shown", function () {
                expect($preloader.is(':visible')).toBeFalsy();
                $preloader.preloader("showPreloader");
                expect($preloader.is(':visible')).toBeTruthy();
            });

            it("is not visible when hidden", function () {
                $preloader.preloader("showPreloader");
                expect($preloader.is(':visible')).toBeTruthy();
                $preloader.preloader("hidePreloader");
                expect($preloader.is(':visible')).toBeFalsy();
            });

            it("can be destroyed", function () {
                $preloader.preloader("destroy");
                expect($preloader.find("div").length).toEqual(0);
            });
        });

        describe("with autoShow", function () {
            beforeEach(function () {
                $preloader = $("<div/>").preloader({
                    autoShow: true
                });
                $body.append($preloader);
            });

            afterEach(function () {
                $preloader.remove();
            });


            it("is visible automatically", function () {
                expect($preloader.is(':visible')).toBeTruthy();
            });

            rendersCorrectly(true);
        });

        describe("with destroyAfter", function () {
            beforeEach(function () {
                $preloader = $("<div/>").preloader({
                    destroyAfter: true
                });
                $body.append($preloader);
            });

            afterEach(function () {
                $preloader.remove();
            });

            it("is destroyed when hidden", function () {
                $preloader.preloader("hidePreloader");
                expect($preloader.is(':visible')).toBeFalsy();
                expect($preloader.find("div").length).toEqual(0);
            });

            rendersCorrectly(true);
        });

        describe("with timeout", function () {
            beforeEach(function () {
                $preloader = $("<div/>").preloader({
                    timeout: 10
                });
                $body.append($preloader);
            });

            afterEach(function () {
                $preloader.remove();
            });

            it("is hidden when timed out", function (done) {
                expect($preloader.is(':visible')).toBeTruthy();
                setTimeout(function () {
                    expect($preloader.is(':visible')).toBeTruthy();
                }, 5);
                setTimeout(function () {
                    expect($preloader.is(':visible')).toBeFalsy();
                    done();
                }, 11);
            });

            rendersCorrectly(true);
        });
    });
});