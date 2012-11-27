define(["dojo/_base/declare", "dojo/_base/lang", "dojo/_base/array","moment/moment"],
function(declare, lang, array, moment){
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
		if (s) {
		    var d = moment.unix(s);
		    return "<abbr title='"+ d.format('LLLL')+"'>"+d.fromNow()+"</abbr>" ;
		}else {
		    return "n/a";
		}
	    };
	    if (column.style === undefined){
		column.style="width:110px;";
	    }
	},
	_configColumn_url: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(s) {
		return "<a href='"+s+"'>"+s;
	    };
	},
	_configColumn_revision: function(column, columnId, rowColumns, prefix){
	    column.get = function(o) { return o;};
	    column.formatter = function(o) {
		return "<a href='"+o.revlink+"'>"+o.revision;
	    };
	},
	_configColumn_filelist: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(f) {
		var r = "<ul>";
		array.map(f, function(file) {
		    r += "<li>"+file+"</li>";
		});
		return r+"<ul>";
	    };
	},
	_configColumn_user: function(column, columnId, rowColumns, prefix){
	    column.formatter = function(s) {
		if (s) {
		    var Name = lang.trim(s.split("<")[0]);
		    var id = Name;
		    if (s.split("<").length>1) {
			id = lang.trim(s.split("<")[1].split(">")[0]);
		    }
		    return "<a href='#user?id="+id+"'>"+Name;
		}
		return "unknown";
	    };
	}
    });
});
