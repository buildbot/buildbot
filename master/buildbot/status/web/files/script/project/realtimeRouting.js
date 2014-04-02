define(['jquery', 'helpers', 'realtimePages'], function ($, helpers, realtimePages) {
    "use strict";
    var realtimeRouting;

    realtimeRouting = {
        init: function () {        	

        	switch(helpers.getCurrentPage()) { 
				case 'builddetail_page':        	
					// For the builddetailpage
					require(['rtbuilddetail'],
			        function(rtBuildDetail) {
			        	rtBuildDetail.init();
			        });
			      	break;
				
				case 'builders_page':							
					// For the builderspage
					require(['rtbuilders'],
			        function(rtBuilders) {
			        	rtBuilders.init();
			        });
			       break;

                case 'buildslaves_page':
                    // For the frontpage
                    require(['rtbuildslaves'],
                        function (rtBuildSlaves) {
                            rtBuildSlaves.init();
                        });
                    break;

                case 'buildqueue_page':
                    // For the frontpage
                    require(['rtbuildqueue'],
                        function (rtBuildqueue) {
                            rtBuildqueue.init();
                        });
                    break;
            	default:
                    // For pages without overriden realtime
                    require(['rtglobal'],
                        function (rtGlobal) {
                    	rtGlobal.init();
                    });
                    break;
			}

		
		}
	};
   return realtimeRouting
});
