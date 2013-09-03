require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'select2': 'plugins/select2',
		'datatables': 'plugins/jquery-datatables',
		'setcurrentitem': 'project/set-current-item',
		'helpers': 'project/helpers'
	}
});

require(['jquery','helpers','setcurrentitem', 'datatables', 'select2'], function($, setCurrentItem, helpers) {
	'use strict';
	 
	$(document).ready(function() {
		
		helpers.init();
		setCurrentItem.init();
		
		// Colums with sorting 

		var colList = [];
		$('.tablesorter-js > thead th').each(function(i){
			
			if (!$(this).hasClass('no-tablesorter-js')) {
				colList.push(null);
			} else {
				colList.push({'bSortable': false });
			}
		});
		
		// sort and filter tabless		
		$('.tablesorter-js').dataTable({
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
		
			
	});
});