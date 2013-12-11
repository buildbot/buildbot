define(['jquery', 'select2'], function ($) {

    "use strict";
    var selectors;

	selectors = {

		//Set the highest with on both selectors
		init: function () {
				
			$("select.select-tools-js").select2({
				width: selectors.getMaxChildWidth(".select-tools-js")
			});
			
			$('.show-common').click(function(){
				//$('#branchTxt').fadeOut('fast');
				var commonContainer = $(this).next('.select2-container');
				
				$(commonContainer).show(0,function(){
					$(this).select2('open');	
				});
			});
			$('#commonBranch_select').on("select2-close", function() {
				$('.common-branch-select').hide();
			});	
			$("#commonBranch_select").select2({
				placeholder: "Common branches"
			});

			selectors.clickSort($('#select2-drop .select2-results'));

		}, getMaxChildWidth: function(sel) {
			    var max = 80;
			    $(sel).each(function(){
			        var c_width = $(this).width();
			        if (c_width > max) {
			            max = c_width + 30;
			        }
			    });

			    return max;
		},
		// combobox on codebases
		comboBox: function (selector) {

			// invoke selec2 plugin
			var selectLength = $('select.select-tools-js').length;

			$('option', selector).each(function() {			
				 if ($('option[value="' + $(this).val() + '"]', selector).length == selectLength) {
	        		$(this).clone().prop('selected', false).appendTo("#commonBranch_select");			
	    		}
			});

			// Remove duplicates from the list
			var map = {};
			$("#commonBranch_select option").each(function(){
			    var value = $(this).text();
			    if (map[value] == null){
			        map[value] = true;
			    } else {
			        $(this).remove();
			    }
			});

			$('#commonBranch_select').change(function(){
				var commonVal = $(this);
				
				$('option',selector).each(function() {
					
					if ($(this).val() === $(commonVal).val() ) {					
							$(this).parent().children('option').prop('selected', false);
							$(this).prop('selected', true);
						}
				});
				
				$(selector).trigger("change");
			});

		},
		// sort selector list by name
		clickSort: function (selector) {

			$('.sort-name').click(function(e){
				var sn = $(this)
				sn.toggleClass('direction-up');
				e.preventDefault();

			    selector.children("li").sort(function(a, b) {
			        var upA = $(a).text().toUpperCase();
			        var upB = $(b).text().toUpperCase();
			        if ($(sn).hasClass('direction-up')) {
			        	return (upA < upB) ? -1 : (upA > upB) ? 1 : 0;
			        } else {
			        	return (upA > upB) ? -1 : (upA < upB) ? 1 : 0;
			        }
			    }).appendTo(selector);
			});
			
		}
	}	
	return selectors;
});