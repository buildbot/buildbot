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

define(["dojo/_base/declare","dojo/_base/array", "lib/ui/base", "dgrid/OnDemandGrid",
	"dgrid/Selection", "dgrid/Keyboard","dgrid/extensions/ColumnHider",
	"lib/ui/dgridext/AutoHeight","lib/ui/dgridext/StyledColumns",
	"dojo/store/Observable", "lib/fakeChangeStore",
        "./templates/changes.haml"],
       function(declare, arrayUtil, Base, Grid, Selection, Keyboard, Hider, AutoHeight, StyledColumns, observable, Store, template) {
	   "use strict";
	   return declare([Base], {
	       templateFunc:template,
               constructor: function(args){
		   declare.safeMixin(this,args);
               },
	       postCreate: function(){
		   this.store = observable(new Store());
		   this.store.autoUpdate();
		   var maingrid = new (declare([Grid, Selection, Keyboard, Hider,AutoHeight,StyledColumns]))({
                       loadingMessage: "loading...",
		       store: this.store,
		       minRowsPerPage: 15,
		       maxRowsPerPage: 15,
		       cellNavigation:false,
		       tabableHeader: false,
		       columns: {
			   id: {label:"ID", width:"10px"},
			   changeid: "Change ID",
			   revision:
			   {label: "Revision",
			    sortable: false},
			   committer:
			   {label: "committer",
			    sortable: false},
			   comments:
			   {label: "Comments",
			    sortable: false}
		       }
		   }, this.maingrid_node);
		   maingrid.on(".dgrid-row:dblclick", dojo.hitch(this, this.rowDblClick));
		   maingrid.on("dgrid-select", dojo.hitch(this, this.select));
		   maingrid.refresh();
		   this.maingrid = maingrid;
	       },
	       select: function(event) {
		   var _this = this;
		   if (this.withSelect) {
		       this.withSelect(arrayUtil.map(event.rows, function(row){ return _this.store.get(row.id); }));
		   }
	       },
	       rowDblClick : function(evt) {
	       },
	       destroy: function(){
		   this.maingrid.destroy();
		   this.store.destroy();
	       }
	   });
       });
