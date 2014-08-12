/*global define*/
define(['jquery', 'iFrameResizeContent'], function ($) {
    "use strict";

    $("document").ready(function () {
        setTimeout(function () {
            var removePadding = function removePadding() {
                if (window.parentIFrame !== undefined) {
                    $("pre.code").css("padding-left", 0);
                    return true;
                }
                return false;
            };


            if (!removePadding()) {
                var i = setInterval(function () {
                    if (removePadding()) {
                        clearInterval(i);
                    }
                }, 1000);
            }
        }, 300);
    });
});
