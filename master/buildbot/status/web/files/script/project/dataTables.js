define(['jquery', 'datatables-plugin'], function ($) {
	 "use strict";
    var dataTables;
    
    dataTables = {
        init: function (m) {

 			// Colums with sorting 
				var colList = [];
				var tablesorterEl = $('.tablesorter-js');

				// Select which columns not to sort
				$('> thead th', tablesorterEl).each(function(i){
					
					if (!$(this).hasClass('no-tablesorter-js')) {
						colList.push(null);
					} else {
						colList.push({'bSortable': false });
					}
				});
				
				// sort and filter tabless		
				 var oTable = tablesorterEl.dataTable({
					"bPaginate": false,
					"bLengthChange": false,
					"bFilter": true,
					"bSort": true,
					"bInfo": false,
					"bAutoWidth": false,
					"bRetrieve": false,
					"asSorting": true,
					"bServerSide": false,
					"bSearchable": true,
					"aaSorting": [],
					"aoColumns": colList,					
					"oLanguage": {
					 	"sSearch": ""
					 },
					"bStateSave": true
				});

				// Set the marquee in the input field on load adn listen for key event
				$('#filterTableInput').focus().keydown(function(event) {
					oTable.fnFilter($(this).val());
				});;
		}
	}
	return dataTables;
});