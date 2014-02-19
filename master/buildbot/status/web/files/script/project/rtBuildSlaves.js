define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var rtBuildSlaves;
    
    rtBuildSlaves = {
        init: function () {
            realtimePages.initRealtime(realtimePages.rtBuildSlaves);
        }
    };
    return rtBuildSlaves;
});