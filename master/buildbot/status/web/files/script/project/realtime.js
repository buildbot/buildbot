define(['jquery', 'project/realtimePages', 'helpers'], function ($, realtimePages, helpers) {
         "use strict";
    var realtime;
    
    realtime = {
        init: function () {
	        // creating a new websocket
	                
	                
	         window.sock = null;

	         var wsuri;

	        var realTimeServer =  $('body').attr('data-realTimeServer');
	         
         	wsuri = realTimeServer;

         	console.log($('body').attr('data-realTimeServer'));

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
		             console.log(helpers.getJsonUrl())
		             broadcast(helpers.getJsonUrl());
	         	    log("Connected to " + wsuri);
	             }

	             sock.onclose = function(e) {
	                 log("Connection closed (wasClean = " + e.wasClean + ", code = " + e.code + ", reason = '" + e.reason + "')");
	                 sock = null;
	                 console.log('closed')
	             }

	             sock.onmessage = function(e) {

	         		log(e.data);
	             }
	         }
	        
	         function broadcast(msg) {
	             if (sock) {
	             	sock.send(msg);
	            	 //log("Sent: " + msg);
	             }		         
	         };

	        // For the build detailpage
			
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