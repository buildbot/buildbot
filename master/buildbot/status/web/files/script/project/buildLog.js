/*global define*/
define(["jquery", "helpers", "iFrameResize"], function ($) {

    "use strict";

    function maybeScroll(checked) {
        if (checked) {
            setTimeout(function () {
                window.scrollTo(0, document.body.scrollHeight);
            }, 300);
        }
    }

    $(document).ready(function () {
        
        var $iFrame = $("#logIFrame"),
            $scrollOpt = $("#scrollOpt"),
            hasPressed = false;
            
        //Start auto resizer
        $iFrame.iFrameResize({
            "autoResize": true,
            "sizeWidth": false,
            "resizedCallback": function () {
                maybeScroll($scrollOpt.prop("checked"));
            }
        });        

        $(document).keyup(function (event) {
            if (event.which === 83) {
                if (hasPressed === false) {
                    var checked = !$scrollOpt.prop("checked");
                    hasPressed = true;
                    $scrollOpt.prop("checked", checked);
                    maybeScroll(checked);
                    setTimeout(function () { hasPressed = false; }, 300);
                }
            }
        });
    });

});