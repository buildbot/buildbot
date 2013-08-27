
$(document).ready(function() {
	
	//Show / hide

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
		$(document, '.close-btn').click(function(e){
			if (!$(e.target).closest('.more-info-box-js, .popup-btn-js, .more-info-box-js-2, .popup-btn-js-2').length || $(e.target).closest('.close-btn').length ) {
				$('.command_forcebuild').removeClass('form-open');
				$('.more-info-box-js, .more-info-box-js-2').hide();
				$('#content').empty();
			}
		}); 
	}
	closePopUp();
	// class on selected menuitem
	$(function setCurrentItem(){
		var path = window.location.pathname.split("\/");
		
		 $('.top-menu a').each(function(index) {
		 	var thishref = this.href.split("\/");
	        if(thishref[thishref.length-1].trim().toLowerCase() == path[1].trim().toLowerCase())
	            $(this).parent().addClass("selected");
	    });
	});

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

	// sort and filter tables
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
		"bSortable": true,
		//"oSearch": {"sSearch": " "}
		"aaSorting": [],
		"oLanguage": {
		 	"sSearch": ""
		 },
		"bStateSave": true
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
		/* clear all button
			$(".clear-btn", formEl).click(function (e) {
				$('input[name="fmod_revision"]',formEl).val("").removeClass('not-valid');
				e.preventDefault();
			});
		*/
	}

	// Freetext filtering



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

	// Name sorting for filterbox
	function clickSort() {
		$('.sort-name').click(function(e){
			e.preventDefault();

			var items = $('#select2-drop .select2-results li').get();
			
			items.sort(function(a,b){
			  var keyA = $(a).text();
			  var keyB = $(b).text();
			  if (keyA < keyB) return -1;
			  if (keyA > keyB) return 1;
			  return 0;
			});
			var ul = $(this).next($('.select2-results'));
			
			$.each(items, function(i, li){
			  ul.append(li);
			});

		});
	}
	clickSort();


	// display popup box with external content

	// get content in the dropdown and display it while removing the preloader
	

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

			$("#formWrapper .select-tools-js").select2({
				width:"150px"
			});
			$("#formWrapper #commonBranch_select").select2({
				placeholder: "Common branches"
			});

			comboBox('#formWrapper .select-tools-js');

			$('.more-info-box-js-2').center();
			
  			clickSort();
			$(window).resize(function() {
				$('.more-info-box-js-2').center();
			});
			$('.more-info-box-js-2').fadeIn('fast');
			$('#getForm').attr('action', window.location.href);
		});
	});
	
	// tooltip for long txtstrings
	$('.ellipsis-js').hover(function(){
		var tthis = $(this);
		var txt = $(this).text();
		var toolTip = $('<div/>').addClass('tool-tip').text(txt);
		$(this).css('overflow', 'visible')
		$(this).append(toolTip);
	}, function(){
		$(this).css('overflow', 'hidden');
		$('.tool-tip', this).remove();
	});

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

			$('.shortcut-js .scLink').each(function(){
				var scLink = $(this).attr('data-sc');
				$(this).attr('href', scLink);
			});

			$(mib).slideDown('fast');

			$(document, '.close-btn').click(function(e){
			    if (!$(e.target).closest(mib).length || $(e.target).closest('.close-btn').length) {
			        	
			        $(mib).slideUp('fast', function(){
			        	$(this).remove();	
			        });
			        
			        $(this).unbind(e);
			    }
			});
	
		});

	});
	
});