/*global require, define*/
(function () {
    "use strict";

    var allTestFiles = [],
        TEST_REGEXP = /(spec|test_)[\w\W]*\.js$/i;

    var pathToModule = function (path) {
        return path.replace(/^\/base\/script\//, '').replace(/\.js$/, '');
    };

    Object.keys(window.__karma__.files).forEach(function (file) {
        if (TEST_REGEXP.test(file)) {
            // Normalize paths to RequireJS module names.
            allTestFiles.push(pathToModule(file));
        }
    });

    require.config({
        // Karma serves files under /base, which is the basePath from your config file
        baseUrl: '/base/script',

        // dynamically load all test files
        deps: allTestFiles,

        // we have to kickoff jasmine, as it is asynchronous
        callback: window.__karma__.start,

        paths: {
            'handlebars-internal': "libs/handlebars",
            'jquery': 'libs/jquery',
            'jquery-ui': 'libs/jquery-ui',
            'ui.dropdown': 'project/ui/dropdown',
            'ui.popup': 'project/ui/popup',
            'ui.preloader': 'project/ui/preloader',
            'selectors': 'project/selectors',
            'select2': 'plugins/select2',
            'datatables': 'libs/jquery-datatables',
            'datatables-extend': 'project/datatables-extend',
            'dotdotdot': 'plugins/jquery-dotdotdot',
            'screensize': 'project/screen-size',
            'helpers': 'project/helpers',
            'realtimePages': 'project/realtimePages',
            'realtimerouting': 'project/realtimeRouting',
            'rtBuildDetail': 'project/rtBuildDetail',
            'rtBuilders': 'project/rtBuilders',
            'rtBuilderDetail': 'project/rtBuilderDetail',
            'rtBuildSlaves': 'project/rtBuildSlaves',
            'rtBuildSlaveDetail': 'project/rtBuildSlaveDetail',
            'rtBuildQueue': 'project/rtBuildQueue',
            'rtGlobal': 'project/rtGlobal',
            'jqache': 'plugins/jqache-0-1-1-min',
            'overscroll': 'plugins/jquery-overscroll',
            'moment': 'plugins/moment-with-langs',
            'extend-moment': 'project/extendMoment',
            'livestamp': "plugins/livestamp",
            'timeElements': "project/timeElements",
            'iFrameResize': "libs/iframeResizer.min",
            'rtGenericTable': "project/rtGenericTable",
            'userSettings': 'project/userSettings',
            'URIjs': 'libs/uri',
            'toastr': 'plugins/toastr',
            "precompiled.handlebars": "../generated/precompiled.handlebars"
        },

        shim: {
            'underscore': {
                exports: '_'
            },
            'ui.preloader': {
                deps: ['jquery-ui']
            },
            "precompiled.handlebars": {
                deps: ['handlebars']
            }
        }
    });

    define("handlebars", ["handlebars-internal"], function () {
        "use strict";
        return Handlebars;
    });

}());