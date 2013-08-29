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
		
		setCurrentItem.init();
		

		
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
			"bSortable": true,
			//"oSearch": {"sSearch": " "}
			"aaSorting": [],
			"oLanguage": {
			 	"sSearch": ""
			 },
			"bStateSave": true
		});	
		
			helpers.init();
	});
});