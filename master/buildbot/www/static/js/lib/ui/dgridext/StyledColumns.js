define(["dojo/_base/declare"],
function(declare, array){
    /* ultra simple feature that adds style configurability to dgrid
       for some reason, they decided to force this into css, while its often
       much more practicle to decide it in the grid column declaration
     */
    return declare(null, {
	_configColumn: function(column, columnId, rowColumns, prefix){
	    if (column.style) {
		this.styleColumn(columnId, column.style);
	    }
	    return this.inherited(arguments);
	}
    });
});
