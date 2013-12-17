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
		'realtimerouting': 'project/realtimeRouting',
		'rtbuilddetail': 'project/rtBuildDetail',
		'rtbuilders': 'project/rtBuilders',
		'rtfrontpage': 'project/rtFrontpage',
		'jqache': 'plugins/jqache-0-1-1-min'
	}
});

require(['jquery','helpers','popup','screensize','projectdropdown'], 
	function($, helpers, popup, screenSize, projectDropDown ) {
	'use strict';

	$(document).ready(function() {
		

		// get all common scripts
		helpers.init();			
		// get scripts for general popups
		popup.init();
		// get scripts for the projects dropdown
		projectDropDown.init();

		
		if ($('.tablesorter-js').length > 0) {
			require(['dataTables'],
	        function(dataTables) {
	        	dataTables.init();
	        });
		}
 	
		if (helpers.getCurrentPage('isrealtime') && $('body').attr('data-realTimeServer') != '') {						
			require(['realtimerouting', 'jqache'],
	        function(realtimeRouting) {
	        	realtimeRouting.init();
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
		if ($('#builddetail_page').length > 0) {
			helpers.summaryArtifactTests();
		}
		
		

	});
});