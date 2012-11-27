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

define(["dojo/_base/declare", "bb/jsonapi", "doh/main"],function(declare,jsonapi, doh) {
    /* get the dojo script tag element */
    var baseurl= dojo.query("script[data-dojo-config]")[0].src;
    /* remove the 3 last path in the URL */
    for (var i=0;i<3;i+=1) {
	baseurl = baseurl.substr(0, baseurl.lastIndexOf("/"));
    }
    baseurl+="/";
    function testBrockenLink(t, tag) {
	/* we need to use the special doh's deferred for this to work */
	var d = new doh.Deferred();
	var ctx = {errors : []};
	var alltags = dojo.query(tag);
	ctx.toLoad = alltags.length;
	function didLoad(){
	    ctx.toLoad-=1;
	    if (ctx.toLoad===0) {
		d.callback(true);
	    }
	}
	alltags.connect("onerror", function(){
	    ctx.errors.push(this.src+" is broken link");
	    didLoad();
	});
	alltags.connect("onload", didLoad);
	alltags.forEach(function(x){x.src=x.src+"?reload";}); /* reload the images now we've setup the hooks */
	d.addCallback(function(x) {
	    t.assertEqual(ctx.errors.length, 0, ctx.errors.join("\n"));
	});
	return d;
    }
    var utils = {
	getBaseUrl : function() {
	    return baseurl;
	},
	registerBBTests: function(doh, hash, testname, tests) {
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
		    _test = "&test="+testname;
		}else{
		    _test = "?test="+testname;
		}
		doh.register(testname, require.toUrl(this.getBaseUrl()+"ui/#"+hash+_test));
	    } else {
		doh.register("sanity", [
		    function baseurl(t) { t.assertEqual(window.bb_router.base_url, utils.getBaseUrl());},
		    function brockenimg(t) { return testBrockenLink(t,"img");}
		]);
		doh.register(testname, tests);
	    }
	    /* if we return true, the test is supposed to declare the real tests */
	    return !topdog;
	}
    };
    return utils;
});
