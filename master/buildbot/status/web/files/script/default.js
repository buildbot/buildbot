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

	$(function centerPopup(){
		$('.more-info-box').each(function(){
				$(this).css('left',($(window).width()-$(this).outerWidth())/ 2 + 'px');
				$(this).css('top',($(window).height()-$(this).outerHeight())/ 2 + 'px');
		});
	});
	$('.popup-btn-js').click(function(e){
		e.preventDefault();
		$('.more-info-box').hide();
		$(this).next().fadeIn('fast');
	});

	$(document, '.close-btn').click(function(e){
		if (!$(e.target).closest('.more-info-box, .popup-btn-js').length || $(e.target).closest('.close-btn').length ) {
			$('.more-info-box').fadeOut('fast');
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
	
		$('.tablesorter').dataTable({
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
});