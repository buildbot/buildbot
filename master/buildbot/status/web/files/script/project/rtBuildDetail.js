define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var rtBuildDetail;
    
    rtBuildDetail = {
        init: function () {
            realtimePages.initRealtime(realtimePages.rtBuildDetail)
        }
    };

    return rtBuildDetail;
});