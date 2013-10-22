define(['jquery'], function ($) {

    "use strict";

	$(document).ready(function(){

    		$("#filterinput").val("");
			$('.check-boxes-list input').attr('checked', false);
			
			var th = $('.table-holder');

			//  sort failues and ignored first
			var failIgnoreArray = [];
			$(th).each(function(){	
				var igCount = $('.ignored-count',this).text() > 0;
				var failCount = $('.failures-count',this).text() > 0;
				if (igCount && !failCount) {
					failIgnoreArray.push($(this))
				} else if (failCount && !igCount ) {
					failIgnoreArray.splice(0,0,$(this))
				}
				else if (igCount) {
					failIgnoreArray.splice(0,0,$(this))
				}
			});
			
			failIgnoreArray.reverse();
			$(failIgnoreArray).each(function(){
				$(this).insertAfter('#summaryTable')	
			});
			
			// insert one input field for all tables
			$.fn.dataTableExt.oApi.fnFilterAll = function(oSettings, sInput, iColumn, bRegex, bSmart) {
			    var settings = $.fn.dataTableSettings;
			     
			    for ( var i=0 ; i<settings.length ; i++ ) {
			      settings[i].oInstance.fnFilter( sInput, iColumn, bRegex, bSmart);
			    }

			    var dv = $('.dataTables_empty').closest(th)
				$(dv).hide();    
				
			};

			jQuery.fn.dataTableExt.oApi.fnFilterOnReturn = function (oSettings) {
			    var _that = this;
			  
			    this.each(function (i) {
			        $.fn.dataTableExt.iApiIndex = i;
			        var $this = this;
			        var anControl = $('input', _that.fnSettings().aanFeatures.f);
			        anControl.unbind('keyup').bind('keypress', function (e) {
			            if (e.which == 13) {
			                $.fn.dataTableExt.iApiIndex = i;
			                _that.fnFilter(anControl.val());
			            }
			        });
			        return this;
			    });
			    return this;
			};

			//console.log(colList)
			var oTable = $('.tablesorter-log-js').dataTable({
				"asSorting": false,
				"bSearchable": true,			
				"bPaginate": false,
				"bFilter": true,
				"bSort": false,
				"bInfo": false,
				"bSortable": false,
				"bAutoWidth": false
			});

			/* Add event listeners to the two range filtering inputs */
			
			function checkFilterInput() {
				var iFields = $('.check-boxes-list input:checked');
				$(th).show();
				var checkString = []
				
				$(iFields).each(function(i){
					checkString.push('(' + $(this).val() + ')');
				});
				var changesstr = checkString.join("|");
				
				oTable.fnFilterAll(changesstr, 1, true);	
					
			}
			checkFilterInput();	

			$('.dataTables_filter input').click(function(){
				checkFilterInput();
			});
			
			function inputVal(inputVal, num, bool) {
				$(th).show(inputVal);
				oTable.fnFilterAll(inputVal, num, bool);	
			}

			// submit on return
			$("#filterinput").keydown(function(event) {
			// Filter on the column (the index) of this element
			var e = (window.event) ? window.event : event;
			if(e.keyCode == 13){
			    inputVal(this.value);
			}
			
			});
			
			$('#submitFilter').click(function(){
				inputVal($("#filterinput").val());	
			});

			$('#clearFilter').click(function(){
				location.reload();
			});

			// remove empty tds for rows with colspan
			$('.colspan-js').next().remove();
			$('.colspan-js').next().remove();
	});
});