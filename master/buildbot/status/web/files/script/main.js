require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'selector':'project/selectors',
		'select2': 'plugins/select2',
		'datatables': 'plugins/jquery-datatables',
		'dotdotdot': 'plugins/jquery-dotdotdot'
	}
});

require(['jquery','project/selectors','project/popup','project/screen-size','project/project-drop-down','project/set-current-item','dotdotdot','project/helpers','datatables','select2','libs/socket-io'], function($, selectors, popup, screenSize, projectDropDown, setCurrentItem, dotdotdot, helpers ) {
	'use strict';

	$(document).ready(function() {
		
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
		setCurrentItem.init();
		helpers.init();	

	});
});