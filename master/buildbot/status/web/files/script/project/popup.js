define(['helpers','text!templates/popups.html', 'mustache'], function (helpers,popups,Mustache) {

    "use strict";
    var popup;

	popup = {
		init: function () {

			//For non ajax boxes
			$('.popup-btn-js-2').click(function(e){
				console.log('click');
				e.preventDefault();
				popup.nonAjaxPopup($(this));
			});

			// for dynamic added links in buildqueue
			$('.tablesorter-js').delegate('.popup-btn-js-2', 'click', function(e){
				e.preventDefault();
				popup.nonAjaxPopup($(this));
			});


			//For builders pending box
			$('.popup-btn-js').each(function(i){
				$(this).attr('data-in', i).on('click', function(e){
					e.preventDefault();
					popup.pendingJobs($(this));				
				});				
			});

			// Display the codebases form in a popup
			$('#getBtn').click(function(e) {
				e.preventDefault();
				popup.codebasesBranches();
			});
			
			// popbox for ajaxcontent
			$('.ajaxbtn').click(function(e){
				e.preventDefault();
				popup.externalContentPopup($(this));
			});

		}, validateForm: function(formContainer) { // validate the forcebuildform
				var formEl = $('.command_forcebuild', formContainer);
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
	    				var mustacheTmplErrorinput = Mustache.render(popups, {'errorinput':'true', 'text':'Fill out the empty revision fields or clear all before submitting'});
						var errorinput = $(mustacheTmplErrorinput);
	    				$(formEl).prepend(errorinput);
	    			} 
					e.preventDefault();
				}
			});
		}, nonAjaxPopup: function(thisEl) {
			var clonedInfoBox = thisEl.next($('.more-info-box-js')).clone();				
			clonedInfoBox.appendTo($('body'));
			helpers.jCenter(clonedInfoBox).fadeIn('fast', function() {
				helpers.closePopup(clonedInfoBox);
			});
			$(window).resize(function() {
				helpers.jCenter(clonedInfoBox);				
			});

		}, pendingJobs: function(thisEl) {

			var thisi = thisEl.attr('data-in');
			
			var rtUpdate = thisEl.attr('data-rt_update');
			var mustacheTmpl = Mustache.render(popups, {'preloader':'true'});
			var preloader = $(mustacheTmpl);
			$('body').append(preloader).show();
			// get currentpage with url parameters
			$.ajax({
				url:'',
				cache: false,
				dataType: "html",
				data: {
					rt_update:'pending'
				},
				success: function(data) {
					preloader.remove();
					var doc = document.createElement('html');
 					doc.innerHTML = data;
					
					var pendListRes = $('.more-info-box-js', doc);
					
					var mib;
					pendListRes.each(function(i){
						if (i == thisi) {
							mib = $(this);
						}
					});
					
					mib.appendTo('body');
					
					helpers.jCenter(mib).fadeIn('fast');
					$(window).resize(function() {						
						helpers.jCenter(mib);
					});

					helpers.closePopup(mib);
					
				}
			});

		}, codebasesBranches: function() {
			
			var path = $('#pathToCodeBases').attr('href');

			var mustacheTmpl = Mustache.render(popups, {'preloader':'true'});
			var preloader = $(mustacheTmpl);

			$('body').append(preloader).show();
			
			var mustacheTmplOutBox = Mustache.render(popups, {'popupOuter':'true','headline':'Select branches'});
			var mib = $(mustacheTmplOutBox);
			
			mib.appendTo('body');


			$.get(path)
			.done(function(data) {

				var formContainer = $('#content1');	
				preloader.remove();
				
				var fw = $(data).find('#formWrapper')
				
				$(fw).appendTo(formContainer);
				
				$('#content .blue-btn').val('update');

				// remove unwanted html for the popup box
				$('#content1 .filter-table-input label, #content1 .filter-table-input .help-txt').remove();

				helpers.jCenter(mib).fadeIn('fast');
				
				$(window).resize(function() {					
					helpers.jCenter(mib);
				});


				require(['selectors'],function(selectors) {
		        	selectors.comboBox('#formWrapper .select-tools-js');
		        	selectors.init();
					$(window).resize(function() {
						helpers.jCenter($('.more-info-box-js'));
						
					});
				});
				
				$('#getForm').attr('action', window.location.href);	
				$('#getForm .blue-btn[type="submit"]').click(function(){
					$('.more-info-box-js').hide();				
				});

				helpers.closePopup(mib);

			});
		}, customTabs: function (){ // tab list for custom build
			$('.tabs-list li').click(function(i){
				var indexLi = $(this).index();
				$(this).parent().find('li').removeClass('selected');
				$(this).addClass('selected');
				$('.content-blocks > div').each(function(i){
					if ($(this).index() != indexLi) {
						$(this).hide();
					} else {
						$(this).show();
					}
				});

			});
		}, externalContentPopup: function(thisEl) { // custom buildpopup on builder and builders
			var popupTitle = thisEl.attr('data-popuptitle');
			var datab = thisEl.attr('data-b');
			var dataindexb = thisEl.attr('data-indexb');
			var rtUpdate = thisEl.attr('data-rt_update');
			var contentType = thisEl.attr('data-contenttype'); 

			var mustacheTmpl = Mustache.render(popups, {'preloader':'true'});
			var preloader = $(mustacheTmpl);
			$('body').append(preloader);
			var mustacheTmplOutBox = Mustache.render(popups, {'popupOuter':'true','headline':popupTitle});
			var mib = $(mustacheTmplOutBox);			
			mib.appendTo($('body'));
			
			// get currentpage with url parameters
			$.get('', {rt_update: rtUpdate, datab: datab, dataindexb: dataindexb}).done(function(data) {
				var exContent = $('#content1');
				preloader.remove();
				$(data).appendTo(exContent);

				
				// Insert full name from cookie
				if (contentType === 'form') {
					helpers.setFullName($("#usernameDisabled, #usernameHidden", exContent));	
					popup.validateForm(exContent);
				}
				
				helpers.jCenter(mib).fadeIn('fast');
				$(window).resize(function() {
					helpers.jCenter(mib)
				});
				// popup.customTabs();
				helpers.closePopup(mib);
				

			});
		}
	};
	 return popup;
});
