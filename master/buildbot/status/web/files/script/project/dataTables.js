define(['jquery', 'datatables-plugin'], function ($) {
	 "use strict";
    var dataTables;
    
    dataTables = {
        init: function (m) {

 				// Colums with sorting 
	        
				var colList = [];
				$('.tablesorter-js > thead th').each(function(i){
					
					if (!$(this).hasClass('no-tablesorter-js')) {
						colList.push(null);
					} else {
						colList.push({'bSortable': false });
					}
				});
				var oTable = dataTables.oTable(colList);
				

				if ($('.tablesorter-js').length) {
					$('#filterTableInput').focus();

					$('#filterTableInput').keydown(function(event) {
						oTable.fnFilter($(this).val());
					});
					
				}
			
		},
		oTable: function(colList) {
			// sort and filter tabless		
			 var oTable = $('.tablesorter-js').dataTable({
				"bPaginate": false,
				"bLengthChange": false,
				"bFilter": true,
				"bSort": true,
				"bInfo": false,
				"bAutoWidth": false,
				"bRetrieve": false,
				"asSorting": true,
				"bSearchable": true,
				"aaSorting": [],
				"aoColumns": colList,
				"oLanguage": {
				 	"sSearch": ""
				 },
				"bStateSave": true
			});
			return oTable;
		}
	}
	return dataTables;
});