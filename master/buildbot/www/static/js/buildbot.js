require({
    packages: [{name: "lib", location: "/static/js/lib"}]
},
        [
            "lib/websocket",
            "lib/changes",
            "dojo/on",
            "dojo/dom",
            "dojo/json",
            "dojo/html",
            "dojo/_base/fx",
        ],

        function(websocket, changes, on, dom, JSON, fx, html) {
            setTimeout(websocket.startWebsocket, 0);

            //Add onClick event for changes
            var changesButton = dom.byId("changesButton");
            on(changesButton, "click", function(evt){
                data = changes.loadSingleChange();
                data.then(function(d) {
                    var content = dom.byId("changesContent");
                    // html.set(dom.byId("content"), JSON.stringify(d));
                    content.innerHTML += JSON.stringify(d);
                });
            });
        });


