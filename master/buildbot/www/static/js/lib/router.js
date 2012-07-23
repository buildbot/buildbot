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

define(["dojo/_base/declare", "dojo/_base/connect","dojo/_base/array","dojo/dom", "put-selector/put","dojo/hash"],
       function(declare, connect, array, dom, put, hash) {
    /* allow chrome to display correctly generic errbacks from dojo */
    console.error = function(err) {
	console.log(err);
	console.log(err.message);
	console.log(err.stack);
    };
    return declare([],{
	routes: [
	    /* The routes are hardcoded here for efficiency,
	       we could describe then in each plugin, but that would mean loading all plugins
	       before showing the first page 

	     route is a list of dicts which have following attributes:
	         path: regexp describing the path that matches this route
	         name: title of the navbar shortcut for this route
	         widget: lib/ui/* dijit style widget that will be loaded inside #container div
		 enableif: function that is called to findout whether this path is enabled
	    */
	    { path:"", name:"Home", widget:"home"},
	    { path:"overview", name:"Overview", widget:"overview"},
	    { path:"builders", name:"Builders", widget:"builders"},
	    { path:"builds", name:"Last Builds", widget:"builds"},
	    { path:"changes", name:"Last Changes", widget:"changes"},
	    { path:"slaves", name:"Build Slaves", widget:"buildslaves"},
	    { path:"masters", name:"Build Masters", widget:"buildmasters"},
	    { path:"users", name:"Users", widget:"users"},
	    { path:"admin", name:"Admin", enableif:function() {return this.isAdmin();}, widget:"admin"},

	    { path:"404", widget:"404"},

	    /* details paths */
	    { path:"builders/([^/]+)", widget:"builder" },
	    { path:"builders/([^/]+)/builds/([0-9]+)", widget:"build" },
	    { path:"builders/([^/]+)/builds/([0-9]+)/steps/([0-9]+)", widget:"step" },
	    { path:"builders/([^/]+)/builds/([0-9]+)/steps/([0-9]+)/logs/([^/]+)", widget:"log" },
	    { path:"slaves/([^/]+)", widget:"buildslave"},
	    { path:"masters/([^/]+)", widget:"buildmaster"},
	    { path:"users/([^/]+)", widget:"user"},
	],
	constructor: function(args){
            declare.safeMixin(this,args);
	    this.fill_navbar();
	    connect.subscribe("/dojo/hashchange", this, this.location_changed)
	    this.location_changed();
	},
	forEachRoute: function(callback) {
	    var path = hash()
	    if (path.charAt(0)=="/") {
		path = path.substr(1); /* ignore first '/' */
	    }
	    var args = {};
	    var reformated_args="";
	    path = path.split("?")
	    if (path.length>1) {
		array.forEach(path[1].split("&"), function(a) {
		    var name_val = a.split("=");
		    if (name_val.length == 2) {
			args[name_val[0]] = name_val[1];
			reformated_args += name_val[0] +"="+ name_val[1];
		    }
		});
	    }
	    path = path[0];
	    if (reformated_args.length>0) {
		reformated_args = "?"+reformated_args
	    }
	    hash("/"+path+reformated_args);
            array.forEach(this.routes, dojo.hitch(this, function(route, index){
		if (route.enableif && !dojo.hitch(this,route.enableif)()) {
		    return;
		}
		var match = path.match(route.path);
		if (match && match[0] != path) {
		    match = false;
		}
		callback(route, match, args);
	    }));
	},
	fill_navbar: function() {
	    var navlist = dom.byId("navlist");
	    var base_url = this.base_url;
	    this.forEachRoute( dojo.hitch(this, function(route, match){
		if (route.hasOwnProperty("name")){
		    var klass = "";
		    put(navlist, "li#nav_"+route.path+" a[href='"+base_url+"ui/#/"+route.path+"']", route.name);
		}
	    }));
	},
	select_navbar: function() {
	    var navlist = dom.byId("navlist");
	    var base_url = this.base_url;
	    this.forEachRoute( dojo.hitch(this, function(route, match){
	    }));
	},
	location_changed: function() {
	    var base_url = this.base_url;
	    var found = false;
	    this.forEachRoute( dojo.hitch(this, function(route, match, args){
		var nav = dom.byId("nav_"+route.path)
		if (match) {
		    var widget = "lib/ui/"+route.widget;
		    found = true;
		    require(["dijit/dijit", widget], function(dijit, Widget) {
			var old = dijit.byId("content");
			if (old) {
			    old.destroy();
			    dijit.registry.remove("content");
			}
			var w = new Widget({id:"content",path_components:match, url_args:args});
			var content = dojo.byId("content");
			content.innerHTML = "";
			w.placeAt(content)
		    });
		    if (nav) {
			nav.classList.add("active");
		    }
		} else { /* match */
		    if (nav) {
			nav.classList.remove("active");
		    }
		}
	    }));
	    if (!found) {
		hash("/404", true);
	    }
	},
	isAdmin: function() {
	    return false;
	}
    });
});