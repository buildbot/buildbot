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
	"dgrid/OnDemandGrid","dgrid/extensions/DijitRegistry", "dojo/store/Observable", "dojo/store/Memory",
	"dojo/_base/array", "dojo/fx/Toggler", "dojo/fx",
        "./templates/build.haml"
       ], function(declare, Base, Grid, DijitRegistry, observable, Memory, array, Toggler, fx, template) {
    "use strict";
    return declare([Base], {
	templateFunc : template,
	togglers : [],
        constructor: function(args){
            declare.safeMixin(this,args);
        },
	fullName: function() {
	    return this.builderName+"/"+this.number;
	},
	loadMoreContext: function(){
	    this.builderName = this.path_components[1].toString();
	    this.number = this.path_components[2].toString();
	    return this.getApiV1("builders",this.builderName,"builds",this.number).then(
		dojo.hitch(this, function(b) { /* success */
		    this.b = b;
		    window.bb.addHistory("recent_builds", this.fullName());
		}),
		dojo.hitch(this, function(err) { /* error */
		    if (err.status === 404) {
			this.showError("build: "+this.fullName()+" not found");
			return 0;
		    }
		}));
	},
	isFinished: function() {
	    return this.b.times[1]!==null;
	},
	postCreate: function(){
	    if (this.error_msg) {
		return;
	    }
	    /* build the properties grid */
	    var data=[];
	    array.forEach(this.b.properties, function(p) {
		data.push({ name:p[0], value:p[1], source:p[2]});
	    });
	    var store = observable(new Memory({data:data,idProperty: "name"}));
	    var grid = new (declare([Grid,DijitRegistry]))({
		store: store,
		cellNavigation:false,
		tabableHeader: false,
		columns: {
		    name: "Name",
		    value: "Value",
		    source: "Source"
		}
	    }, this.propertiesgrid_node);
	    grid.refresh();
	},
	stepLogsDisplayStyle: function(step) {
	    if ((step.isFinished && step.results[0]>0) ||
		step.isStarted && !step.isFinished) {
		return "";
	    }
	    return "display:none";
	},
	toggleLogs: function(ev) {
	    var toggler = null;
	    array.forEach(this.togglers, function(t) {
		if (t.node === ev.target.nextSibling) {
		    toggler = t;
		}
	    });
	    if (toggler === null) {
		toggler = new Toggler({
		    node:ev.target.nextSibling,
		    showFunc: fx.wipeIn,
		    hideFunc: fx.wipeOut
		});
		toggler.hidden = dojo.style(toggler.node, "display")==="none";
		this.togglers.push(toggler);
	    }
	    if (toggler.hidden) {
		console.log("show");
		toggler.show();
	    } else {
		console.log("hide");
		toggler.hide();
	    }
	    toggler.hidden = !toggler.hidden;
	}
    });
});
