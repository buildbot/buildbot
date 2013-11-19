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
	        if ($('#buildDetail').length != 0) {
	        	var stepList = $('#stepList > li');
	        }
	        
	        function log(m) {
				if ($('#tb-root').length != 0) {
					// For the frontpage
					realtimePages.frontPage(m);
				}
				if ($('#buildDetail').length != 0) {
					// For the builddetailpage
					realtimePages.buildDetail(m, stepList);
				}
	        };
        }
    };
   return realtime
});