$(document).ready(function() {


// sort and filter tables logs


		var th = $('.table-holder');
		$("#filterinput").val("");

		$.fn.dataTableExt.oApi.fnFilterAll = function(oSettings, sInput, iColumn, bRegex, bSmart) {
		    var settings = $.fn.dataTableSettings;
		     
		    for ( var i=0 ; i<settings.length ; i++ ) {
		      settings[i].oInstance.fnFilter( sInput, iColumn, bRegex, bSmart);
		
		    }
		    var dv = $('.dataTables_empty').closest(th)
			$(dv).hide();    
		    
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

			var oTable = $('.tablesorter-log-js').dataTable({
			"bPaginate": false,
			"bFilter": true,
			"bSort": true,
			"bInfo": false,
			"bSortable": true,
			"aaSorting": [],
			"bStateSave": true
		});

		//var oTable = $('.tablesorter-log-js').dataTable();
			
		$("#filterinput").keydown(function(event) {
		// Filter on the column (the index) of this element
		var e = (window.event) ? window.event : event;
		if(e.keyCode == 13){
		    //var fnct = $(this).attr('onenter');
		    //eval(fnct);
		    $(th).show();
		    oTable.fnFilterAll(this.value);
		  }
		
		});

		$('#submitFilter').click(function(){
			$(th).show();
			oTable.fnFilterAll($("#filterinput").val());
		});
		$('#clearFilter').click(function(){
			$("#filterinput").val("");
			th.show();
			oTable.fnFilterAll($("#filterinput").val());

		});
	
});