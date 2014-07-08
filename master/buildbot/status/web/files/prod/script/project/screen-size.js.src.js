/*global define*/
define(['jquery', 'helpers'], function ($) {

    

    var viewportSizes = {
            EXTRA_SMALL: 480,
            SMALL: 768,
            MEDIUM: 992,
            LARGE: 1520
        };

    var publicFunc = {
        isExtraSmallScreen: function () {
            return publicFunc.getViewportMediaQuery(viewportSizes.EXTRA_SMALL).matches;
        },
        isSmallScreen: function () {
            return publicFunc.getViewportMediaQuery(viewportSizes.SMALL).matches;
        },
        isMediumScreen: function () {
            return publicFunc.getViewportMediaQuery(viewportSizes.MEDIUM).matches;
        },
        isLargeScreen: function () {
            return publicFunc.getViewportMediaQuery(viewportSizes.LARGE).matches;
        },
        getViewportMediaQuery: function (size) {
            return window.matchMedia("(min-width: {0}px".format(size));
        },
        viewportSizes: viewportSizes
    };

    return publicFunc;
});
