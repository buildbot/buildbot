// This file is part of Buildbot.  Buildbot is free software: you can
// redistribute it and/or modify it under the terms of the GNU General Public
// License as published by the Free Software Foundation, version 2.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc., 51
// Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
// Copyright Buildbot Team Members

/* pub/sub api to the buildbot websocket

   We are automatically subscribing/unsubscribing to the associated event on the websocket side.

   dojo standard "on" api should used, e.g:
   r = websocket.on("builders/12/builds/234", function(event) {
   // make something on build event
   });
   // after a while
   r.remove();

*/
define(
    [
        "dojo/_base/declare",
        "dojo/on",
        "dojo/json",
        "dojo/Evented",
        "dojo/aspect"
    ],
    function(declare, on, JSON, Evented, aspect) {
        return declare([Evented], {
            constructor: function(){
                this.listeners = {};
                this.reconnect_timeout = 100;
                this.reconnect();
                declare.safeMixin(this,arguments);
            },
            reconnect:function() {
                var ws_url = dojo.config.bb.wsUrl;
                var self = this;
                if (WebSocket) {
                    /* we dont have a longpoll server side implementation,
                       so no need to use dojox.socket */
                    self.socket = new WebSocket(ws_url);
                    on(self.socket,"open", function(event){
                        self.reconnect_timeout = 100;
                    });
                    on(self.socket,"message", function(event){
                        data = JSON.parse(event.data);
                        self.emit(data.path, data);
                    });
                    on(self.socket,"error", function(){
                        console.log("socket error!",self.socket);
                        /* we will close soon and reconnect */
                    });
                    on(self.socket,"close", function(){
                        setTimeout(function() {
                            self.reconnect_timeout*=2;
                            self.reconnect();
                        },
                                   self.reconnect_timeout);
                    });
                } else {
                    self.socket = undefined;
                }
            },
            send: function(msg) {
                var self = this;
                function send() {
                    self.socket.send(JSON.stringify(msg));
                }
                if (self.socket) {
                    if (self.socket.readyState === 1) {
                        send();
                    } else {
                        on(self.socket,"open", function(event){
                            send();
                        });
                    }
                }
            },
            on: function(path, listener) {
                var self = this;
                if (self.socket) {
                    var type = path.join('/');

                    var r = this.inherited(arguments);
                    if (!self.listeners.hasOwnProperty(type)) {
                        self.listeners[type] = 0;
                    }
                    self.listeners[type] += 1;
                    if (self.listeners[type]===1) {
                        self.send({req: 'startConsuming',
                                   path: path,
                                   options: {}});
                    }
                    aspect.after(r, "remove", function() {
                        self.listeners[type] -= 1;
                        if (self.listeners[type] === 0) {
                            self.send({req: 'stopConsuming',
                                       path: path,
                                       options: {}});
                        }
                        if (self.listeners[type] < 0) {
                            throw "too many release!";
                        }
                    });
                    return r;
                } else {
                    return { remove:function(){}};
                }
            }
        })();/*note the singleton */
    });
