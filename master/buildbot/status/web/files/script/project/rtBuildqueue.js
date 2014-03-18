define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var tbsorter = $('#tablesorterRt').dataTable();
    var rtBuildqueue = {
        init: function () {
            realtimePages.initRealtime(rtBuildqueue.processBuildQueue);
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