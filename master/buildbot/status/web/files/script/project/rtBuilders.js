define(['jquery', 'project/realtimePages', 'helpers', 'libs/jquery.form'], function ($, realtimePages, helpers, form) {
         "use strict";
    var rtBuilders;
    var tbsorter = $('#tablesorterRt').dataTable();
    rtBuilders = {
        init: function () {
            realtimePages.initRealtime(rtBuilders.processBuilders);
        }, 
        processBuilders: function(data) {        	
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