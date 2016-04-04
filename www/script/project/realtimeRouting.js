/*global define*/
define(function (require) {
    "use strict";

    var helpers = require('helpers'),
        _callbacks = {};

    return {
        addPageInitHandler : function(key, callback) {
            if (!key || !callback) {
                return;
            }
           _callbacks[key] =  callback;
        },
        init: function () {
            /*jslint white: true */
            var page = helpers.getCurrentPage();
            switch (page) {
                case 'builddetail_page':
                    // For the builddetailpage
                    require(['rtBuildDetail'],
                        function (rtBuildDetail) {
                            rtBuildDetail.init();
                        });
                    break;

                case 'builders_page':
                    // For the builderspage
                    require(['rtBuilders'],
                        function (rtBuilders) {
                            rtBuilders.init();
                        });
                    break;

                case 'builderdetail_page':
                    // For the builddetailpage
                    require(['rtBuilderDetail'],
                        function (rtBuilderDetail) {
                            rtBuilderDetail.init();
                        });
                    break;

                case 'buildslaves_page':
                    // For the frontpage
                    require(['rtBuildSlaves'],
                        function (rtBuildSlaves) {
                            rtBuildSlaves.init();
                        });
                    break;
                case 'buildslavedetail_page':
                    // For the frontpage
                    require(['rtBuildSlaveDetail'],
                        function (rtBuildSlaveDetail) {
                            rtBuildSlaveDetail.init();
                        });
                    break;

                case 'buildqueue_page':
                    // For the frontpage
                    require(['rtBuildQueue'],
                        function (rtBuildQueue) {
                            rtBuildQueue.init();
                        });
                    break;
                case 'comparison':
                    // For the comparison page
                    require(['project/rtComparison'],
                        function (rtComparison) {
                            rtComparison.init();
                        });
                    break;
                default:
                    if(Object.keys(_callbacks).indexOf(page) > -1)
                    {
                        _callbacks[page]();
                        break;
                    }
                    // For pages without overriden realtime
                    require(['rtGlobal'],
                        function (rtGlobal) {
                            rtGlobal.init();
                        });
                    break;
            }
            /*jslint white: false */
        }
    };
});
