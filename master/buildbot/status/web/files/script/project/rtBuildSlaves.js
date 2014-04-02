define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var rtBuildSlaves;
    var tbsorter = $('#tablesorterRt').dataTable();
    
    rtBuildSlaves = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions["slaves"] = rtBuildSlaves.processBuildSlaves
            realtimePages.initRealtime(realtimeFunctions);
        }, processBuildSlaves: function(data) {
        	tbsorter.fnClearTable();
        	try {
                //Buildbot doesn't easily give you an array so we are running through a dictionary here
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