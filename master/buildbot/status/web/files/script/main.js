require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'select2': 'plugins/select2',
		'datatables': 'plugins/jquery-datatables',
		'dotdotdot': 'plugins/jquery-dotdotdot',
		'setcurrentitem': 'project/set-current-item',
		'helpers': 'project/helpers'
	}
});

require(['jquery','setcurrentitem','dotdotdot','helpers','datatables','select2'], function($, setCurrentItem, dotdotdot, helpers) {
	'use strict';
	 
	$(document).ready(function() {
		
		setCurrentItem.init();
		helpers.init();
	});
});