define(['select2'], function () {

    "use strict";
    var selectors;

	selectors = {

		//Set the highest with on both selectors
		init: function () {
			
			$("select.select-tools-js").select2({
				width: selectors.getMaxChildWidth(".select-tools-js"),
				minimumResultsForSearch : 10
			});
			
			// display common container
			$('.show-common').click(function(){			
				var commonContainer = $(this).next('.select2-container');
				
				$(commonContainer).show(0,function(){
					$(this).select2('open');	
				});
				selectors.clickSort();
			});

			//Invoke select2 for the common selector
			$("#commonBranch_select").select2({
				placeholder: "Common branches"

			});

			// invoke the sortingfunctionality when the selector
			$("select.select-tools-js").on("select2-open", function() { 	
				selectors.clickSort();
			})
			
			// fill the options in the combobox with common options
			selectors.comboBox($('.select-tools-js'));	

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

			// Find common options
			var commonOptions = {};
			$('option', selector).each(function() {			
			    var value = $(this).text();
			    if (commonOptions[value] == null){
			        commonOptions[value] = true;
			    } else {			        
			        $(this).clone().prop('selected', false).appendTo($('#commonBranch_select'))
			    }
			});

			// remove the duplicates
			var removedDuplicatesOptions = {};
			$('#commonBranch_select option').each(function() {			
			    var value = $(this).text();
			    if (removedDuplicatesOptions[value] == null){
			        removedDuplicatesOptions[value] = true;
			    } else {
			    	$(this).remove();			        
			    }
			});

			$('#commonBranch_select').on("change", function() {
				
				var commonVal = $(this);
				
				$('option',selector).each(function() {
					
					if ($(this).val() === $(commonVal).val() ) {					
						$(this).parent().children('option').prop('selected', false);
						$(this).prop('selected', true);
					}
				});
				
				selector.trigger("change");
				
			});	

			// closing the common selector
			$('#commonBranch_select').on("select2-close", function() {
				$('.common-branch-select').hide();
			});			
		},
		// sort selector list by name
		clickSort: function () {
			var selector = $('#select2-drop');
			var sortLink = selector.children('.sort-name')

			sortLink.bind('click', function(e){
				e.preventDefault();							
				sortLink.toggleClass('direction-up');
			    $(".select2-results li",selector).sort(function(a, b) {
			        var upA = $(a).text().toUpperCase();
			        var upB = $(b).text().toUpperCase();
			        if (!sortLink.hasClass('direction-up')) {
			        	return (upA < upB) ? -1 : (upA > upB) ? 1 : 0;
			        } else {
			        	return (upA > upB) ? -1 : (upA < upB) ? 1 : 0;
			        }
			    }).appendTo($(".select2-results",selector));
			});
		}
	}	
	return selectors;
});