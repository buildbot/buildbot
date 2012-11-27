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

define(["dojo/_base/declare", "bb/ui/base",
	"dojo/store/Observable", "dojo/store/Memory",
	"dojo/_base/array",
        "./templates/builders.haml"
       ], function(declare, Base, observable, Memory, array, template) {
    "use strict";
    return declare([Base], {
	templateFunc : template,
        constructor: function(args){
            declare.safeMixin(this,args);
        },
	loadMoreContext: function(){
	    return this.api.getApiV1("builders").then(dojo.hitch(this, function(builders) {
		this.builders = builders;
	    }));
	},
	postCreate: function(){
	    var data=[];
	    for (var b in this.builders) {
		if (this.builders.hasOwnProperty(b)) {
		    this.builders[b].builderName = b;
		    data.push(this.builders[b]);
		}
	    }
	    var store = observable(new Memory({data:data,idProperty: "builderName"}));
	    this.createBaseGrid({
		store: store,
		cellNavigation:false,
		tabableHeader: false,
		contentMaxHeight:700,
		columns: {
		    builderName: {label:"BuilderName", formatter: function(b)
				  {
				      return "<a href='#/builders/"+b+"'>"+b+"</a>";
				  }},
		    slaves: {label:"Slaves", formatter: function(s)
			     {
				 return array.map(s, function(s) {
				     return "<a href='/#/slaves/"+s+"'>"+s+"</a>";
				 }).join(",");
			     }},
		    currentBuilds: {label:"currentBuilds",
				    get: function(o){return o;},
				    formatter: function(data)
				    {
					return array.map(data.currentBuilds, function(s) {
					    return "<a href='#/builders/"+data.builderName+"/builds/"+s+"'>"+s+"</a>";
					}).join(",");
				    }},
		    state: {label:"Status",
				    get: function(o){return o;},
				    formatter: function(data) {
					var ret= data.state;
					if (data.pendingBuilds>0){
					    ret += ", "+data.pendingBuilds+" pending builds";
					}
					return ret;
				    }
			   }
		    }
	    }, this.buildersgrid_node);
	}
    });
});
