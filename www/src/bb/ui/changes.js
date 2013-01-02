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
        "./templates/changes.haml"
       ], function(declare, Base, template) {
    "use strict";
    return declare([Base], {
        templateFunc : template,
        postCreate: function(){
            this.createGrid({
                apiPath : "change",
                idProperty: "changeid",
                contentMaxHeight:700,
                columns: {
                    "changeid": { label:"#",style:"width:30px"},
                    "author": { label:"Author",type:"user"},
                    "branch": { label:"Branch",style:"width:100px"},
                    "repository": { label:"Repository", type:"url"},
                    "revision": { label:"Revision", type:"revision"},
                    "when_timestamp": { label:"Date",type:"date"},
                    "files": { label:"Files",type:"filelist"}
                    },
                sort:[{attribute:"changeid",descending:1}]
            }, this.maingrid_node);
        }
    });
});
