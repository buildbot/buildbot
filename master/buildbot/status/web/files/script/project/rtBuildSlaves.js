define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var rtBuildSlaves;
    var tbsorter = $('#tablesorterRt').dataTable();
    
    rtBuildSlaves = {
        init: function () {
            realtimePages.initRealtime(rtBuildSlaves.processBuildSlaves);
        }, processBuildSlaves: function(data) {        	
        	tbsorter.fnClearTable();        	
        	try {
          		$.each(data, function (key, value) {
          			var arObjData = [value];
					tbsorter.fnAddData(arObjData);
          		});
            }
            catch(err) {
            }
        }
    };
    return rtBuildSlaves;
});