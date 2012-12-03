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


/* utilities, and code related to direct access to the api
   deferred based!
*/
define(["dojo/_base/declare", "dojo/_base/Deferred", "dojo/request/xhr","dojo/json",
        "dojo/_base/lang"],
       function(declare, Deferred, xhr, json, lang){
           var api_url = dojo.baseUrl + "/../../../../api/";
           var jsonrpc_curid = 0;
           return {
               createAPIPath: function(a) {
                   var path=[];
                   for (var i = 0;i<a.length; i+=1) {
                       path.push(a[i]);
                   }
                   path = path.join("/");
                   return path;
               },
               APIv2URL: function(path) {
                   return api_url+"v2/"+this.createAPIPath(path);
               },
               getApiV1: function() {
                   return xhr(api_url+"v1/"+this.createAPIPath(arguments),
                              {handleAs:"json"});
               },
               getApiV2: function() {
                   return xhr(this.APIv2URL(arguments),
                              {handleAs:"json"});
               },
               get: function(path, args, xhrargs) {
                   xhrargs = lang.mixin({handleAs:"json"}, xhrargs);
                   return xhr(this.APIv2URL(path),
                              xhrargs);
               },
               control: function(path, method, args) {
                   jsonrpc_curid+=1;
                   return xhr(api_url+"v2/"+this.createAPIPath(path),
                              {handleAs:"json",method:"POST",
                               headers: {
                                   'Content-Type': 'application/json'
                               },
                               data:json.stringify({jsonrpc:"2.0",
                                      method:method,
                                      params:args,
                                      id:jsonrpc_curid})
                              }
                             );
               }
           }; // note the singleton..
       });
