/*global require, define, jQuery, Handlebars*/
require.config({
    paths: {
        "jquery-internal": "libs/jquery",
        "jquery-ui": "libs/jquery-ui",
        "handlebars-internal": "libs/handlebars",
        "ui.dropdown": "project/ui/dropdown",
        "ui.popup": "project/ui/popup",
        "ui.preloader": "project/ui/preloader",
        "selectors": "project/selectors",
        "select2": "plugins/select2",
        "datatables": "libs/jquery-datatables",
        "datatables-extend": "project/datatables-extend",
        "dotdotdot": "plugins/jquery-dotdotdot",
        "screensize": "project/screen-size",
        "helpers": "project/helpers",
        "realtimePages": "project/realtimePages",
        "realtimerouting": "project/realtimeRouting",
        "rtBuildDetail": "project/rtBuildDetail",
        "rtBuilders": "project/rtBuilders",
        "rtBuilderDetail": "project/rtBuilderDetail",
        "rtBuildSlaves": "project/rtBuildSlaves",
        "rtBuildSlaveDetail": "project/rtBuildSlaveDetail",
        "rtBuildQueue": "project/rtBuildQueue",
        "rtGlobal": "project/rtGlobal",
        "jqache": "plugins/jqache-0-1-1-min",
        "overscroll": "plugins/jquery-overscroll",
        "moment": "plugins/moment-with-langs",
        "extend-moment": "project/extendMoment",
        "livestamp": "plugins/livestamp",
        "timeElements": "project/timeElements",
        "iFrameResize": "libs/iframeResizer",
        "iFrameResizeContent": "libs/iframeResizer.contentWindow",
        "rtGenericTable": "project/rtGenericTable",
        "userSettings": "project/userSettings",
        "URIjs": "libs/uri",
        "toastr": "plugins/toastr",
        "testResults": "project/testresults-common",
        "buildLog": "project/buildLog",
        "buildLogiFrame": "project/buildLog-iFrame",
        "login": "project/login",
        "precompiled.handlebars": "../generated/precompiled.handlebars"
    },
    shim: {
        "overscroll": {
            deps: ["jquery"]
        },
        "ui.preloader": {
            deps: ["jquery-ui"]
        }
    }
});

define("jquery", ["jquery-internal"], function () {
    "use strict";
    return jQuery;
});

define("handlebars", ["handlebars-internal"], function () {
    "use strict";
    return Handlebars;
});

define(function (require) {

    "use strict";

    var $ = require('jquery'),
        helpers = require('helpers'),
        dataTables = require('datatables-extend'),
        popup = require('ui.popup'),
        dropdown = require('ui.dropdown'),
        extendMoment = require('extend-moment'),
        timeElements = require('timeElements'),
        toastr = require('toastr');

    require('ui.preloader');
    require('overscroll');


    // reveal the page when all scripts are loaded
    $(document).ready(function () {
        var $body = $("body");
        $body.show();

        var $preloader = $("<div/>").preloader({
            "autoShow": false
        }).attr("id", "preloader");
        $body.append($preloader);

        if ($body.attr("id") === "usersettings_page") {
            require(["userSettings"], function (userSettings) {
                userSettings.init();
            });
        }

        // swipe or scroll in the codebases overview
        $("#overScrollJS").overscroll({
            showThumbs: false,
            direction: "horizontal"
        });

        // tooltip for long txtstrings
        if ($(".ellipsis-js").length) {
            require(["dotdotdot"],
                function () {
                    $(".ellipsis-js").dotdotdot();
                });
        }

        // codebases combobox selector
        if ($("#commonBranch_select").length || $(".select-tools-js").length) {
            require(["selectors"],
                function (selectors) {
                    selectors.init();
                });
        }

        if (helpers.hasfinished() === false) {
            require(["realtimerouting"],
                function (realtimeRouting) {
                    realtimeRouting.init();
                });
        }

        if (helpers.isRealTimePage() === true) {
            $preloader.preloader("showPreloader");
        }

        if ($("#home_page").length > 0) {
            helpers.randomImage($("#image").find("img"));
        }

        // setup toastr
        toastr.options = {
            closeButton: true,
            timeOut: 5000,
            extendedTimeOut: 0,
            hideDuration: 300
        };

        // get scripts for general popups
        popup.init();
        // get scripts for the projects dropdown
        dropdown.init();

        // get all common scripts
        helpers.init();
        dataTables.init();
        extendMoment.init();
        timeElements.init();
    });
});
