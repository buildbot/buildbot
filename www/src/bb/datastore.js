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

/* Generic store serving the list style data APIs of buildbot

   Serves as a translation of api between rest+websocket, and dojo's store/query/paging/notification
   api described in:

   dojo/store/api/Store.js

*/
define(["dojo/_base/declare", "dojo/_base/lang",
        "bb/jsonapi",
        "bb/websocket",
        "dojo/store/Observable",
        "dojo/store/Memory",
        "dojo/store/JsonRest",
        "dojo/store/Cache",
        "dojo/aspect"

    ],
       function(declare, lang,  api, websocket, observable, Memory, JsonRest, Cache, aspect) {
           var after = aspect.after;
           function createStore(args) {
               var memoryStore = new Memory(lang.delegate({},args));
               var restStore = new JsonRest(lang.delegate({sortParam:"sort",target: api.APIv2URL(args.path)+"/"},args));
               var store = observable(new Cache(restStore, memoryStore));
               store._num_listeners = 0;
               after(store,"query", function(results) {
                   /* hook query, in order to register web socket events
                      if somebody is observing the results */
                   after(results,"observe", function(handler) {
                       store._num_listeners +=1;
                       if (store._num_listeners === 1) {
                           store.websocket_listener = websocket.on(args.path, function(event) {
                               var id = event.message[store.idProperty];
                               var o = event.message;
                                   console.log(event);
                               if (memoryStore.index.hasOwnProperty(id)) {
                                   /* reconstruct object from the cache */
                                   var no = lang.clone(memoryStore.get(id));
                                   for (var k in o) {
                                       if (o.hasOwnProperty(k)){
                                           no[k] = o[k];
                                       }
                                   }
                                   o = no;
                               } else if (event.key.length===3 && event.key[2] === "new"){
                                   /* we dont do store access if this is a new item,
                                      the message is already containing full item,
                                      just cache it.
                                      */
                                   memoryStore.put(o);
                               } else {
                                   o = store.get(id);
                               }
                               dojo.when(o, function(o) {
                                   store.notify(o, id);
                               });
                           });
                       }
                       after(handler,"remove", function(x) {
                           store._num_listeners -=1;
                           if (store._num_listeners === 0) {
                               store.websocket_listener.remove();
                           }
                           return x;
                       });
                       return handler;
                   });
                   return results;
               });
               return store;
           }
           var datastore = {
               change: createStore({path:["change"],idProperty:"changeid"}),
               master: createStore({path:["master"],idProperty:"masterid"}),
               buildsets: createStore({path:["buildsets"]}),
               builders: createStore({path:["builders"]})
           };
           window.bb.datastore = datastore; /* for console debug */
           return datastore;
       }
      );
