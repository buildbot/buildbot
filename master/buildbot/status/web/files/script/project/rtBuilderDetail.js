define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'handlebars', 'mustache' ,'libs/jquery.form', 'text!templates/builderdetail.handlebars', 'text!templates/builders.mustache', 'timeElements'], function ($, realtimePages, helpers, dt, hb, mustache, form, builderdetail, builders, timeElements) {
    "use strict";
    var rtBuilderDetail;
    var tbsorterCurrentBuildsTable = undefined;
    var builderdetailHandle = Handlebars.compile(builderdetail);

    rtBuilderDetail = {
        init: function () {
            tbsorterCurrentBuildsTable = rtBuilderDetail.dataTableInit($('#rtCurrentBuildsTable'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();

            realtimeFunctions['builderdetail'] = rtBuilderDetail.realtimeFunctionsProcessrtBuilderDetail();
            realtimePages.initRealtime(realtimeFunctions);

            // insert codebase and branch
            var $dtWTop = $('.dataTables_wrapper .top');
            if (window.location.search != '') {
                // Parse the url and insert current codebases and branches
                helpers.codeBaseBranchOverview($('#brancOverViewCont'));
            }            
        },
        realtimeFunctionsProcessrtBuilderDetail: function (data) {
            
            $.get('http://10.45.6.93:8001/json/builders/All%20Branches%20%3E%20Build%20AndroidPlayer/builds?filter=0', function(obj) {
                
                //timeElements.clearTimeObjects(tbsorterCurrentBuildsTable);
                

                var filteredCurrentBuilds = $.grep(obj, function(v) {
                    return v.currentStep != null;
                });
                
                

                tbsorterCurrentBuildsTable.fnClearTable();
                try{
                   tbsorterCurrentBuildsTable.fnAddData(filteredCurrentBuilds);
                    //timeElements.updateTimeObjects();
                }
                catch(err) {
                }
            });

        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null },
                { "mData": null },
                { "mData": null },                
                { "mData": null }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [ 0 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {                                            
                        return builderdetailHandle({showNumber:true,'type':type});
                    }
                },
                {
                    "aTargets": [ 1 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        var runningBuilds = {
                            showRunningBuilds:true,                                                        
                        }
                        var extended = $.extend(runningBuilds, type);
                        console.log(JSON.stringify(extended));
                        return builderdetailHandle(extended);
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        if (oData.currentBuilds != undefined) {
                            helpers.delegateToProgressBar($(nTd).find('.percent-outer-js'));
                        }
                    }                    
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left"
                },                    
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-left"                  
                }
            ];

            return dt.initTable($tableElem, options);
        }
    };

    return rtBuilderDetail;
});
