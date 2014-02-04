define(['datatables-plugin','helpers','text!templates/buildqueue.html','mustache'], function (dataTable,helpers,buildqueue,Mustache) {

    "use strict";
    var dataTables;
    
    dataTables = {
        init: function () {
			
			// datatable element				
			var tablesorterEl = $('.tablesorter-js');	

			// initialize with empty array before updating from json			
			var aa =[]
			// Select which columns not to sort
			tablesorterEl.each(function(i) {			    	
				var colList = [];

				var optionTable = {					
					"bPaginate": false,
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
					"bStateSave": true
				}
				
				// add only filter input nor pagination
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

				// add specific for the buildqueue page
				if ($(this).hasClass('buildqueue-table')) {						
					optionTable.aoColumns = [
						{ "mData": "builderName" },
			            { "mData": "results" },
			            { "mData": "reason" },
			            { "mData": "slave" },
			            { "mData": "steps",
			            'bSortable': false }
					]
					optionTable.aaData = aa;

					optionTable.aoColumnDefs = [
						{
						"sClass": "txt-align-left",
						"aTargets": [ 0 ]
						},
						{
						"aTargets": [ 1 ],
						"sClass": "txt-align-left",
						"mRender": function (data,full,type)  {
							var htmlnew = Mustache.render(buildqueue, {codebases:true})								
							return htmlnew;					
						}
						},
						{
						"aTargets": [ 2 ],
						"sClass": "txt-align-left",
						"mRender": function (data,full,type)  {															
							var reason = type.reason
							//var startTime = moment.unix(type.times[0]).format('MMMM Do YYYY, H:mm:ss')
							/*
							var today = moment().toDate()
							var minusDay = moment.utc(type.times[0]).diff(today)
							console.log(moment(minusDay).format('MMMM Do YYYY, H:mm:ss'))
							*/
							var waitingTime = moment.unix(type.times[0]).fromNow();						
							var htmlnew = Mustache.render(buildqueue, {reason:reason,waitingTime:waitingTime})								
							return htmlnew;							
							}
						},
						{
						"aTargets": [ 3 ],
						"sClass": "txt-align-right",
						"mRender": function (data,full,type)  {		
						/*							
							var slaveLength = type.slaves.length	
							console.log(data)						
							var htmlnew = Mustache.render(buildqueue, {slaves:true,slave:data, slavelength:slaveLength})
						    return  htmlnew; 						    
						 */
						var slavelength = type.slave.length	
						var htmlnew = Mustache.render(buildqueue, {slaves:true,slave:data,slavelength:slavelength})
						//console.log(type.slave.length)
						return htmlnew; 						    
					    }
						},
						{
							"aTargets": [ 4 ],
							"sClass": "select-input",
							"mRender": function (data,full,type)  {	
							
							var inputHtml = Mustache.render(buildqueue, {input:'true'})
							return inputHtml;							
							}
						}
					]

				} else {
					// add no sorting 
					optionTable.aoColumns = colList;	
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

			   	//initialize datatable with options
			  	var oTable = $(this).dataTable(optionTable);

			  	var filterTableInput = $('.dataTables_filter input');

			  	// insert codebase and branch on the builders page
	        	if ($('#builders_page').length && window.location.search != '') {
	        		// Parse the url and insert current codebases and branches
	        		helpers.codeBaseBranchOverview();	
				}

				// Set the marquee in the input field on load and listen for key event	
				filterTableInput.attr('placeholder','Filter results').focus();

			});
		}
	};

    return dataTables;
});