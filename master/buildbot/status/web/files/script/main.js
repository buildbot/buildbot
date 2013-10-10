require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'selector':'project/selectors',
		'select2': 'plugins/select2',
		'datatables': 'plugins/jquery-datatables',
		'dotdotdot': 'plugins/jquery-dotdotdot'
	}
});

require(['jquery','project/set-current-item','project/selectors','project/popup','project/screen-size','project/project-drop-down','dotdotdot','project/helpers','datatables','select2'], 
	function($, setCurrentItem,selectors, popup, screenSize, projectDropDown, dotdotdot, helpers ) {
	'use strict';

	$(document).ready(function() {

		setCurrentItem.init();
		// codebases combobox selector
		if ($('#commonBranch_select').length) {
			selectors.comboBox('.select-tools-js');
		}
		// General codebases selectors
		if ($('.select-tools-js').length) {
			selectors.init();
		}
		popup.init();
		projectDropDown.init();
		
		helpers.init();	

	});
});