/*global define*/
define(['jquery', 'rtGlobal', 'helpers', 'timeElements'], function ($, rtGlobal, helpers, timeElements) {
    "use strict";
    var sock = null;
    var realTimeFunctions = {};
    var realtimeURLs = {};
    var realTimeLastUpdated = {};

    //Realtime commands
    var KRT_JSON_DATA = "krtJSONData";
    var KRT_URL_DROPPED = "krtURLDropped";
    var KRT_REGISTER_URL = "krtRegisterURL";

    //Timeouts
    var iURLDroppedTimeout = 30000;
    var iServerDisconnectTimeout = 30000;
    var KRT_RELOAD_CD = 500; //Amount of time before we can reload data

    var realtimePages = {
        createWebSocket: function (wsURI, json) {
            if (sock === null) {

                if (window.WebSocket !== undefined) {
                    sock = new window.WebSocket(wsURI);
                } else if (window.MozWebSocket !== undefined) {
                    sock = new window.MozWebSocket(wsURI);
                } else {
                    console.log("Realtime is not supported on this browser.");
                    return;
                }

                // if the socket connection is success
                if (sock) {
                    sock.onopen = function () {
                        $("#preloader").preloader("hidePreloader");
                        // get the json url to parse
                        $.each(realtimeURLs, function (name, url) {
                            var data = {
                                url: url
                            };

                            if (json !== undefined) {
                                data.waitForPush = json[name].waitForPush;
                                data.pushFilters = json[name].pushFilters;
                            }
                            realtimePages.sendCommand(KRT_REGISTER_URL, data);
                        });
                    };

                    // when the connection closes
                    sock.onclose = function () {
                        sock = null;
                        console.log("We lost our connection, retrying in {0} seconds...".format(iServerDisconnectTimeout / 1000));
                        setTimeout(function () {
                            realtimePages.createWebSocket(wsURI, json);
                        }, iServerDisconnectTimeout);
                    };

                    // when the client recieves a message
                    sock.onmessage = function (e) {
                        var data = e.data;
                        if (typeof data === "string") {
                            data = JSON.parse(data);
                        }
                        realtimePages.parseRealtimeCommand(data);
                    };
                }
            }

            return sock;
        },
        initRealtime: function (rtFunctions) {
            realTimeFunctions = rtFunctions; //Needs to be an array linked to URLs

            //Attempt to load our table immediately
            var json = realtimePages.getInstantJSON();
            if (json !== undefined) {
                console.log("Loaded from instant JSON");
                realtimePages.updateRealTimeData(json, true);
            }

            // Creating a new websocket
            var wsURI = $('body').attr('data-realTimeServer');
            if (wsURI !== undefined && wsURI !== "") {
                console.log(wsURI);
                realtimePages.createWebSocket(wsURI, json);
                return sock;
            }

            console.log("Realtime server not found, disabling realtime.");

            return undefined;
        },
        sendCommand: function (cmd, data) {
            if (sock) {
                var msg = JSON.stringify({cmd: cmd, data: data});
                sock.send(msg);
            }
        },
        parseRealtimeCommand: function (data) {
            if (data.cmd === KRT_JSON_DATA) {
                realtimePages.updateRealTimeData(data.data, false);
            }
            if (data.cmd === KRT_URL_DROPPED) {
                console.log("URL Dropped by server will retry in {0} seconds... ({1})".format((iURLDroppedTimeout / 1000), data.data));
                setTimeout(function () {
                    realtimePages.sendCommand(KRT_REGISTER_URL, data.data);
                }, iURLDroppedTimeout);
            }
        },
        updateRealTimeData: function (json, instantJSON) {
            if (instantJSON === true) {
                $.each(json, function (name, jObj) {
                    var data = jObj.data;
                    if (typeof data === "string") {
                        data = JSON.parse(data);
                        realtimeURLs[name] = jObj.url;
                    }
                    realtimePages.updateSingleRealTimeData(name, data);
                });
            } else {
                var name = realtimePages.getRealtimeNameFromURL(json.url);
                realtimePages.updateSingleRealTimeData(name, json.data);
            }
        },
        getRealtimeNameFromURL: function (url) {
            var name;
            $.each(realtimeURLs, function (n, u) {
                if (u === url) {
                    name = n;
                    return false;
                }
                return true;
            });

            return name;
        },
        updateSingleRealTimeData: function (name, data, force) {
            var shouldUpdate = true;
            var now = new Date();
            if ((force === undefined || !force) && realTimeLastUpdated.hasOwnProperty(name)) {
                if ((now - realTimeLastUpdated[name]) < KRT_RELOAD_CD) {
                    shouldUpdate = false;
                }
            }
            if (shouldUpdate && realTimeFunctions.hasOwnProperty(name)) {
                realTimeFunctions[name](data);
                realTimeLastUpdated[name] = now;
                console.log("Reloading data for {0}...".format(name));
            }
        },
        getInstantJSON: function () {
            var script = $('#instant-json');
            // remove prelaoder
            $("#preloader").preloader("hidePreloader");
            $('.initjson').show();
            if (script.length && window.instantJSON !== undefined) {
                script.remove();
                return window.instantJSON;
            }
            return undefined;
        },
        defaultRealtimeFunctions: function () {
            return {
                "global": rtGlobal.processGlobalInfo
            };
        },
        setReloadCooldown: function (miliseconds) {
            KRT_RELOAD_CD = miliseconds;
        }
    };

    return realtimePages;
});
