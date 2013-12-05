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
	var delimiter = "---";
	var values = form.children("input[name='username']").val() + delimiter + $('#rememberMe').is(':checked');
	console.log(values)
	// set cookie
	var today = new Date(); var expiry = new Date(today.getTime() + 30 * 24 * 3600 * 1000); // plus 30 days 
	function setCookie(name, value) { 
		var expire = $('#rememberMe').is(':checked') === true? 	expiry.toGMTString() : '';
		document.cookie=name + values +"; path=/; expires=" + expire; 
	}

	// store cookie values from form
	function storeValues(form) {					
		setCookie("userName", form.children("input[name='username']").val()); 					
		return true;
	}
	 
	//get cookie values
	function getCookie(name) { 
	  	var re = new RegExp(name + "=([^;]+)"); 
	  	var value = re.exec(document.cookie); 
	  	return (value != null) ? unescape(value[1]) : null; 
	}
	var sname = getCookie("userName").split(delimiter)[1]
console.log(sname)
	// set cookie values in form	 
	if(userName = getCookie("userName")) {
		$(form).children("input[name='username']").val(getCookie("userName"));
	} 

});