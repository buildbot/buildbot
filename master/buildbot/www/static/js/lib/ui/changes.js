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

define(["dojo/_base/declare", "lib/ui/base", "dgrid/OnDemandGrid",
	"dgrid/Selection", "dgrid/Keyboard","dgrid/extensions/ColumnHider",
	"dojo/store/Observable", "lib/fakeChangeStore",
        "dojo/text!./templates/changes.html"],
       function(declare, Base, Grid, Selection, Keyboard, Hider, observable, Store, template) {
	   "use strict";
	   return declare([Base], {
	       templateString:template,
               constructor: function(args){
		   declare.safeMixin(this,args);
               },
	       postCreate: function(){
		   this.store = observable(new Store());
		   var maingrid = new (declare([Grid, Selection, Keyboard, Hider]))({
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
