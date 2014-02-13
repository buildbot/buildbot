define(['datatables-plugin','helpers','text!templates/popups.html','text!templates/buildqueue.html','text!templates/buildslaves.html','mustache'], function (dataTable,helpers,popups,buildqueue,buildslaves,Mustache) {
   
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
				
					var preloader = Mustache.render(popups, {'preloader':'true'});
										
        			$('body').append(preloader)

					optionTable.aaSorting = [[ 2, "asc" ]]			
					optionTable.aoColumns = [
						{ "mData": "builderName" },	
			            { "mData": "sources" },
			            { "mData": "reason"},
			            { "mData": "slaves" },
			            { "mData": "brid",
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
							var sourcesLength = type.sources.length
							var htmlnew = Mustache.render(buildqueue, {showsources:true,sources:type.sources,codebase:type.codebase,sourcesLength:sourcesLength})								
							return htmlnew;												
						}
						},
						{
						"aTargets": [ 2 ],
						"sClass": "txt-align-left",						
						"mRender": function (data,full,type)  {		
							var requested = moment.unix(type.submittedAt).format('MMMM Do YYYY, H:mm:ss');																				
							var waiting = helpers.getTime(type.submittedAt, null);							
							var htmlnew = Mustache.render(buildqueue, {reason:type.reason,requested:requested,submittedAt:type.submittedAt});								
							return htmlnew;										
						},
						"fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {									
							helpers.startCounter($(nTd).find('.waiting-time'),oData.submittedAt);													
					    }
						},
						{
						"aTargets": [ 3 ],
						"sClass": "txt-align-right",						
						"mRender": function (data,full,type)  {
							var slavelength = type.slaves.length	
							var htmlnew = Mustache.render(buildqueue, {showslaves:true,slaves:data,slavelength:slavelength})						
							return htmlnew; 						    						
					    }
					    
						},
						{
						"aTargets": [ 4 ],
						"sClass": "select-input",				
						"mRender": function (data,full,type)  {								
							var inputHtml = Mustache.render(buildqueue, {input:'true',brid:type.brid})
							return inputHtml;							
							}
							
						}
					]
					
				} else if ($(this).hasClass('buildslaves-tables')) {	

					var preloader = Mustache.render(popups, {'preloader':'true'});
										
        			$('body').append(preloader);

					optionTable.aoColumns = [
						{ "mData": "friendly_name" },	
			            { "mData": "builders" },
			            { "mData": "connected"},
			            { "mData": "lastMessage" }
					]
					optionTable.aaData = aa;
					optionTable.aoColumnDefs = [
						{					
						"aTargets": [ 0 ],
						"mRender": function (data,full,type)  {												
							var htmlnew = Mustache.render(buildslaves, {buildersPopup:true,friendly_name:type.friendly_name,host_name:type.name,buildbotversion:type.version,admin:type.admin,builders:type.builders});
							return htmlnew;
						}
						},
						{
						"aTargets": [ 1 ],
						"mRender": function (data,full,type)  {
							var name;
							if (type.name != undefined) {
								name = type.name;
							} else {
								name = 'Not Available';
							}
							return name;
						}
						},
						{
						"aTargets": [ 2 ],
						"fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
							if (oData.connected === false) {
								$(nTd).addClass('offline').text('Not connected');
							} 
							else if (oData.connected === true && oData.runningBuilds.length === 0) {
								$(nTd).addClass('idle').text('Idle');
							} else if (oData.connected === true && oData.runningBuilds.length >0){							
								var runningTxt = 'Running ' + oData.runningBuilds.length + ' build(s)';
								$(nTd).addClass('building').text(runningTxt);
							}											
					    }
						},									
						{
						"aTargets": [ 3 ],
						"mRender": function (data,full,type)  {														
							var lastMessageDate = ' ('+ moment().utc(type.lastMessage).format('MMM Do YYYY, H:mm:ss') + ')';
							var lastMessageTimeAgo = moment().utc(type.lastMessage).fromNow();							
							var timeAgo =  type.lastMessage != 0? lastMessageTimeAgo + lastMessageDate : '';							
							var showTimeago = type.lastMessage != 0? true : null;							
							var htmlnew = Mustache.render(buildslaves, {showTimeago:showTimeago,timeAgo:timeAgo,lastMessageTimeAgo:lastMessageTimeAgo,lastMessageDate:lastMessageDate});
							return htmlnew;
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

			  	// special for the codebasespage
			  	if ($('#codebases_page').length != 0) {
					$('.dataTables_wrapper .top').append('<div class="filter-table-input">'+
	    			'<input value="Show builders" class="blue-btn var-2" type="submit" />'+
	    			'<h4 class="help-txt">Select branch for each codebase before showing builders</h4>'+    
	  				'</div>');
				}

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