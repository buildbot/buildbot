$(document).ready(function() {

		// variables for elements
		var loginBox = $('.login-box');
		var form = $('#loginForm');
		var excludeFields = ':button, :hidden, :checkbox, :submit';
		var allInputs = $('input', form).not(excludeFields);

		
			// the current url
			var url = window.location;

			// Does the url have 'authorized' ? 
				
			if (url.search.match(/autorized=/)) {		
				var authorizedLdap = url.search.split('&').slice(0)[0].split('=')[1].toLowerCase();
			} 

			// Does the url have 'user' ? get the fullname
			if (url.search.match(/user/)) {
				var fullNameLdap = decodeURIComponent(url.search.split('&').slice(0)[1].split('=')[1]);	
			}

			// give error message if user or pasword is incorrect
			if (authorizedLdap === 'false') {
				errorMessage(true, 'incorrect'); 
			} else if (authorizedLdap === 'true') {
				
				// set the cookie containing the full name
				storeValues(); 
				window.location = "/";
			}
		
	
	// redirect if authenticated

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

		validateloginFields(value, e);	

	});

	// validate the log in form
	function validateloginFields(form, e) {		
		var error = false;
		$(allInputs).each(function() {		
			
			if ($(this).val() === '') {
				 e.preventDefault();
				 $(this).addClass('not-valid');
				 error = true;
			}
		});
		
		// display error message if there is an error
		errorMessage(error)
	}

	// Display errormessage
	function errorMessage(error, errorMsg) {
		var errorMsg = errorMsg === ''? "Fill in your username and password before submitting" : "Incorrect username or password";
		
		if (error === true && $('.error-input').length === 0) {
			$('.login-welcome-txt', loginBox).hide();
			$(form).prepend('<div class="error-input">'+errorMsg+'</div>');
			shake(loginBox);
			
		} else if (error === true && $('.error-input').length > 0) {
			errorMsg = 'Fill in your username and password before submitting';
			$('.error-input', form).remove();
			$(form).prepend('<div class="error-input">'+errorMsg+'</div>');
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

	//var today = new Date(); var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days 
	// uncommented until I know why expiry crash
	function setCookie(name, value) { 								
		document.cookie=name + "=" + escape(value) + "; path=/"; 
	}
	
	// store cookie values from form
	function storeValues(form) {
		setCookie("fullName", fullNameLdap);
		return true;
	}
	 
	//get cookie values
	function getCookie(name) { 
	  	var re = new RegExp(name + "=([^;]+)"); 
	  	var value = re.exec(document.cookie); 
	  	return (value != null) ? unescape(value[1]) : null; 
	}

	// set cookie values in form	 
	/*
	if(userName = getCookie("fullName")) {
		$(form).children("input[name='username']").val(getCookie("userName"));
	} 
	*/

});