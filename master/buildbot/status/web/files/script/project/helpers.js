define(['jquery', 'project/screen-size'], function ($, screenSize) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {
		
		// only for testing		
    	$('<div/>').addClass('windowsize').css({'position': 'absolute', 'fontSize': '20px'}).prependTo('body');

    	var ws = $(window).width() + ' ' +  $(window).height();

    	$('.windowsize').html(ws);
    	    	
        $(window).resize(function(event) {
        	ws = $(window).width() + ' ' +  $(window).height();
        	$('.windowsize').html(ws);
        });

        // submenu overflow on small screens
        
        var isSmallScreen = screenSize.isSmallScreen();
                
        function menuItemWidth() {
        	if (isSmallScreen){	
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
			isSmallScreen = screenSize.isSmallScreen();
			menuItemWidth();			  
		});
		
        // json on frontpage
        if ($('#tb-root').length != 0) {
	         $.ajax({
			    url: "/json?filter=0",
			    dataType: "json",
			    type: "GET",
			    cache: false,
			    success: function (data) {
			        
			        var arrayBuilders = [];
			        var arrayPending = [];
			        var arrayCurrent = [];
			        $.each(data.builders, function (key, value) {
	        			arrayBuilders.push(key);
	        			arrayPending.push(value.pendingBuilds);
	        			if (value.state == 'building') {
	        				arrayCurrent.push(value.currentBuilds);
	        			}
	    			});

			        function sumVal(arr) {
			        	var sum = 0;
						$.each(arr,function(){sum+=parseFloat(this) || 0;});
						return sum;
			        };
					
	    			var arraySlaves = [];
			        $.each(data.slaves, function (key) {
	        			arraySlaves.push(key);
	    			});

	    			var arrayProjects = [];
			        $.each(data.project, function (key) {
	        			arrayProjects.push(key);
	    			});

	    			$('.summary-td').append("<td><span>" + ' ' + arraySlaves.length + '</span></td> ' + "<td><span>" + ' ' + sumVal(arrayPending) + '</span></td> ')	
			    }
			});
		   
		}

        // Colums with sorting 
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
				console.log($(this).val())
				oTable.fnFilter($(this).val());
			});
		}

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
		$('.more-info-box-js-3').remove();
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
