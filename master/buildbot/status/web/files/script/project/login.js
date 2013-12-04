$(document).ready(function() {
	jQuery.fn.center = function() {
	  this.css("position", "absolute");
	  this.css("top", ($(window).height() - this.outerHeight()) / 2 + $(window).scrollTop() + "px");
	  this.css("left", ($(window).width() - this.outerWidth()) / 2 + $(window).scrollLeft() + "px");
	  return this;
	};

	$(window).resize(function() {
		$('.more-info-box-js').center();
	});

	$('.more-info-box-js').center();

	// variables for elements
	var loginBox = $('.login-box');
	var form = $('#loginForm');
	var excludeFields = ':button, :hidden, :checkbox, :submit';
	var allInputs = $('input', form).not(excludeFields);


	// Mark input field red if empty on focus out
	$(allInputs).each(function() {
		$(this).focusout(function() {
			if ($(this).val() === '') {
				$(this).addClass('not-valid');
				errorMessage(true);
			} else {
				$(this).removeClass('not-valid');
				errorMessage();
			}
		});
	}); 


	// Submit the form
	$(form).submit(function(e) {
		var value = $('#loginForm');

		validatelogin(value, e);	

	});

	// validate the log in form
	function validatelogin(form, e) {		
		var error = false;
		$(allInputs).each(function() {		
		console.log($(this).val())		
			if ($(this).val() === '') {
				 e.preventDefault();
				 $(this).addClass('not-valid');
				 error = true;
			}
		});
		if (error === false) {
			
			storeValues(form);
		}
		errorMessage(error)
	}

	// Display errormessage
	function errorMessage(error) {
		if (error === true && $('.error-input').length === 0) {
			$('.login-welcome-txt', loginBox).hide();
			$(form).prepend('<div class="error-input">Fill in your username and password before submitting</div>');
			shake(loginBox);
		} else if (error === true && $('.error-input').length > 0) {
			shake(loginBox);
		} else {
			shake(loginBox, 'remove');
		}
	}

	// Shake the box if not validating
	function shake(element, rm) {
		if (!rm) { 
			element.removeClass('shake');
			element.addClass('shake');
		} else {
			element.removeClass('shake');
		}
	}

	// set cookie
	var today = new Date(); var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days 
	function setCookie(name, value) { 
		document.cookie=name + "=" + escape(value) + "; path=/; expires=" + expiry.toGMTString(); 
	}

	// store cookie values from form
	function storeValues(form) {					
		setCookie("fullName", form.children("input[name='fullname']").val()); 					
		return true;
	}
	 
	//get cookie values
	function getCookie(name) { 
	  	var re = new RegExp(name + "=([^;]+)"); 
	  	var value = re.exec(document.cookie); 
	  	return (value != null) ? unescape(value[1]) : null; 
	}

	// set cookie values in form
	if(fullName = getCookie("fullName")) {	  	
		$(form).children("input[name='fullname']").val(fullName);
	} 

});