define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";

    var rtBuildqueue = {
        init: function () {
            realtimePages.initRealtime(realtimePages.rtBuildqueue);
        }
    };

    return rtBuildqueue;
});