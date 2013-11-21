define(['jquery', 'project/realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var realtime;
    
    realtime = {
        init: function () {
	        // creating a new websocket
	                
	                
	         window.sock = null;
	        

	         var wsuri;
	        

	         if (window.location.protocol === "file:") {
	        	 wsuri = "ws://localhost:9000";
	         } else {
	         	wsuri = "ws://" + window.location.hostname + ":9000";
	         }

	         if ("WebSocket" in window) {
	         	sock = new WebSocket(wsuri);
	         } else if ("MozWebSocket" in window) {
	         	sock = new MozWebSocket(wsuri);
	         } else {
	             log("Browser does not support WebSocket!");
	             window.location = "http://autobahn.ws/unsupportedbrowser";
	         }

	         if (sock) {
	             sock.onopen = function() {
		             // get the json url to parse
		             broadcast(helpers.getJsonUrl());
	         	    log("Connected to " + wsuri);
	             }

	             sock.onclose = function(e) {
	                 log("Connection closed (wasClean = " + e.wasClean + ", code = " + e.code + ", reason = '" + e.reason + "')");
	                 sock = null;
	             }

	             sock.onmessage = function(e) {
	         		log(e.data);
	             }
	         }
	        
	         function broadcast(msg) {
	             console.log(msg)
	             if (sock) {
	             	sock.send(msg);
	            	 //log("Sent: " + msg);
	             } else {
	             	//log("Not connected.");
	             }
	        
	         };

	        // For the build detailpage

	        /*
	        function cachedHtml(returnHtml) {

	        	if (returnHtml === '#builddetail_page') {	        	
		        	var stepList = $('#stepList > li');
			        return stepList
		        } else if (returnHtml === '#builders_page') {
		        	var moreInfo = $('<a class="more-info popup-btn-js mod-1" data-rt_update="pending" href="#" data-in=""> Pending jobs </a>');
		        	return moreInfo;
		        }

	        };
	        */
			
	        if (helpers.getCurrentPage() === '#builddetail_page') {
	        	var stepList = $('#stepList > li');
	        }
	       // console.log(cachedHtml())
	        if (helpers.getCurrentPage() === '#builders_page') {	        	
	        	var tableRowList = $('.tablesorter-js tbody > tr');

	        }

	        function log(m) {
				if ($('#tb-root').length != 0) {
					// For the frontpage
					realtimePages.frontPage(m);
				}
				if (helpers.getCurrentPage() === '#builddetail_page') {
					// For the builddetailpage
					realtimePages.buildDetail(m, stepList);
				}
				if (helpers.getCurrentPage() === '#builders_page') {
					realtimePages.buildersPage(m);	
				}

	        };
        }
    };
   return realtime
});