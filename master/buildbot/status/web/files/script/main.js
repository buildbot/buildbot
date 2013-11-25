require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'selectors':'project/selectors',
		'select2': 'plugins/select2',
		'datatables-plugin': 'plugins/jquery-datatables',
		'dataTables': 'project/dataTables',
		'dotdotdot': 'plugins/jquery-dotdotdot',
		'screensize': 'project/screen-size',
		'currentitem': 'project/set-current-item',
		'helpers': 'project/helpers',
		'projectdropdown': 'project/project-drop-down',
		'popup': 'project/popup',
		'realtime': 'project/realtime',
		'jqache': 'plugins/jqache-0-1-1-min'
	}
});

require(['jquery','currentitem','popup','screensize','projectdropdown','helpers'], 
	function($,setCurrentItem, popup, screenSize, projectDropDown, helpers ) {
	'use strict';

	$(document).ready(function() {

		setCurrentItem.init();
		
		if ($('.tablesorter-js').length > 0) {
			require(['dataTables'],
	        function(dataTables) {
	        	dataTables.init();
	        });
		}
 	
		if (helpers.getCurrentPage('isrealtime') && $('body').attr('data-realTimeServer') != '') {
			require(['realtime', 'jqache'],
	        function(realtime) {
	        	realtime.init();
	        });
		}

		// tooltip for long txtstrings
		if ($('.ellipsis-js').length) {
			require(['dotdotdot'],
	        function(dotdotdot) {
	        	$(".ellipsis-js").dotdotdot();
	        });
			
		}

		// codebases combobox selector
		if ($('#commonBranch_select').length || $('.select-tools-js').length) {
			require(['selectors'],
		        function(selectors) {
			        selectors.comboBox('.select-tools-js');	
			        selectors.init();
		    });
		}
		
		popup.init();
		projectDropDown.init();
		
		helpers.init();	

	});
});