$(document).ready(function() {
	//Default text on login input fields
    $(".defaultText").focus(function(srcc) {
        if ($(this).val() == $(this)[0].value)
        {
 
            $(this).removeClass("defaultTextActive");
            $(this).val("");
        }
    });
    
    $(".defaultText").blur(function() {
        if ($(this).val() == "")
		{
            $(this).addClass("defaultTextActive");
            $(this).val($(this)[0].value);
        }
    });
    
    $(".defaultText").blur();        

    $("form").submit(function() {
		$(".defaultText").each(function() {
			if($(this).val() == this.value) 
			{
				$(this).val("");
			}
		});
	});

	$('#password-clear').show();
	$('#password-password').hide();
	 
	$('#password-clear').focus(function() {
	    $('#password-clear').hide();
	    $('#password-password').show();
	    $('#password-password').focus();
	});
	$('#password-password').blur(function() {
	    if($('#password-password').val() == '') {
	        $('#password-clear').show();
	        $('#password-password').hide();
	    }
	});


	//Show / hide

	function centerPopup(className){
		$(className).each(function(){
			$(this).css('left',($(window).width()-$(this).outerWidth())/ 2 + 'px');
			$(this).css('top',($(window).height()-$(this).outerHeight())/ 2 + 'px');
		});
	};

	centerPopup('.more-info-box');

	function popUpBtn(classBtn, classHide){

		$(classBtn).click(function(e){
			e.preventDefault();
			$('.more-info-box-js, .more-info-box-js-2').hide();
			$('.command_forcebuild').removeClass('form-open');
			$(this).next().fadeIn('fast', function (){
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
	        $('#inputfields').find(':checkbox').prop('checked', this.checked);
	    });
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

	// validate the form
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
		centerPopup('.more-info-box-js-2');
		$('#content').append(preloader).show();
		$('.more-info-box-js-2').fadeIn('fast');
		$.get(path)
		.done(function(data) {
			var $response=$(data);
			$('#bowlG').remove();
			$($response).find('#formWrapper').appendTo($('#content'));
		});
	});

});