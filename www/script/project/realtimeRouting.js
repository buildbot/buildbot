/*global define*/
define(function (require) {
    "use strict";

    var helpers = require('helpers');

    return {
        init: function () {
            /*jslint white: true */
            switch (helpers.getCurrentPage()) {
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
