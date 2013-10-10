define(['jquery', 'project/screen-size'], function ($, screenSize) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {

			// creating a new websocket
			if ($('#tb-root').length != 0) {
				(function( $ ) {
					 var sock = null;
			         var ellog = null;

			            var wsuri;
			            ellog = document.getElementById('log');

			            if (window.location.protocol === "file:") {
			               wsuri = "ws://localhost:9000";
			            } else {
			               wsuri = "ws://" + window.location.hostname + ":9000";
			            }

			            if ("WebSocket" in window) {
			               sock = new WebSocket(wsuri);
			            } else if ("MozWebSocket" in window) {
			               sock = new MozWebSocket(wsuri);
			            } else {
			               log("Browser does not support WebSocket!");
			               window.location = "http://autobahn.ws/unsupportedbrowser";
			            }

			            if (sock) {
			               sock.onopen = function() {
			                  log("Connected to " + wsuri);
			               }

			               sock.onclose = function(e) {
			                  log("Connection closed (wasClean = " + e.wasClean + ", code = " + e.code + ", reason = '" + e.reason + "')");
			                  sock = null;
			               }

			               sock.onmessage = function(e) {
			                  log(e.data);
			               }
			            }
			         
			         
			        function sumVal(arr) {
			          var sum = 0;
			          $.each(arr,function(){
			            sum+=parseFloat(this) || 0;
			          });
			          return sum;
			        };

			         function log(m) {

			            try {

			                var obj = JSON.parse(m);
			                  $.each(obj.builders, function() {

			                      
			                      var arraySlaves = [];

			                      $.each(obj.slaves, function (key) {
			                        arraySlaves.push(key);
			                      });

			                      var arrayPending = [];
			                      $.each(obj.builders, function (key, value) {
			                          arrayPending.push(value.pendingBuilds);
			                      });

			                      $('#slavesNr').html(arraySlaves.length);
			                      $('#pendingBuilds').html(sumVal(arrayPending));
			                    
			                  });
			            }
			            catch(err) {
			            }
			           
			         };
		         })( jQuery );
    		 }
			/*
				// only for testing		
				$('<div/>').addClass('windowsize').css({'position': 'absolute', 'fontSize': '20px'}).prependTo('body');

				var ws = $(window).width() + ' ' +  $(window).height();

				$('.windowsize').html(ws);
				    	
			    $(window).resize(function(event) {
			    	ws = $(window).width() + ' ' +  $(window).height();
			    	$('.windowsize').html(ws);
			    });
			*/
        // submenu overflow on small screens
        
        var isMediumScreen = screenSize.isMediumScreen();
                
        function menuItemWidth() {
        	
        	if (isMediumScreen){	
	        	var wEl = 0;
	        	$('.breadcrumbs-nav li').each(function(){
		        	wEl += $(this).outerWidth();
		        });
		        $('.breadcrumbs-nav').width(wEl + 100);
	        } else {
	        	$('.breadcrumbs-nav').width('');	
	        }
	        
        }
        menuItemWidth();
		$(window).resize(function() {
			isMediumScreen = screenSize.isMediumScreen();
			menuItemWidth();			  
		});
		


        // Colums with sorting 
        (function($) {
			var colList = [];
			$('.tablesorter-js > thead th').each(function(i){
				
				if (!$(this).hasClass('no-tablesorter-js')) {
					colList.push(null);
				} else {
					colList.push({'bSortable': false });
				}
			});
			


			// sort and filter tabless		
			 var oTable = $('.tablesorter-js').dataTable({
				"bPaginate": false,
				"bLengthChange": false,
				"bFilter": true,
				"bSort": true,
				"bInfo": false,
				"bAutoWidth": false,
				"bRetrieve": false,
				"asSorting": true,
				"bSearchable": true,
				"aaSorting": [],
				"aoColumns": colList,
				"oLanguage": {
				 	"sSearch": ""
				 },
				"bStateSave": true
			});

			if ($('.tablesorter-js').length) {
				$('#filterTableInput').focus();

				$('#filterTableInput').keydown(function(event) {
					oTable.fnFilter($(this).val());
				});
			}

		})(jQuery);


	// check all in tables
	$(function selectAll() {
	    $('#selectall').click(function () {
	    	
	        $('.fi-js').prop('checked', this.checked);
	    });
	});
	$('.force-individual-js').click(function(e){
		e.preventDefault();
		/*
		$(this).prev('.fi-js').prop('checked', true);
		*/
		var iVal = $(this).prev().prev().val();
		
		var hi = $('<input checked="checked" name="cancelselected" type="hidden" value="'+  iVal  +'"  />');
		$(hi).insertAfter($(this));
		$('#formWrapper form').submit();

	});
	
	// chrome font problem fix
	$(function chromeWin() {
		var is_chrome = /chrome/.test( navigator.userAgent.toLowerCase() );
		var isWindows = navigator.platform.toUpperCase().indexOf('WIN')!==-1;
		if(is_chrome && isWindows){
		  $('body').addClass('chrome win');

		}
	});
	
	// tooltip for long txtstrings
	if ($('.ellipsis-js').length) {
		$(".ellipsis-js").dotdotdot();
	}

	function toolTip(ellipsis) {
		$(ellipsis).parent().hover(function(){
			
			var txt = $(ellipsis, this).attr('data-txt');
			
			var toolTip = $('<div/>').addClass('tool-tip').text(txt);

			$(this).append($(toolTip).css({
				'top':$(ellipsis, this).position().top -10,
				'left':$(ellipsis, this).position().left - 20
			}).show());

		}, function(){
			$('.tool-tip').remove();
		});
		// ios fix
		$(document).bind('click touchstart', function(e){
			$('.tool-tip').remove();
			$(this).unbind(e);
		});

	}
		
	toolTip('.ellipsis-js');

	//parse reason string
	$('.codebases-list .reason-txt').each(function(){
		var rTxt = $(this).text().trim();
		if (rTxt === "A build was forced by '':") {
			$(this).remove();
		}
	});

	$('#submitBtn').click(function(){
		$('#formWrapper form').submit();
	});
	
	
	
	// run build with default parameters
	$('.run-build-js').click(function(e){
		$('.remove-js').remove();
		e.preventDefault();
		var datab = $(this).prev().attr('data-b');
		var dataindexb = $(this).prev().attr('data-indexb');
		var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
		$('body').append(preloader).show();
		$.get('', {extform: true, datab: datab, dataindexb: dataindexb}).done(function(data) {
			$('#bowlG').remove();
			$('<div/>').addClass('formCont').hide().appendTo('body')		
			$(data).appendTo('.formCont')
			$('.formCont .command_forcebuild .grey-btn').trigger('click');
		});
	});

	
	
	}
	};

    return helpers;
});
