define(['jquery'], function ($) {

    "use strict";
    var helpers;
    
    helpers = {
        init: function () {
		
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
		$('.tablesorter-js').dataTable({
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
			"bStateSave": true,
			"fnInitComplete": function() {
				$('.dataTables_filter input').attr('placeholder', 'Filter results')
            	$('.dataTables_filter input').focus();
        	}
		});

		// center infobox
	jQuery.fn.center = function() {
		var h = $(window).height();
	    var w = $(window).width();

	    // adjust height to browser height
	    this.css('height',(h < 400) ? 300 : '');

		this.css("position", "absolute");
		this.css("top", ($(window).height() - this.outerHeight()) / 2 + $(window).scrollTop() + "px");
		this.css("left", ($(window).width() - this.outerWidth()) / 2 + $(window).scrollLeft() + "px");
		return this;
	};

	function popUpBtn(classBtn, classHide){

		$(classBtn).click(function(e){
			e.preventDefault();
			$('.cloned').hide();
			$('.command_forcebuild').removeClass('form-open');

			var clonedInfoBox = $(this).next().clone().addClass('cloned');

			$('body').append(clonedInfoBox);

			$(window).resize(function() {
				$(clonedInfoBox).center();
			});
			
			$(clonedInfoBox).center().fadeIn('fast', function (){
				$('.command_forcebuild', this).addClass('form-open')
				validateForm();
			});
		});
	};
	popUpBtn('.popup-btn-js');

	function closePopUp() {
			


		$(document, '.close-btn').bind('click touchstart', function(e){
			if (!$(e.target).closest('.more-info-box-js, .popup-btn-js, .more-info-box-js-2, .popup-btn-js-2').length || $(e.target).closest('.close-btn').length ) {
				$('.command_forcebuild').removeClass('form-open');
				$('.more-info-box-js, .more-info-box-js-2').hide();
				$('#content').empty();
			}

		}); 
		
	}
	closePopUp();
	
	//Set the highest with on both selectors
			function getMaxChildWidth(sel) {
			    var max = 80;
			    $(sel).each(function(){
			        var c_width = $(this).width();
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

		// sort selector list by name
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

	// validate the forcebuildform
	function validateForm() {
		var formEl = $('.form-open');
		var excludeFields = ':button, :hidden, :checkbox, :submit';
		$('.grey-btn', formEl).click(function(e) {

			var allInputs = $('input', formEl).not(excludeFields);
			
			var rev = allInputs.filter(function() {
				return this.name.indexOf("revision") >= 0;
			});
			
			var emptyRev = rev.filter(function() {
				return this.value === "";
			});

			if (emptyRev.length > 0 && emptyRev.length < rev.length) {
				
				rev.each(function(){
    				if ($(this).val() === "") {
						$(this).addClass('not-valid');
					} else {
						$(this).removeClass('not-valid');
					}
    			});

    			$('.form-message', formEl).hide();

    			if (!$('.error-input', formEl).length) {
    				$(formEl).prepend('<div class="error-input">Fill out the empty revision fields or clear all before submitting</div>');
    			} 
				e.preventDefault();
			}
		});
		
	}

	// display popup box with external content	
	$('#getBtn').click(function() {

		$('.more-info-box-js, .more-info-box-js-2').hide();
		$('#content').empty();
		var path = $('#pathToCodeBases').attr('href');
		var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
		$('body').append(preloader).show();
		
		$.get(path)
		.done(function(data) {
			var $response=$(data);
			$('#bowlG').remove();
			
			var fw = $($response).find('#formWrapper')
			
			$(fw).appendTo($('#content'));
			
			$('.more-info-box-js-2').fadeIn('fast');

			$('.more-info-box-js-2').center();

			$("#formWrapper .select-tools-js").select2({
				width: getMaxChildWidth(".select-tools-js")
			});
			$("#formWrapper #commonBranch_select").select2({
				placeholder: "Common branches"
			});

			comboBox('#formWrapper .select-tools-js');
			
			$('.select2-drop').bind('click touchstart', function(e){
				e.stopPropagation();
				$(this).unbind(e);
			});	

  			clickSort('#select2-drop .select2-results');
			$(window).resize(function() {
				$('.more-info-box-js-2').center();
			});
			
			$('#getForm').attr('action', window.location.href);	
			$('#getForm .grey-btn[type="submit"]').click(function(){
				$('.more-info-box-js-2').hide();				
			});			
		});
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

	$('#projectDropdown').click(function(e){
		
		var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
		$('body').append(preloader).show();

		var path = "/projects";
		var mib = $('<div class="more-info-box more-info-box-js-3"><span class="close-btn"></span><h3>Builders shorcut</h3><div id="content1"></div></div>');
		$(mib).insertAfter($(this));

		$.get(path)
		.done(function(data) {
			var $response=$(data);
			$('#bowlG').remove();
			
			var fw = $($response).find('.tablesorter-js');
			$(fw).appendTo($('#content1'));
			$('.more-info-box-js-3 .tablesorter-js').removeClass('tablesorter')

			$('.top-menu .shortcut-js .scLink').each(function(){
				var scLink = $(this).attr('data-sc');
				$(this).attr('href', scLink);
			});

			$(mib).slideDown('fast');

			$(document, '.close-btn').bind('click touchstart', function(e){
			    if (!$(e.target).closest(mib).length || $(e.target).closest('.close-btn').length) {
			        	
			        $(mib).slideUp('fast', function(){
			        	$(this).remove();	
			        });
			        
			        $(this).unbind(e);
			    }
			});
	
		});

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

	$('.ajaxbtn').click(function(e){
		e.preventDefault();
		var datab = $(this).attr('data-b');
		var dataindexb = $(this).attr('data-indexb');
		
		var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
		$('body').append(preloader).show();
		var mib3 = $('<div class="more-info-box more-info-box-js-3"><span class="close-btn"></span><h3>Run custom build</h3><div id="content1"></div></div>');
		$(mib3).insertAfter($(this));

		$.get('', {extform: true, datab: datab, dataindexb: dataindexb}).done(function(data) {

			$('#bowlG').remove();
			$(data).appendTo($('#content1'));
			$(mib3).center();
			$(window).resize(function() {
				$(mib3).center();
			});
			$(mib3).fadeIn('fast');

			$(document, '.close-btn').bind('click touchstart', function(e){
		
			    if (!$(e.target).closest(mib3).length || $(e.target).closest('.close-btn').length) {
			        	        	
			        $(mib3).remove();
			        	
			        $(this).unbind(e);
			    }
			});

		});

	});
	
	}
	};

    return helpers;
});
