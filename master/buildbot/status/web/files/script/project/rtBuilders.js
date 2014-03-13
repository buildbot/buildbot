define(['jquery', 'project/realtimePages', 'helpers', 'libs/jquery.form'], function ($, realtimePages, helpers, form) {
         "use strict";
    var rtBuilders;
    
    rtBuilders = {
        init: function () {
            realtimePages.initRealtime(realtimePages.buildersPage);
        }
    };

    return rtBuilders;
});