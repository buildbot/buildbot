/*global define*/
define(["jquery", "helpers"], function ($, helpers) {

    "use strict";

    $(document).ready(function ($iFrame) {
        var iFrame = document.getElementById("logIFrame"),
            $scrollOpt = $("#scrollOpt"),
            hasPressed = false;

        $(document).keyup(function (event) {
            if (event.which === 83) {
                if (hasPressed === false) {
                    var checked = !$scrollOpt.prop("checked");
                    hasPressed = true;
                    $scrollOpt.prop("checked", checked);
                    if (checked) {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                    setTimeout(function () { hasPressed = false; }, 300);
                }
            }
        });

        setInterval(function () {
            helpers.setIFrameSize(iFrame);

            if ($scrollOpt.prop("checked")) {
                window.scrollTo(0, document.body.scrollHeight);
            }
        }, 1000);

        helpers.setIFrameSize(iFrame);
    });

});