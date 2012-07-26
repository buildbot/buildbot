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

define(["dojo/_base/declare", "lib/ui/base",
        "lib/haml!./templates/build.haml"
       ], function(declare, Base, template) {
    "use strict";
    return declare([Base], {
	templateFunc : template,
        constructor: function(args){
            declare.safeMixin(this,args);
        },
	loadMoreContext: function(){
	    var deferred = new dojo.Deferred();
	    this.builderName = this.path_components[1].toString();
	    this.number = this.path_components[2].toString();
	    /* simulate loading of all needed stuff from json API */
	    setTimeout(dojo.hitch(this, function(){ 
		this.sourceStamps = [ { changes: { changeid:"changeid1",
						   revision:"revision1",
						   committer: "me@anonymous.com",
						   files: ["path/to/file1",
							   "path/to/file2"],
						   comments: "this code should pas CI" }}];
		this.reason = "change committed";
		this.blame = ["me@anonymous.com"];
		this.properties = [ { name:"prop1", value:"value1", source:"fake"} ];
		this.times = ['two hours ago', 'last hour'];
		this.when_time = "soon";
		this.when = "~5min";
		this.text = "build succeeded";
		this.results = "SUCCESS"
		this.slave = "slave1"
		this.slave_url = "#/slaves/"+this.slave
		this.steps = [ {name:"build step",
				text:"make done",
				results:"SUCCESS",
				isStarted:true,
				isFinished:true,
				statistics:[],
				times:[0,1],
				expectations: [],
				eta:null,
				urls:{url1:"./url1.html"},
				step_number: 1,
				hidden:false,
				logs:{stdio:"./stdio"}},
			       {name:"test step",
				text:"test done",
				results:"SUCCESS",
				isStarted:true,
				isFinished:true,
				statistics:[],
				times:[0,1],
				expectations: [],
				eta:null,
				urls:{url1:"url2.html"},
				step_number: 2,
				hidden:false,
				logs:{stdio:"stdio"}}];
		this.currentStep="test step";
		this.results_class = "btn-success"
		deferred.callback({success: true}); }), 100);
	    return deferred;
	},
	isFinished: function() {
	    return this.number<5;
	}
    });
});
