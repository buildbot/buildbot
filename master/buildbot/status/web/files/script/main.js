define('jquery', [], function() {
    return jQuery;
});
 
require.config({
	paths: {		
		'selectors':'project/selectors',
		'select2': 'plugins/select2',
		'datatables-plugin': 'plugins/jquery-datatables',
		'dataTables': 'project/dataTables',
		'dotdotdot': 'plugins/jquery-dotdotdot',
		'screensize': 'project/screen-size',
		'helpers': 'project/helpers',
		'projectdropdown': 'project/project-drop-down',
		'popup': 'project/popup',
		'realtimePages':'project/realtimePages',
		'realtimerouting': 'project/realtimeRouting',
		'rtbuilddetail': 'project/rtBuildDetail',
		'rtbuilders': 'project/rtBuilders',
		'rtbuildslaves': 'project/rtBuildSlaves',
		'rtbuildqueue': 'project/rtBuildqueue',
		'jqache': 'plugins/jqache-0-1-1-min',
		'overscroll': 'plugins/jquery-overscroll',		
		'moment': 'plugins/moment-with-langs',
        'extend-moment': 'project/extendMoment',
		'mustache': "libs/mustache-wrap",
		'livestamp': "plugins/livestamp"
	}
});

define(['helpers','dataTables','popup','screensize','projectdropdown', 'extend-moment'],
	function(helpers, dataTables,popup, screenSize, projectDropDown, extendMoment) {
		
	'use strict';

	 // reveal the page when all scripts are loaded
	  
	  $(document).ready(function() {
        $('body').show();
	  	// swipe or scroll in the codebases overview
	  	if ($('#builders_page').length) {
	  	require(['overscroll'],
	        function(overscroll) {	        	
	        	$("#overScrollJS").overscroll({
	        		showThumbs:false,
	        		direction:'horizontal'
	        	});
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
			        selectors.init();
		    });
		}

		if (helpers.isRealTimePage() === true) {						
			require(['realtimerouting'],
	        function(realtimeRouting) {	        		        	
	        	realtimeRouting.init();
	        });
		}

		if ($('#builddetail_page').length > 0) {
			helpers.summaryArtifactTests();
		}
				
		// get scripts for general popups
		popup.init();
		// get scripts for the projects dropdown
		projectDropDown.init();
		// get all common scripts
		helpers.init();	
		dataTables.init($('.tablesorter-js'));	
		dataTables.init($('#tablesorterRt'));
        extendMoment.init();
	});	
});