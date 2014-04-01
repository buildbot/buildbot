define(['jquery', 'realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
        var buildQueueTotal = $('#buildQueueTotal');
        var buildSlavesTotal = $('#buildSlavesTotal');
        var outerBar = $('#verticalProgressBar');        
        
        var rtGlobal = {
        init: function () {
            realtimePages.initRealtime(rtGlobal.processGlobal);
        }, 
        processGlobal: function(data) {        	

        	try {
			     helpers.verticalProgressBar(outerBar.children(), data);        
                 outerBar.attr('title',""+16+ " builds are running, "+43+" agents are idle ");
            }
            catch(err) {
            }        

        }
    };

    return rtGlobal;
});