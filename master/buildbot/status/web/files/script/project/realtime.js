define(['jquery', 'project/realtimePages'], function ($, realtimePages) {
	 "use strict";
    var realtime;
    
    realtime = {
        init: function () {
			// creating a new websocket

				(function( $ ) {
					 var sock = null;
			         var ellog = null;

			            var wsuri;
			            ellog = document.getElementById('log');

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
				              
				               	var currentUrl = document.URL;
				               	
							    var parser = document.createElement('a');
							    parser.href = currentUrl;
							     
							    parser.protocol; // => "http:"
							    parser.hostname; // => "example.com"
							    parser.port;     // => "3000"
							    parser.pathname; // => "/pathname/"
							    parser.search;   // => "?search=test"
							    parser.hash;     // => "#hash"
							    parser.host;     // => "example.com:3000"

							    var buildersPath = parser.pathname.match(/\/builders\/([^\/]+)/);
							    var buildPath = parser.pathname.match(/\/builds\/([^\/]+)/);

				               	broadcast('http://localhost:8001/json/builders/'+ buildersPath[1] +'/builds?select='+ buildPath[1] +'/');
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
			           
			            if (sock) {
			               sock.send(msg);
			               //log("Sent: " + msg);
			            } else {
			               //log("Not connected.");
			            }
			             
			         };
			        
			         function log(m) {
			         	if ($('#tb-root').length != 0) {
			         		realtimePages.frontPage(m);
			         	}
			            
			            realtimePages.buildDetail(m);
			         };
		         	
			     })( jQuery );
			 
		}
	};
	return realtime
});