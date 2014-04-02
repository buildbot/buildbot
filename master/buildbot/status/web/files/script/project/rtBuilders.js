define(['jquery', 'realtimePages', 'helpers', 'libs/jquery.form'], function ($, realtimePages, helpers, form) {
         "use strict";
    var rtBuilders;
    var tbsorter = $('#tablesorterRt').dataTable();
    rtBuilders = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions['builders'] = rtBuilders.realtimeFunctionsProcessBuilders
            realtimePages.initRealtime(realtimeFunctions);
        }, 
        realtimeFunctionsProcessBuilders: function(data) {
        	tbsorter.fnClearTable();        
        	
        	try {
          		tbsorter.fnAddData(data.builders);
	        }
	           catch(err) {
	        	//console.log(err);
	        }
        }
    };

    return rtBuilders;
});