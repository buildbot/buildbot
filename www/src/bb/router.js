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

define(["dojo/_base/declare", "dojo/_base/connect","dojo/_base/array","dojo/dom", "put-selector/put","dojo/hash", "dojo/io-query", "dojo/dom-class", "dojo/window"],
       function(declare, connect, array, dom, put, hash, ioquery, domclass, win) {
    "use strict";
    /* allow chrome to display correctly generic errbacks from dojo */
    console.error = function(err) {
        console.log(err);
        console.log(err.message);
        console.log(err.stack);
    };
    return declare([],{
        constructor: function(args){
            declare.safeMixin(this,args);
            this.fill_navbar();
            connect.subscribe("/dojo/hashchange", this, this.location_changed);
            this.location_changed();
            window.bb = this;
        },
        forEachRoute: function(callback) {
            var path = hash();
            if (path.charAt(0)==="/") {
                path = path.substr(1); /* ignore first '/' */
            }
            path = path.split("?", 2);
            array.forEach(dojo.config.bb.routes, dojo.hitch(this, function(route, index){
                if (route.enableif && !this.checkEnableIf(route)) {
                    return;
                }
                var match = path[0].match(route.path);
                if (match && match[0] !== path[0]) {
                    match = false;
                }
                callback(route, match, path);
            }));
        },
        checkEnableIf: function(route) {
            var ok = true;
            array.forEach(route.enableif, dojo.hitch(this, function(ei) {
                if (ei === 'admin') {
                    ok = ok && this.isAdmin();
                } else {
                    ok = false;
                }
            }));
            return ok;
        },
        fill_navbar: function() {
            var navlist = dom.byId("navlist");
            var baseUrl = dojo.config.baseUrl;
            this.forEachRoute( dojo.hitch(this, function(route, match){
                if (route.hasOwnProperty("name")){
                    var klass = "";
                    put(navlist, "li#nav_"+route.path+" a[href='"+baseUrl+"#/"+route.path+"']", route.name);
                }
            }));
        },
        location_changed: function() {
            var found = false;
            this.forEachRoute( dojo.hitch(this, function(route, match, path){
                var nav = dom.byId("nav_"+route.path);
                if (match) {
                    var widget = "bb/ui/"+route.widget;
                    var args = {};
                    var reformated_args="";
                    var test;
                    found = true;
                    /* allows user to pass URL style arguments to the UI
                       e.g: /builder/builder1?force1.reason=generated%20form&force1.branch=new_branch
                    */
                    if (path.length>1) {
                        args = ioquery.queryToObject(path[1]);
                        reformated_args = ioquery.objectToQuery(args);
                    }
                    path = path[0];
                    if (reformated_args.length>0) {
                        reformated_args = "?"+reformated_args;
                    }
                    if(args.hasOwnProperty("test")) {
                        test = args.test;
                        delete args.test;
                    }
                    /* make sure we give user feedback in case of malformated args */
                    hash("/"+path+reformated_args);
                    require(["dijit/dijit", widget], function(dijit, Widget) {
                        var w = new Widget({path_components:match, url_args:args});
                        var loading = dojo.byId("loading");
                        loading.style.display = "block";
                        loading.style.left = (((win.getBox().w+loading.offsetWidth)/2))+"px";
                        dojo.when(w.readyDeferred, function() {
                            var old = window.bb.curWidget;
                            if (old) {
                                old.destroy();
                                dijit.registry.remove(old.id);
                            }
                            var content = dojo.byId("content");
                            content.innerHTML = "";
                            loading.style.display = "none";
                            w.placeAt(content);
                            w.startup();
                            window.bb.curWidget = w;
                            if(test) {
                                if (window.doh) { /* doh already loaded! We need to cleanup the iframe */
                                    location.reload();
                                    return;
                                }
                                require(["doh/main","bb/tests/"+test],function(doh) {doh.run();});
                            }
                        });
                    });
                    if (nav) {
                        domclass.add(nav, "active");
                    }
                } else { /* match */
                    if (nav) {
                        domclass.remove(nav, "active");
                    }
                }
            }));
            if (!found) {
                hash("/404", true);
            }
        },
        isAdmin: function() {
            return false;
        },
        /* we could use dojox.storage, but we really want to only use html5, and not embed flash crap in our build */
        localStore: function(key, value) {
            if (localStorage === null || typeof localStorage === 'undefined') {
                return;
            }
            value = dojo.toJson(value);
            try { // ua may raise an QUOTA_EXCEEDED_ERR exception
                localStorage.setItem(key,value);
            } catch(e) {
            }
        },
        localGet: function(key, _default) {
            if (localStorage === null || typeof localStorage === 'undefined') {
                return _default;
            }
            var json = localStorage.getItem(key);
            if (json === null){
                return _default;
            }
            return dojo.fromJson(json);
        },
        addHistory: function(history_type, title) {
            var recent_stuff = this.localGet(history_type, []);
            if (typeof recent_stuff === 'undefined' || typeof recent_stuff.push === 'undefined') {
                recent_stuff = []; /* if it is not a list better reset it! */
            }
            for (var i = 0; i < recent_stuff.length; i+=1 ) {
                if (recent_stuff[i].title === title) {
                    return; /* dont add same stuff again */
                }
            }
            if (recent_stuff.length >= 5) {
                recent_stuff.pop();
            }
            recent_stuff.unshift({url:"#"+hash(), title:title});
            this.localStore(history_type, recent_stuff);
        },
        reload: function(){
            this.location_changed();
        }


    });
});
