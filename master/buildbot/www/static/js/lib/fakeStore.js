define(
    [
	"dojo/_base/declare",
	"dojo/store/Memory"
    ],
    function(declare, Memory) {
	return declare([Memory], {
	    fields: ["field1"],
            constructor: function(args){
		declare.safeMixin(this,args);
		this.interval = setInterval(dojo.hitch(this, this.addSomeData), 1000); //simulate adding some data every second
	    },
	    addSomeData: function() {
		var randomfeed = "sdlkjs alkdj alsdjl ksdj lsajldkjaslkdj asdlkja iwjedo ajlskj lhsl";
		var curId=0;
		if (this.data.length>0) {
		    curId = this.data[this.data.length-1].id+1;
		}
		var o = {id:curId};
		this.curId+=1;
		for (var i=0; i < this.fields.length; i+=1) {
		    var l = Math.floor(Math.random()*20);
		    var v = "";
		    for (var j=0; j<l; j+=1) {
			v +=randomfeed[Math.floor(Math.random()*randomfeed.length)];
		    }
		    o[this.fields[i]] = v;
		}
		this.addData(o);
	    },
	    addData: function(o) {
		this.put(o);
	    },
	    destroy: function(){
		clearInterval(this.interval);
		this.inherited(arguments);
	    }
	});
    });
