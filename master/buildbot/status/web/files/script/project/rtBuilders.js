define(['jquery', 'project/realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var rtBuilders;
    
    rtBuilders = {
        init: function () {
            realtimePages.initRealtime(realtimePages.buildersPage);
        }
    };

    return rtBuilders;
});