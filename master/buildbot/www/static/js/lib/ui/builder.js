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
	"dojo/store/Observable", "dojo/store/Memory",
	"dojo/_base/array",
        "./templates/builder.haml"
], function(declare, Base, observable, Memory, array, template) {
    "use strict";
    return declare([Base], {
	templateFunc:template,
        constructor: function(args){
            declare.safeMixin(this,args);
        },
	loadMoreContext: function(){
	    this.builderName = this.path_components[1].toString();
	    return this.getApiV1("builders",this.builderName).then(
		dojo.hitch(this, function(builder) {
		    this.builder = builder;
		    window.bb.addHistory("recent_builders", this.builderName);
		    return this.getApiV1("builders",this.builderName,"builds","_all").then(dojo.hitch(this, function(builds) {
			this.builds = builds;
		    }));
	    }),
		dojo.hitch(this, function(err) { /* error */
		    if (err.status === 404) {
			this.showError("builder: "+this.builderName+" not found");
			return 0;
		    }
		}));
	},
	postCreate: function(){
	    var data=[];
	    for (var bn in this.builds) {
		if (this.builds.hasOwnProperty(bn)) {
		    var b = this.builds[bn];
		    b.number = bn;
		    array.forEach(b.properties, function(p) {
			if (p[0] === "owner") { /* I know... We need it in the db ;-)*/
			    b.owner = p[1];
			}
		    });
		    data.push(b);
		}
	    }
	    var store = observable(new Memory({data:data,idProperty: "number"}));
	    this.createBaseGrid({
		store: store,
		cellNavigation:false,
		tabableHeader: false,
		contentMaxHeight:700,
		columns: {
		    number: {label:"number",
			     get: function(o){return o;},
			     formatter: function(data){
				 return "<a href='#/builders/"+data.builderName+"/builds/"+data.number+"'>"+data.builderName+"/"+data.number+"</a>";
			     }
			    },
		    reason: "Reason",
		    slave: "Slave",
		    owner: "Owner",
		    text: {label:"results",
			   get: function(o){return o;},
			   formatter: function(data){
			       var results_class = ["btn-success", "btn-warnings", "btn-danger", "btn", "btn-inverse", "btn-info"][data.results];
			       return "<div style='height:100%;display:block' class='btn "+results_class+"'>"+data.text.join(" ")+"</div>";
			   }
			  }
		}
	    }, this.buildersgrid_node);
	}
    });
});
