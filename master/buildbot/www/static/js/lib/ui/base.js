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
	"dojo/_base/Deferred",
	"dojo/text!./templates/unimplemented.html"],
       function(declare, _Widget, _TemplatedMixin, _WidgetsInTemplateMixin, Deferred, template) {
	   return declare([_Widget, _TemplatedMixin, _WidgetsInTemplateMixin], {
	       templateString: template,
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
	       },
	       postCreate: function(){
		   if (this.templateString===template) {
		       this.functionality.innerText=this.path_components.toString();
		   }
               }
	   });
       });
