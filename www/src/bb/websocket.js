define(
    [
        "dojox/socket",
        "dojo/dom",
        "dojo/json"
    ],
    function(socket, dom, JSON) {
        var socket = socket(dojoConfig.bb.wsUrl);

        function setText(div, content){
            node = dom.byId(div);
            node.innerHTML = content;
        };

        function appendText(div, content){
            node = dom.byId(div);
            node.innerHTML = content + "<br/>" + node.innerHTML;
        };

        return {
            startWebsocket : function() {
                socket.on("open", function(event){
                    setText("status", "Open");
                    socket.send(JSON.stringify({req: 'startConsuming',
                                                path: [ 'change' ],
                                                options: {}}));
                });
                socket.on("message", function(event){
                    appendText("message", event.data);
                    console.log(event.data);
                });
                socket.on("error", function(event){
                    setText("info", event.data);
                    console.log("error");
                    console.log(event.data);
                });
                socket.on("close", function(){
                    setText("status", "Closed");
                    console.log("closed");
                });
            }
        }
    });
