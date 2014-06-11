/*global require, define, jQuery*/
require.config({
    paths: {
        'jquery': 'libs/jquery',
        'selectors': 'project/selectors',
        'select2': 'plugins/select2',
        'datatables-plugin': 'plugins/jquery-datatables',
        'dataTables': 'project/dataTables',
        'dotdotdot': 'plugins/jquery-dotdotdot',
        'screensize': 'project/screen-size',
        'helpers': 'project/helpers',
        'projectdropdown': 'project/project-drop-down',
        'popup': 'project/popup',
        'realtimePages': 'project/realtimePages',
        'realtimerouting': 'project/realtimeRouting',
        'rtbuilddetail': 'project/rtBuildDetail',
        'rtbuilders': 'project/rtBuilders',
        'rtbuilderdetail': 'project/rtBuilderDetail',
        'rtbuildslaves': 'project/rtBuildSlaves',
        'rtbuildslavedetail': 'project/rtBuildSlaveDetail',
        'rtbuildqueue': 'project/rtBuildqueue',
        'rtglobal': 'project/rtGlobal',
        'jqache': 'plugins/jqache-0-1-1-min',
        'overscroll': 'plugins/jquery-overscroll',
        'moment': 'plugins/moment-with-langs',
        'extend-moment': 'project/extendMoment',
        'mustache': "libs/mustache-wrap",
        'handlebars': "libs/handlebars",
        'livestamp': "plugins/livestamp",
        //'noise': "plugins/jquery.noisy",
        'timeElements': "project/timeElements",
        'iFrameResize': "libs/iframeResizer.min",
        'rtGenericTable': "project/rtGenericTable",
        'hbCells': 'templates/rtCells.handlebars',
        'userSettings': 'project/userSettings',
        'URIjs': 'libs/uri',
        'toastr': 'plugins/toastr'
    },
    shim: {
        'overscroll': {
            deps: ['jquery']
        }
    }
});

define(['jquery', 'helpers', 'dataTables', 'popup', 'screensize', 'projectdropdown', 'extend-moment',
        'text!templates/popups.mustache', 'mustache', 'timeElements', 'URIjs/URI', 'rtglobal', 'toastr', 'realtimerouting',
        'realtimePages', 'rtbuilders', 'overscroll'],
    function ($, helpers, dataTables, popup, screenSize, projectDropDown, extendMoment, popups, Mustache, timeElements, URI, rtGlobal, toastr) {

        'use strict';

        // reveal the page when all scripts are loaded
        $(document).ready(function () {
            $('body').show();

            // swipe or scroll in the codebases overview
            if ($('#builders_page').length || $('#builder_page').length) {
                require(['overscroll'],
                    function (overscroll) {

                        $("#overScrollJS").overscroll({
                            showThumbs: false,
                            direction: 'horizontal'
                        });
                    });
            }

            // tooltip for long txtstrings
            if ($('.ellipsis-js').length) {
                require(['dotdotdot'],
                    function () {
                        $(".ellipsis-js").dotdotdot();
                    });
            }

            // codebases combobox selector
            if ($('#commonBranch_select').length || $('.select-tools-js').length) {
                require(['selectors'],
                    function (selectors) {
                        selectors.init();
                    });
            }

            if (helpers.hasfinished() === false) {
                require(['realtimerouting'],
                    function (realtimeRouting) {
                        realtimeRouting.init();
                    });
            }

            if (helpers.isRealTimePage() === true) {
                var preloader = $(Mustache.render(popups, {'preloader': 'true'}));
                $('div.content').append(preloader);

            }

            if ($('#home_page').length > 0) {
                helpers.randomImage($('#image').find('img'));
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
            projectDropDown.init();

            // get all common scripts
            helpers.init();
            dataTables.init();
            extendMoment.init();
            timeElements.init();

            if ($("body").attr("id") === "usersettings_page") {
                require(["userSettings"], function (userSettings) {
                    userSettings.init();
                });
            }
        });
    });
