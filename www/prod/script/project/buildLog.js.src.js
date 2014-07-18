/*global define, require*/
define(["main"], function () {
    

    require(["jquery", "helpers", "iFrameResize"], function ($) {

        function maybeScroll(checked) {
            if (checked) {
                setTimeout(function () {
                    window.scrollTo(0, document.body.scrollHeight);
                }, 300);
            }
        }

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

        //Show body
        $("body").show();

        $scrollOpt.click(function () {
            window.scrollTo(0, document.body.scrollHeight);
        });

        $(document).keyup(function (event) {
            if (event.which === 83) {
                if (hasPressed === false) {
                    var checked = !$scrollOpt.prop("checked");
                    hasPressed = true;
                    $scrollOpt.prop("checked", checked);
                    maybeScroll(checked);
                    setTimeout(function () {
                        hasPressed = false;
                    }, 300);
                }
            }
        });
    });
});