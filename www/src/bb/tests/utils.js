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
    function testBrokenLink(t, tag) {
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
		    function brokenimg(t) { return testBrokenLink(t,"img");}
		]);
		doh.register(testname, tests);
	    }
	    /* if we return true, the test is supposed to declare the real tests */
	    return !topdog;
	},
	assertDomText : function(t, expected, query) {
		    var e = dojo.query(query);
		    t.assertEqual(1, e.length, "query needs only one result: "+query);
		    t.assertEqual(expected, e[0].innerText," query's text is not as expected:"+query);
	},
	playTestScenario: function(scenario) {
	    var d = new doh.Deferred();
	    jsonapi.control(["testhooks"], "playScenario", { scenario:scenario}).then(function(res) {
		d.callback(res);
	    });
	    return d;
	},
	/* play the scenario, and wait for any dom change triggered by tested code
	   on a given css query */
	playTestScenarioWaitForDomChange: function(scenario, query) {
	    function get_query_html() {
		var r ="";
		dojo.query(query).forEach(function(e){r+= e.innerHTML;});
		return r;
	    }
	    var orig_html = get_query_html();
	    var d = new doh.Deferred();
	    dojo.when(this.playTestScenario(scenario), function(res){
		/* poll for dom change for 500 msecs,
		   doh times out at 1000msec
		 */
		var retries = 50;
		var t = window.setInterval(function() {
		    retries -= 1;
		    if (retries <= 0 || get_query_html() !== orig_html) {
			window.clearInterval(t);
			d.callback(res);
		    }
		}, 10);
	    });
	    return d;
	},
	when : function(d, f) {
	    if (d.addCallback) {
		d.addCallback(f);
		return d;
	    } else {
		var _d = new doh.Deferred();
		_d.addCallback(f);
		_d.callback(d);
		return _d;
	    }
	}
    };
    return utils;
});
