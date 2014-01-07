$( document ).ready(function() {
// Colums with sorting 
				
var tablesorterEl = $('.tablesorter-js');				

// Select which columns not to sort
tablesorterEl.each(function(i){			    	
	var colList = [];

	var optionTable = {
		"bPaginate": false,
		//"sPaginationType": "full_numbers",
		"bLengthChange": false,
		"bFilter": false,
		"bSort": true,
		"bInfo": false,
		"bAutoWidth": false,
		"sDom": '<"table-wrapper"t>',
		"bRetrieve": true,
		"asSorting": true,
		"bServerSide": false,
		"bSearchable": true,
		"aaSorting": [],
		"iDisplayLength": 50,
		"bStateSave": true,

		//"fnDrawCallback": function( oSettings ) {
	     // alert( 'DataTables has redrawn the table' );

	    //},
	   // "fnInitComplete": function(oSettings, json) {
	    	//$('#formWrapper').show();	
				 //alert( 'DataTables has finished its initialisation.' );
		//}
	}

	// add searchfilterinput, length change and pagination
	if ($(this).hasClass('tools-js')) {						
		optionTable.bPaginate = true;
		optionTable.bLengthChange = true;
		optionTable.bInfo = true;
		optionTable.bFilter = true;
		optionTable.oLanguage = {
		 	"sSearch": "",
		 	 "sLengthMenu": 'Entries per page<select>'+
	            '<option value="10">10</option>'+
	            '<option value="25">25</option>'+
	            '<option value="50">50</option>'+
	            '<option value="100">100</option>'+
	            '<option value="-1">All</option>'+
	            '</select>'
		};
		optionTable.sDom = '<"top"flip><"table-wrapper"t><"bottom"pi>';
	}

	// remove sorting from selected columns
    $('> thead th', this).each(function(i){
        
        if (!$(this).hasClass('no-tablesorter-js')) {
            colList.push(null);
        } else {
            colList.push({'bSortable': false });
        }

    });

    optionTable.aoColumns = colList;
    
   	//initialize datatable with options
  	var oTable = $(this).dataTable(optionTable);

  	var filterTableInput = $('.dataTables_filter input');

	// Set the marquee in the input field on load and listen for key event
	filterTableInput.attr('placeholder','Filter results').focus().keydown(function(event) {
		oTable.fnFilter($(this).val());
	});  

});
});