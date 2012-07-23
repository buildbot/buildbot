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

define(["dojo/_base/declare", "dijit/_Widget", "dijit/_Templated",
       	"dojo/text!./templates/unimplemented.html"],
       function(declare, _Widget, _Templated, template) {
	   "use strict";
	   return declare([_Widget, _Templated], {
	       widgetsInTemplate: true,
	       templateString: template,
               constructor: function(args){
		   declare.safeMixin(this,args);
	       },
	       postCreate: function(){
		   if (this.templateString==template) {
		       this.functionality.innerText=this.path_components.toString();
		       console.log(this.url_args)
		   }
               }
	   });
       });
