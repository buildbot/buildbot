define(['jquery', 'helpers'], function ($, helpers) {
         "use strict";
    var realtimeRouting;
    
    realtimeRouting = {
        init: function () {        	

        	// For common elementupdates 
        	require(['rtglobal'],
				function(rtGlobal) {
				rtGlobal.init();
			});

        	switch(helpers.getCurrentPage()) { 
				case 'builddetail':        	
					// For the builddetailpage
					require(['rtbuilddetail'],
			        function(rtBuildDetail) {
			        	rtBuildDetail.init();
			        });
			      	break;
				
				case 'builders':							
					// For the builderspage
					require(['rtbuilders'],
			        function(rtBuilders) {
			        	rtBuilders.init();
			        });
			       break;

			    case 'buildslaves':							
					// For the frontpage
					require(['rtbuildslaves'],
			        function(rtBuildSlaves) {
			        	rtBuildSlaves.init();
			        });
			       break;
				
				case 'buildqueue':
					// For the frontpage
					require(['rtbuildqueue'],
			        function(rtBuildqueue) {
			        	rtBuildqueue.init();
			        });
			       break;

			}

		
		}
	};
   return realtimeRouting
});
