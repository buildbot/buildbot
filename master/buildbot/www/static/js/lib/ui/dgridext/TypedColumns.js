define(["dojo/_base/declare"],
function(declare, array){
    /* implement basic types for columns to display them in a nice way
     */
    return declare(null, {
	_configColumn: function(column, columnId, rowColumns, prefix){
	    var func = this["_configColumn_"+column.type];
	    if (func !== undefined) {
		func(column, columnId, rowColumns, prefix);
	    }
	    return this.inherited(arguments);
	},
	_configColumn_bool: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(s) {
		if (s) {
		    return "<div class='btn btn-mini btn-success' style='height:100%;width:30px;'>Yes</div>";
		}
		else {
		    return "<div class='btn btn-mini btn-danger' style='height:100%;width:30px'>No</div>";
		}
	    };
	    if (column.style === undefined){
		column.style="width:50px;";
	    }
	},
	_configColumn_date: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(s) {
		var d = new Date(0);
		d.setUTCSeconds(s);
		return d.toLocaleDateString()+" "+ d.toLocaleTimeString();
	    };
	    if (column.style === undefined){
		column.style="width:250px;";
	    }
	},
	_configColumn_url: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(s) {
		return "<a href='"+s+"'>"+s;
	    };
	}
    });
});
