define(['jquery','noise'], function ($,noisy) {

    "use strict";
 
	$(document).ready(function(){

			$('body').noisy({
			    'intensity' : 1,
			    'size' : 200,
			    'opacity' : 0.03,
			    'fallback' : '',
			    'monochrome' : false
			});

    		$("#filterinput").val("");
			
			var checkboxesList = $('#CheckBoxesList input');
			checkboxesList.prop('checked', true);

			//console.log($('.check-boxes-list input'))
			var th = $('.table-holder');

			//  sort failues and ignored first
			
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
				"bPaginate": false,
				"bFilter": true,
				"bSort": false,
				"bInfo": false,
				"bAutoWidth": false
			});

			/* Add event listeners to the two range filtering inputs */
			
			function checkFilterInput() {
				var iFields = $('#CheckBoxesList input:checked');
				
				th.show();
				var checkString = []
				
				iFields.each(function(i){
					checkString.push('(' + $(this).val() + ')');
				});
				var changesstr = checkString.join("|");
				
				oTable.fnFilterAll(changesstr, 1, true);	
					
			}
			checkFilterInput();	

			checkboxesList.click(function(){
				checkFilterInput();
			});
			
			function inputVal(inputVal, num, bool) {
				th.show(inputVal);
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

			// clear the input field
			$('#clearFilter').click(function(){
				location.reload();
			});

			// remove empty tds for rows with colspan
			//$('.colspan-js').nextAll('td').remove();

			$('.failure-detail-cont', th).each(function(){	

				var fdTxt = $('.failure-detail-txt', this);
				$(this).height(fdTxt.height() + 40);
				
				if (!fdTxt.is(':empty')) {
					$('<a href="#" class="new-window var-3 grey-btn">Open new window</a>').insertBefore(fdTxt);
					if (fdTxt.height() >= 130) {
						$('<a class="height-toggle var-3 grey-btn" href="#">Show more</a>').insertBefore(fdTxt);	
					}
				}
				
			});		

			function nWin(newWinHtml) {

			  	var w = window.open();
			  	
				var html = "<style>body {padding:0 0 0 15px;margin:0;"+
				"font-family:'Courier New';font-size:12px;white-space:"+
				" pre;overflow:auto;}</style>"+newWinHtml;
				
				$(w.document.body).html(html);

			}

			// show content of exceptions in new window
			$('.new-window').click(function(e){
				e.preventDefault();
				var newWinHtml = $(this).parent().find($('.failure-detail-txt')).html();
				nWin(newWinHtml);
			});

			// show more / hide
			$('.height-toggle').click(function(e){
				
				e.preventDefault();
				var fdtf = $(this).parent().find($('.failure-detail-txt'));
				var parentTd = $(this).parent().parent();

				fdtf.css({'max-height':'none', 'height': ''});
				
				if (!$(this).hasClass('expanded-js')) {
					$(this).addClass('expanded-js');
					$(this).text('Show less');
					fdtf.css('height','');
					parentTd.css('height',fdtf.height() + 40);
				} else {
					$(this).removeClass('expanded-js');
					$(this).text('Show more');
					fdtf.css('max-height',130);
					parentTd.css('height',170);
				}
			});

			// url for back to builddetailpage
			if (window.location.pathname.indexOf('steps') > 0) {
				(function( $ ) {
					var sourceUrl = window.location.pathname.split('/');
					var decodedUriSearch = window.location.search;

					var decodedBuildDetailName = decodeURIComponent(sourceUrl.slice(4)[0]);
					var decodedBuildDetailNumber = decodeURIComponent(sourceUrl.slice(6)[0])

					var url = [];
					
					$.each(sourceUrl, function(i,value){
						if (i < 7) {
							url.push(value)
						}
					});
					
					var urlJoined = url.join('/');
					var urljoinedSearch = urlJoined + decodedUriSearch
					
					$('#btd').text(decodedBuildDetailName + ' #' + decodedBuildDetailNumber);
					$('#btd').attr('href', urljoinedSearch);

				})( jQuery );
			}
	});
});