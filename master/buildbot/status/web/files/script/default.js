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
		$('.command_forcebuild').removeClass('form-open');
		$(this).next().fadeIn('fast', function (){
			$('.command_forcebuild', this).addClass('form-open')

			validateForm();
			
		});

	});

	$(document, '.close-btn').click(function(e){
		if (!$(e.target).closest('.more-info-box, .popup-btn-js').length || $(e.target).closest('.close-btn').length ) {
			$('.command_forcebuild').removeClass('form-open');
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

	// sort and filter tables logs
	$(document).one('click', function(e){

	

			var oTable = $('.tablesorter-log-js').dataTable({
			"bPaginate": false,
			"bLengthChange": false,
			"bFilter": true,
			"bSort": true,
			"bInfo": false,
			"bAutoWidth": false,
			"bRetrieve": false,
			"asSorting": true,
			"bSortable": true,
			//"oSearch": {"sSearch": " "}
			"aaSorting": [],
			
			"bStateSave": true
		});

				$.fn.dataTableExt.oApi.fnFilterAll = function(oSettings, sInput, iColumn, bRegex, bSmart) {
		    var settings = $.fn.dataTableSettings;
		     
		    for ( var i=0 ; i<settings.length ; i++ ) {
		      settings[i].oInstance.fnFilter( sInput, iColumn, bRegex, bSmart);
		    }
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


		//var oTable = $('.tablesorter-log-js').dataTable();
 		
		$("#filterinput").keydown(function(event) {
		// Filter on the column (the index) of this element
		var e = (window.event) ? window.event : event;
		if(e.keyCode == 13){
		    //var fnct = $(this).attr('onenter');
		    //eval(fnct);
		   
		    oTable.fnFilterAll(this.value);
		  }
		
		});

		$('#submitFilter').click(function(){
			oTable.fnFilterAll($("#filterinput").val());
		});
		$('#clearFilter').click(function(){
			$("#filterinput").val("");
			oTable.fnFilterAll($("#filterinput").val());
		});
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
/*
$(document).ready(function () {
    $.ajax({
        url: 'http://localhost:8001/test.xml',
        type: 'GET',
        dataType: "xml",
        success: function(data) {
           parseXml(data);
        }
    });
});




function parseXml(xml) {
	
	$(xml).find('test-case').parent().parent('test-suite').each(function(i){

		if (i < 5) {
			
			var name = $(this).attr('name');

			var testNum = $('test-case',this).length;

			$("#results").append('<ul class="summary-list"><li><span>Tests </span>'+ testNum +'</li><li>'+  +'</li></ul>');
			$("#results").append('<h1 class="main-head"> ' + name + '</h1>');
			$("#results").append('<table class="table-1 first-child tablesorter tablesorter-log-js"><thead><th>Name</th><th>Executed</th><th>Time</th></thead><tbody>');
			

			
			

			$('test-case',this).each(function(){
				var name = $(this).attr('name');			
				var success = $(this).attr('success');			
				var time = $(this).attr('time');			
				$("#results table").append('<tr><td class="txt-align-left">' + name +'</td><td>' + success +'</td><td>' + time +'</td></tr>');
				//console.log(name)
			});

			$("#results").append('</tbody></table>')
			//$("#results").append('<div>fsdfdsf</div>');
		}

	})
}
		/*
		$('<div class="items" id="link_'+id+'"></div>').html('<a href="'+url+'">'+title+'</a>').appendTo('#page-wrap');
		
		$(this).find('desc').each(function(){
			var brief = $(this).find('brief').text();
			var long = $(this).find('long').text();
			$('<div class="brief"></div>').html(brief).appendTo('#link_'+id);
			$('<div class="long"></div>').html(long).appendTo('#link_'+id);
		});
		$(xml).find('test-case').each(function(){
		var time = $(this).attr('time');
		var name = $(this).attr('name');
		var success = $(this).attr('success');
		var asserts = $(this).attr('asserts');			
		var executed = $(this).attr('executed');			
		$("#results").append(time, name, success, executed);
	});
	
	});

	
}
*/

   

});