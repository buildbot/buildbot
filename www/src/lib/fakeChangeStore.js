define(
    [
	"dojo/_base/declare",
        "lib/fakeStore"
    ],
    function(declare, fakeStore) {
	var data=[];
        return declare(fakeStore, {
	    data:data,
	    fields: ["changeid", "revision", "committer", "files", "comments" ],
	    addData: function(o) {
		/* persist data over reload */
		data = this.data;
		this.put(o);
	    }
        });
    });
