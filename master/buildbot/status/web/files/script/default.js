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
			$('.more-info-box-js, .more-info-box-js-2').hide();
			$('.command_forcebuild').removeClass('form-open');
			var newThis = $(this);
			$(window).resize(function() {
				$(newThis).next().center();
			});
			
			$(this).next().center().fadeIn('fast', function (){
				$('.command_forcebuild', this).addClass('form-open')
				validateForm();
			});
		});
	};
	popUpBtn('.popup-btn-js');
	
	$(document, '.close-btn').click(function(e){
		if (!$(e.target).closest('.more-info-box-js, .popup-btn-js, .more-info-box-js-2, .popup-btn-js-2').length || $(e.target).closest('.close-btn').length ) {
			$('.command_forcebuild').removeClass('form-open');
			$('.more-info-box-js, .more-info-box-js-2').hide();
			$('#content').empty();
		}
	}); 

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
		console.log(iVal)
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
		 	"sSearch": "Filter"
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

	// display popup box with external content

	// get content in the dropdown and display it while removing the preloader
	

	$('#getBtn').click(function() {

		$('.more-info-box-js, .more-info-box-js-2').hide();
		$('#content').empty();
		var path = $('#pathToCodeBases').attr('href');
		var preloader = '<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>';
		$('#content').append(preloader).show();
		
		$.get(path)
		.done(function(data) {
			var $response=$(data);
			$('#bowlG').remove();
			$($response).find('#formWrapper').appendTo($('#content'));
			$('.more-info-box-js-2').center();
			$("#formWrapper .select-tools-js").chosen({
				disable_search_threshold: 1,
			    no_results_text: "Nothing found!",
			    width:"170px"
  			});
  			clickSort();
			$(window).resize(function() {
				$('.more-info-box-js-2').center();
			});
			$('.more-info-box-js-2').fadeIn('fast');
			$('#getForm').attr('action', window.location.href);
		});
	});

	// Freetext filtering
	$(".select-tools-js").chosen({
		disable_search_threshold: 1,
	    no_results_text: "Nothing found!",
	    width: "100%"
  	});

	// Name sorting for filterbox
	function clickSort() {
		$('.sort-name').click(function(e){
			e.preventDefault();
			var ch = $(this).next($('.chosen-results li'));
			var items = $('.chosen-with-drop .chosen-results li').get();
			console.log(ch, items)
			items.sort(function(a,b){
			  var keyA = $(a).text();
			  var keyB = $(b).text();
			  if (keyA < keyB) return -1;
			  if (keyA > keyB) return 1;
			  return 0;
			});
			var ul = $(this).next($('.chosen-results'));
			
			$.each(items, function(i, li){
			  ul.append(li);
			});

		});
	}
	clickSort();

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

});