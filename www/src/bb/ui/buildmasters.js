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
        "./templates/buildmasters.haml"
       ], function(declare, Base, template) {
    "use strict";
    return declare([Base], {
        templateFunc : template,
        postCreate: function(){
            this.createGrid({
                apiPath : "master",
                idProperty: "masterid",
                columns: {
                    "masterid": { label:"#",style:"width:30px"},
                    "name": { label:"Name"},
                    "link":   { label:"Json Link", type:"url"},
                    "last_active": { label:"Last Active", type:"date"},
                    "active": { label:"Active",type:"bool"}
                    }
            }, this.buildmastersgrid_node);
        }
    });
});
