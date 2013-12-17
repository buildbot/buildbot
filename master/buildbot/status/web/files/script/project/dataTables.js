define(['jquery', 'datatables-plugin'], function ($) {
	 "use strict";
    var dataTables;
    
    dataTables = {
        init: function () {

 			// Colums with sorting 
				
				var tablesorterEl = $('.tablesorter-js');
				var filterTableInput = $('#filterTableInput');
				// Select which columns not to sort
			    tablesorterEl.each(function(i){			    	
			    	var colList = [];

			        $('> thead th', this).each(function(i){
			            
			            if (!$(this).hasClass('no-tablesorter-js')) {
			                colList.push(null);
			            } else {
			                colList.push({'bSortable': false });
			            }

			        });

			       //initialize datatable
			      	var oTable = $(this).dataTable({
						"bPaginate": false,
						"bLengthChange": false,
						"bFilter": true,
						"bSort": true,
						"bInfo": false,
						"bAutoWidth": false,
						"bRetrieve": true,
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

			    	// Set the marquee in the input field on load and listen for key event
					filterTableInput.focus().keydown(function(event) {
						oTable.fnFilter($(this).val());
					});  

			    });
				
				// sort and filter tables	
				

							
		}
	}
	return dataTables;
});