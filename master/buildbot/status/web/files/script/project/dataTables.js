define(['datatables-plugin','helpers'], function (dataTable,helpers) {

    "use strict";
    var dataTables;

    dataTables = {
        init: function () {
            //Setup sort neutral function
            dataTables.initSortNeutral();

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

				if ($(this).hasClass('input-js')) {										
					optionTable.bFilter = true;
					optionTable.oLanguage = {
					 	"sSearch": ""
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
			  	var dtWTop = $('.dataTables_wrapper .top');
			  	// special for the codebasespage
			  	if ($('#codebases_page').length != 0) {
					dtWTop.append('<div class="filter-table-input">'+
	    			'<input value="Show builders" class="blue-btn var-2" type="submit" />'+
	    			'<h4 class="help-txt">Select branch for each codebase before showing builders</h4>'+    
	  				'</div>');
				}


			  	var filterTableInput = $('.dataTables_filter input');

			  	// insert codebase and branch on the builders page
	        	if ($('#builders_page').length && window.location.search != '') {
	        		// Parse the url and insert current codebases and branches
	        		helpers.codeBaseBranchOverview(dtWTop);	
				}

				// Set the marquee in the input field on load and listen for key event	
				filterTableInput.attr('placeholder','Filter results').focus().keydown(function(event) {
					oTable.fnFilter($(this).val());
				});
				
				$('<div class="reset-sort" title="Reset table sorting"/>')
					.appendTo(dtWTop)
					.click(function(){
                    	oTable.fnSortNeutral();
                    	return false;
                	});

			});
		}, initSortNeutral: function() {
            //Add the ability to unsort
            $.fn.dataTableExt.oApi.fnSortNeutral = function ( oSettings )
            {
                /* Remove any current sorting */
                oSettings.aaSorting = [];

                /* Sort display arrays so we get them in numerical order */
                oSettings.aiDisplay.sort( function (x,y) {
                    return x-y;
                } );
                oSettings.aiDisplayMaster.sort( function (x,y) {
                    return x-y;
                } );

                /* Redraw */
                oSettings.oApi._fnReDraw( oSettings );
            };
        }
	};

    return dataTables;
});