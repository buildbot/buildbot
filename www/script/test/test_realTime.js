/*global define, describe, it, expect, beforeEach, afterEach, spyOn*/
define(["jquery", "realtimePages"], function ($, rt) {
    "use strict";

    var $body = $("body");

    describe("An instant JSON", function () {

        beforeEach(function (done) {
            $.getScript("/base/test/instantJSON.js", function () {
                $body.append($("<script/>").attr("id", "instant-json"));
                done();
            });
        });

        it("is loaded correctly", function () {
            var json = rt.getInstantJSON();
            expect(json.global.url).toEqual("http://10.45.6.89:8001/json/globalstatus");
        });

        it("is removed from the DOM", function () {
            rt.getInstantJSON();
            expect($("#instant-json").length).toEqual(0);
        });
    });

    describe("A websocket", function () {
        var cachedWebsocket = window.WebSocket,
            cachedMozWebSocket = window.MozWebSocket,
            sock,
            realtimeFunctions = {
                test: function () {
                    return "Called";
                }
            },
            realtimeData = {data: {"cmd": "krtJSONData", "data": {"url": "http://test.com", "data": {"test": "test"}}}},
            fakeWebSocketObject = {
                send: function () {
                    return undefined;
                }
            };

        beforeEach(function (done) {
            var fakeWebSocket = function (isMozWebSocket) {
                return function () {
                    fakeWebSocketObject.onopen = undefined;
                    fakeWebSocketObject.isMozWebSocket = isMozWebSocket;

                    setTimeout(function () {
                        if (fakeWebSocketObject.onopen !== undefined) {
                            fakeWebSocketObject.onopen();
                        }
                    }, 15);

                    return fakeWebSocketObject;
                };
            };

            window.WebSocket = fakeWebSocket(false);
            window.MozWebSocket = fakeWebSocket(true);

            $.getScript("/base/test/instantJSON.js", function () {
                $body.append($("<script/>").attr("id", "instant-json"));
                done();
            });

            $body.attr("data-realTimeServer", "ws://test.com:1234");
            rt.setReloadCooldown(0);
        });

        afterEach(function () {
            if (sock !== undefined && sock.onclose !== undefined) {
                sock.onclose();
            }
            window.WebSocket = cachedWebsocket;
            window.MozWebSocket = cachedMozWebSocket;

            $body.removeAttr("data-realTimeServer");
            $body.find("#instant-json").remove();
        });

        it("is not created when there is no instantJSON found", function () {
            $body.removeAttr("data-realTimeServer");
            $body.find("#instant-json").remove();

            expect(rt.initRealtime(realtimeFunctions)).toBeUndefined();
        });

        it("is created", function (done) {
            sock = rt.initRealtime(realtimeFunctions);
            expect(sock.isMozWebSocket).toBeFalsy();
            spyOn(sock, 'onopen');

            setTimeout(function () {
                expect(sock.onopen).toHaveBeenCalled();
                done();
            }, 50);
        });

        it("of type MozWebSocket is created when WebSocket doesn't exist", function (done) {
            window.WebSocket = undefined;

            sock = rt.initRealtime(realtimeFunctions);
            expect(sock.isMozWebSocket).toBeTruthy();
            spyOn(sock, 'onopen');

            setTimeout(function () {
                expect(sock.onopen).toHaveBeenCalled();
                done();
            }, 50);
        });

        it("is not created when the browser is not supported", function () {
            window.WebSocket = undefined;
            window.MozWebSocket = undefined;
            expect(rt.initRealtime(realtimeFunctions)).toBeNull();
        });

        it("parses data and runs a command", function () {
            spyOn(realtimeFunctions, 'test');

            sock = rt.initRealtime(realtimeFunctions);
            expect(sock).not.toBeUndefined();
            sock.onmessage(realtimeData);

            expect(realtimeFunctions.test).toHaveBeenCalled();
            expect(realtimeFunctions.test).toHaveBeenCalledWith(realtimeData.data.data.data);
        });

        it("parses data and runs a command when forced", function () {
            rt.setReloadCooldown(5000);
            spyOn(realtimeFunctions, 'test');

            sock = rt.initRealtime(realtimeFunctions);
            expect(sock).not.toBeUndefined();
            rt.updateSingleRealTimeData("test", realtimeData.data.data.data, true);

            expect(realtimeFunctions.test).toHaveBeenCalled();
            expect(realtimeFunctions.test).toHaveBeenCalledWith(realtimeData.data.data.data);
        });

        it("doesn't run a command when on cooldown", function () {
            rt.setReloadCooldown(5000);
            spyOn(realtimeFunctions, 'test');

            sock = rt.initRealtime(realtimeFunctions);
            expect(sock).not.toBeUndefined();
            rt.updateSingleRealTimeData("test", realtimeData.data.data.data, true);

            expect(realtimeFunctions.test).toHaveBeenCalled();
            expect(realtimeFunctions.test).toHaveBeenCalledWith(realtimeData.data.data.data);

            rt.updateSingleRealTimeData("test", realtimeData.data.data.data);

            expect(realtimeFunctions.test.calls.count()).toEqual(1);
        });

        it("sends data to the realtime server", function () {
            sock = rt.initRealtime(realtimeFunctions);
            spyOn(sock, 'send');
            var testData = {test: "test123"};
            rt.sendCommand("test", testData);

            expect(sock.send).toHaveBeenCalled();
            expect(sock.send).toHaveBeenCalledWith(JSON.stringify({cmd: "test", data: testData}));
        });
    });
});
