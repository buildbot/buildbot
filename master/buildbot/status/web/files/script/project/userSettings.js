/*global define*/
define(['jquery', 'libs/jquery.form'], function ($, form) {
    "use strict";

    var COLOR_BLIND_CSS = "color-blind-mode";

    var privFunc = {
        initColorBlindBtn: function () {
            var $colorBtn = $("#colorBlindMode"),
                $colorField = $("#colorBlind_setting"),
                $body = $("body"),
                $colorBlindOpt = $colorBtn.parent().find("#colorBlindOpt");

            $colorBtn.click(function () {
                var colorBlindActivated = $body.hasClass(COLOR_BLIND_CSS);
                if (colorBlindActivated === true) {
                    $body.removeClass(COLOR_BLIND_CSS);
                } else {
                    $body.addClass(COLOR_BLIND_CSS);
                }

                var val = !colorBlindActivated ? "1" : "0";
                $colorField.val(val);
            });
        }
    };

    return {
        init : function () {
            privFunc.initColorBlindBtn();
        }
    };
});