define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var tbsorter = $('#tablesorterRt').dataTable();
    var rtBuildqueue = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions["queue"] = rtBuildqueue.processBuildQueue
            realtimePages.initRealtime(realtimeFunctions);
        }, processBuildQueue: function(data) {        	
        	tbsorter.fnClearTable();
        	try {
				tbsorter.fnAddData(data);
				

            }
            catch(err) {
            }        
        }
    };

    return rtBuildqueue;
});