/*global define*/
define(['jquery'], function ($) {

    "use strict";

    return {
        isSmallScreen: function () {
            var smallScreen = $(window).width() <= 570;
            return smallScreen;
        },
        isMediumScreen: function () {
            var mediumScreen = $(window).width() <= 1024;
            return mediumScreen;
        },
        isLargeScreen: function () {
            var largeScreen = $(window).width() >= 1025;
            return largeScreen;
        }
    };
});