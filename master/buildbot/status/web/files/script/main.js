require.config({
	paths: {
		'jquery': 'libs/jQuery-2-0-3',
		'select2': 'plugins/select2',
		'datatables': 'plugins/jquery-datatables',
		'setcurrentitem': 'project/set-current-item',
		'helpers': 'project/helpers'
	}
});

require(['jquery','setcurrentitem','helpers', 'datatables', 'select2'], function($, setCurrentItem, helpers) {
	'use strict';
	 
	$(document).ready(function() {
		
		setCurrentItem.init();
		helpers.init();

	});
});