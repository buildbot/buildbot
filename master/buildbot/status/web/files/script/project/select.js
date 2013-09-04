define(['jquery', 'plugins/select2'], function ($) {

    "use strict";
    var selectorStyled;
    
    selectorStyled = {
        init: function () {

			//Set the highest with on both selectors
			function getMaxChildWidth(sel) {
			    max = 80;
			    $(sel).each(function(){
			        c_width = parseInt($(this).width());
			        if (c_width > max) {
			            max = c_width + 30;
			        }
			    });
			    $('#selectorWidth').width(max);
			    return max;
			}
			
			$(".select-tools-js").select2({
				width: getMaxChildWidth(".select-tools-js")
			});
			$("#commonBranch_select").select2({
				placeholder: "Common branches",
				width: $("#commonBranch_select").width() + 140
			});

			// combobox on codebases
			
			function comboBox(selector) {

				// invoke selec2 plugin
				var selectLength = $('select.select-tools-js').length;

				var sortLink = $('<a href="#" class="sort-name">Sort by name</a>');
				$(sortLink).insertAfter($('.select2-search'));
				
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

			}
			comboBox('.select-tools-js');


			function clickSort(selector) {
				$('.sort-name').click(function(e){
					var sn = $(this)
					$(sn).toggleClass('direction-up');
					e.preventDefault();

				    $(selector).children("li").sort(function(a, b) {
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
			
			clickSort('#select2-drop .select2-results');

		}
	};

    return selectorStyled;
});