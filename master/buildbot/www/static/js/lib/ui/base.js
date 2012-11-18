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

define(["dojo/_base/declare", "dijit/_Widget", "dijit/_TemplatedMixin", "dijit/_WidgetsInTemplateMixin",
	"dojo/_base/Deferred", "dojo/_base/xhr",
	"./templates/error.haml"],
       function(declare, _Widget, _TemplatedMixin, _WidgetsInTemplateMixin, Deferred, xhr, template) {
	   return declare([_Widget, _TemplatedMixin, _WidgetsInTemplateMixin], {
	       templateFunc: template,
	       error_msg : undefined,
               constructor: function(args){
		   declare.safeMixin(this,args);
	       },
	       /* support for Haml as a template
		  should be a MixIn, but it is so simple that
		  we put it in the base widget
		*/
	       buildRendering: function(){
		   /* just call the templateFunc, and go ahead with _TemplateMixin implementation */
		   if(this.templateFunc){
		       this.templateString = this.templateFunc(this);
		   }
		   this.inherited(arguments);
	       },
	       create: function(){
		   var _arguments = arguments;
		   var _this = this;
		   var d = this.loadMoreContext();
		   this.readyDeferred = dojo.when(d, function() {
		       document.__base = _this;
		       _this.inherited(_arguments);
		   });
	       },
	       /* overide this function to get more context from json api
		  Maybe return deferred
		*/
	       loadMoreContext: function(){
		   if (this.templateFunc===template) {
		       this.showError("this functionality is not implemented: "+ this.path_components.toString());
		   }
	       },
	       showError: function(text) {
		   console.log("should show error:", text);
		   this.error_msg = text;
		   this.templateFunc = template; /* restore the error template that was overiden by childrens*/
	       },
	       createAPIPath: function(a) {
		   var path=[];
		   for (var i = 0;i<a.length; i+=1) {
		       path.push(a[i]);
		   }
		   path = path.join("/");
		   return path;
	       },
	       getApiV1: function() {
		   return xhr.get({handleAs:"json",url:window.bb.base_url+"api/v1/"+this.createAPIPath(arguments)});
	       },
	       getApiV2: function() {
		   return xhr.get({handleAs:"json",url:window.bb.base_url+"api/v2/"+this.createAPIPath(arguments)});
	       },
	       postCreate: function(){
		   if (this.templateString===template) {
		       this.functionality.innerText=this.path_components.toString();
		   }
               },
	       btn_class: function(results) {
		   /* return css class given results */
		   return ["btn-success", "btn-warnings", "btn-danger", "btn", "btn-inverse", "btn-info"][results];
	       },
	       createGrid: function(options, node) {
		   var self = this;
		   require ([
		       "dojo/store/Observable", "dojo/store/Memory"],
			    function(observable, Memory) {
				/* TODO: should return an observable store API result, that uses the ws api
				   Now, we simply turn the result in Memory store.
				*/
				self.getApiV2(options.apiPath).then(function(results) {
				    var store = observable(new Memory({data:results,idProperty: options.idProperty}));
				    options.store = store;
				    self.createBaseGrid(options, node);
				});
			    });
	       },
	       createBaseGrid: function(options, node) {
		   /* options: same options as dgrid +
		      - apiPath: path to list style buildbot api, where to get the data
		      - idProperty: property that will serve as identifier for queries
		   */
		   var self = this;
		   /* helper for creating a grid with good defaults */
		   require ([
		       "dgrid/OnDemandGrid",
		       "dgrid/extensions/ColumnResizer","dgrid/extensions/DijitRegistry",
		       "dgrid/Selection", "dgrid/Keyboard","dgrid/extensions/ColumnHider",
		       "lib/ui/dgridext/AutoHeight","lib/ui/dgridext/StyledColumns",
		       "lib/ui/dgridext/TypedColumns",
		       "dojo/_base/array"
		       ], function(Grid, ColumnResizer,DijitRegistry, Selection, Keyboard, ColumnHider, AutoHeight, StyledColumns, TypedColumns, array) {
			       var grid = new (declare([Grid,ColumnResizer,DijitRegistry,Selection, Keyboard, ColumnHider,
							AutoHeight, StyledColumns,TypedColumns]))(options,
												  node);
			       grid.refresh();
			   });
	       }
	   });
       });
