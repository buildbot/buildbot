define(['helpers','text!templates/popups.html', 'mustache'], function (helpers,popups,Mustache) {

    "use strict";
    var popup;

	popup = {
		init: function () {

			//For non ajax boxes
						
	
			

			$('#tablesorterRt').delegate('a.popup-btn-json-js', 'click', function(e){
				e.preventDefault();								
				popup.showjsonPopup($(this).data());												
			});

			$('.popup-btn-js-2').click(function(e){			
				e.preventDefault();
				popup.nonAjaxPopup($(this));
			});

			/*
					$('#tablesorterRt').delegate('.popup-btn-js-2', 'click', function(e){			
				e.preventDefault();
				popup.nonAjaxPopup($(this));
			});
			$('#tablesorterRt').delegate('a.popup-btn-codebases-js', 'click', function(e){
				e.preventDefault();				
				//popup.showBuildersInfo($(this).data());										
			});
			*/

			$('#tablesorterRt').delegate('.popup-btn-js', 'click', function(e){
				e.preventDefault();				
				var currentUrl = document.URL;			              	
			    var parser = document.createElement('a');
			    parser.href = currentUrl;
				var url = parser.protocol + '//' + parser.host +'/json/buildqueue?builder='+$(this).attr('data-builderName');							
				popup.pendingJobs(url);					
			});

			// Display the codebases form in a popup
			$('#getBtn').click(function(e) {
				e.preventDefault();
				popup.codebasesBranches();
			});
			
			// popbox for ajaxcontent
			
			$('#tablesorterRt').delegate('.ajaxbtn', 'click', function(e){
				e.preventDefault();
				popup.externalContentPopup($(this));
			});

			$('.ajaxbtn').click(function(e){
				e.preventDefault();
				popup.externalContentPopup($(this));
			});

		}, showjsonPopup: function(jsonObj) {
			
			var mustacheTmpl = $(Mustache.render(popups, jsonObj));					
			
			$('body').append(mustacheTmpl);			
			helpers.jCenter(mustacheTmpl).fadeIn('fast', function() {
				helpers.closePopup(mustacheTmpl);
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

		}, pendingJobs: function(url) {
			var mustacheTmpl = Mustache.render(popups, {'preloader':'true'});
			var preloader = $(mustacheTmpl);
			
			$('body').append(preloader).show();
			
				var currentUrl = document.URL;			              	
			    var parser = document.createElement('a');
			    parser.href = currentUrl;
				var actionUrl = parser.protocol + '//' + parser.host + parser.pathname;							

			$.ajax({
				url:url,
				cache: false,
				dataType: "json",
				
				success: function(data) {
					
					preloader.remove();							
					console.log(data)						
					var mustacheTmpl = $(Mustache.render(popups, {pendingJobs:data,showPendingJobs:true,cancelAllbuilderURL:data[0].builderURL}));					
					var waitingtime = mustacheTmpl.find('.waiting-time-js');
					waitingtime.each(function(i){						
						helpers.startCounter($(this),data[i].submittedAt);
					});					
					mustacheTmpl.appendTo('body');					
					helpers.jCenter(mustacheTmpl).fadeIn('fast', function(){
						helpers.closePopup(mustacheTmpl);	
					});
					
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
				
				fw.children('#getForm').prepend('<div class="filter-table-input">'+
	    			'<input value="Update" class="blue-btn var-2" type="submit" />'+	    			
	  				'</div>');
				
				fw.appendTo(formContainer);												

				helpers.jCenter(mib).fadeIn('fast',function(){					
					$('#getForm .blue-btn').focus();
				});
				
				$(window).resize(function() {					
					helpers.jCenter(mib);
				});

				require(['selectors'],function(selectors) {		        	
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
            var dataReturnPage = thisEl.attr('data-returnpage');
			var rtUpdate = thisEl.attr('data-rt_update');
			var contentType = thisEl.attr('data-contenttype');
            var builder_name = thisEl.attr('data-b_name');
			var preloader = $('<div id="bowlG"><div id="bowl_ringG"><div class="ball_holderG"><div class="ballG"></div></div></div></div>');
            var body = $('body');
			body.append(preloader);
			var mib = popup.htmlModule (popupTitle);
			mib.appendTo(body);

            //get all branches
            var urlParams = {rt_update: rtUpdate, datab: datab, dataindexb: dataindexb, builder_name: builder_name, returnpage: dataReturnPage};
            var sPageURL = window.location.search.substring(1);
            var sURLVariables = sPageURL.split('&');
            $.each(sURLVariables, function(index, val) {
                var sParameterName = val.split('=');
                if (sParameterName[0].indexOf("_branch") >= 0) {
                    urlParams[sParameterName[0]] = sParameterName[1];                    
                }
            });
			
			// get currentpage with url parameters
            var url = location.protocol + "//" + location.host + "/forms/forceBuild";
			$.get(url, urlParams).done(function(data) {
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
					helpers.jCenter(mib);
				});
				// popup.customTabs();
				helpers.closePopup(mib);				
			});
		}, htmlModule: function (headLine) { // html chunks
				var mib = 
				$('<div class="more-info-box remove-js">' +
				'<span class="close-btn"></span>' +
				'<h3 class="codebases-head">'+ headLine +'</h3>' +
				'<div id="content1"></div></div>');

			return mib;
		}
	};
	 return popup;
});
