/*global require*/
(function () {
    "use strict";

    var allTestFiles = [],
        TEST_REGEXP = /(spec|test_)[\w\W]*\.js$/i;

    var pathToModule = function (path) {
        return path.replace(/^\/base\//, '').replace(/\.js$/, '');
    };

    Object.keys(window.__karma__.files).forEach(function (file) {
        if (TEST_REGEXP.test(file)) {
            // Normalize paths to RequireJS module names.
            allTestFiles.push(pathToModule(file));
        }
    });

    require.config({
        // Karma serves files under /base, which is the basePath from your config file
        baseUrl: '/base',

        // dynamically load all test files
        deps: allTestFiles,

        // we have to kickoff jasmine, as it is asynchronous
        callback: window.__karma__.start,

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
            'timeElements': "project/timeElements",
            'iFrameResize': "libs/iframeResizer.min",
            'rtGenericTable': "project/rtGenericTable",
            'hbCells': 'templates/rtCells.handlebars',
            'userSettings': 'project/userSettings',
            'URIjs': 'libs/uri',
            'toastr': 'plugins/toastr',
            'popup-mustache': 'templates/popups.mustache'
        },

        shim: {
            'underscore': {
                exports: '_'
            }
        }
    });

}());