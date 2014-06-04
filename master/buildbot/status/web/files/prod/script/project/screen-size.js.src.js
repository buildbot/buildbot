/*global define*/
define(['jquery'], function ($) {

    

    return {
        isSmallScreen: function () {
            var smallScreen = $(window).width() <= 768;
            return smallScreen;
        },
        isMediumScreen: function () {
            var mediumScreen = $(window).width() <= 992;
            return mediumScreen;
        },
        isLargeScreen: function () {
            var largeScreen = $(window).width() >= 1200;
            return largeScreen;
        }
    };
});
