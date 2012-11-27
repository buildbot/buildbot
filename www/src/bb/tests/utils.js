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

define(["dojo/_base/declare", "bb/jsonapi"],function(declare,jsonapi) {
    /* get the dojo script tag element */
    var baseurl= dojo.query("script[data-dojo-config]")[0].src;
    /* remove the 4 last path in the URL */
    for (var i=0;i<4;i+=1) {
	baseurl = baseurl.substr(0, baseurl.lastIndexOf("/"));
    }
    baseurl+="/";
    return declare([],{
	getBaseUrl : function() {
	    return baseurl;
	},
	goToBuildbotHash: function(doh, hash, test) {
	    var topdog;
	    var _test;
	    try{
		topdog = (window.parent === window) || !Boolean(window.parent.doh);
	    }catch(e){
		//can't access window.parent.doh, then consider ourselves as topdog
		topdog=true;
	    }
	    if (topdog) {
		if (hash.indexOf("?")>0) {
		    _test = "&test="+test;
		}else{
		    _test = "?test="+test;
		}
		doh.register(test, require.toUrl(this.getBaseUrl()+"ui/#"+hash+_test));
	    }
	    /* if we return true, the test is supposed to declare the real tests */
	    return !topdog;
	}
	})();/* note the singleton */
});
