define(['jquery','helpers'], function ($,helpers) {
	 "use strict";
    var realtimePages;    
    
    var sock = null;
    var realTimeFunc = null;

    //Realtime commands
    var KRT_JSON_DATA = "krtJSONData";
    var KRT_URL_DROPPED = "krtURLDropped";
    var KRT_REGISTER_URL = "krtRegisterURL";

    realtimePages = {
        createWebSocket: function(wsURI) {
            if (sock == null) {

                if ("WebSocket" in window) {
                    sock = new WebSocket(wsURI);
                } else if ("MozWebSocket" in window) {
                    sock = new MozWebSocket(wsURI);
                } else {
                    log("Browser does not support WebSocket!");
                    window.location = "http://autobahn.ws/unsupportedbrowser";
                }

                // if the socket connection is success
                if (sock) {
                     sock.onopen = function () {
                         $('#bowlG').remove();
                         // get the json url to parse
                         realtimePages.sendCommand(KRT_REGISTER_URL, helpers.getJsonUrl());
                     };

                     // when the connection closes
                     sock.onclose = function(e) {
                         sock = null;
                         console.log("We lost our connection, retrying in 5 seconds...");
                         setTimeout(function() {realtimePages.createWebSocket(wsURI)}, 5000);
                     };

                     // when the client recieves a message
                     sock.onmessage = function(e) {
                         var data = e.data;
                         if (typeof data === "string") {
                            data = JSON.parse(data);
                         }
                         realtimePages.parseRealtimeCommand(data);
                     }
                }
            }

            return sock;
        },
        initRealtime: function (rtFunc) {
            realTimeFunc = rtFunc;

            //Attempt to load our table immediately
            var json = realtimePages.getInstantJSON();
            if (json !== undefined)
            {
                console.log("Loaded from instant JSON");
                realtimePages.updateRealTimeData(json);
            }

        	// Creating a new websocket
         	var wsURI = $('body').attr('data-realTimeServer');
            if (wsURI !== undefined && wsURI != "") {
                console.log(wsURI);
                realtimePages.createWebSocket(wsURI);
            }
            else {
                console.log("Realtime server not found, disabling realtime.")
            }
        },
        sendCommand: function(cmd, data) {
            if (sock) {
                var msg = JSON.stringify({"cmd": cmd, "data": data});
                sock.send(msg);
            }
        },
        parseRealtimeCommand: function(data) {
            if (data["cmd"] === KRT_JSON_DATA) {
                realtimePages.updateRealTimeData(data["data"]["data"]);
            }
            if (data["cmd"] === KRT_URL_DROPPED) {
                console.log("URL Dropped by server will retry in 5 seconds...");
                setTimeout(function() {
                    realtimePages.sendCommand(KRT_REGISTER_URL, helpers.getJsonUrl());
                }, 5000);
            }
        },
        updateRealTimeData: function(data) {
            realTimeFunc(data);
            console.log("Reloading data...");
        },
        getInstantJSON: function() {
            var script = $('#instant-json');
            if (script.length) {
                script.remove();
                return instantJSON;
            }
            return undefined;
        }
    };

    return realtimePages
});
