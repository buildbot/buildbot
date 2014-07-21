/*global define*/
define(['jquery'], function ($) {

    "use strict";

    var viewportSizes = {
            EXTRA_SMALL: 480,
            SMALL: 768,
            MEDIUM: 992,
            LARGE: 1520
        };

    return {
        isExtraSmallScreen: function () {
            return this.getViewportMediaQuery(viewportSizes.EXTRA_SMALL).matches;
        },
        isSmallScreen: function () {
            return this.getViewportMediaQuery(viewportSizes.SMALL).matches;
        },
        isMediumScreen: function () {
            return this.getViewportMediaQuery(viewportSizes.MEDIUM).matches;
        },
        isLargeScreen: function () {
            return this.getViewportMediaQuery(viewportSizes.LARGE).matches;
        },
        getViewportMediaQuery: function (size) {
            return window.matchMedia("(min-width: {0}px".format(size));
        },
        viewportSizes: viewportSizes
    };
});
