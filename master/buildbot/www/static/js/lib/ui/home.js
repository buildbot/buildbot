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
        "lib/haml!./templates/home.haml"
       ], function(declare, Base, template) {
    "use strict";
    return declare([Base], {
	templateFunc : template,
	recent_builds: {},
	recent_builders: {},
        constructor: function(args){
            declare.safeMixin(this,args);
        },
	loadMoreContext: function(){
	    this.recent_builds = window.bb.localGet("recent_builds",[]);
	    this.recent_builders = window.bb.localGet("recent_builders",[]);
	},
	clearHistory: function() {
	    window.bb.localStore("recent_builds",[]);
	    window.bb.localStore("recent_builders",[]);
	    window.bb.reload();
	}
    });
});
