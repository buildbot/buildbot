/***********************************************
* ng-grid JavaScript Library
* Authors: https://github.com/angular-ui/ng-grid/blob/master/README.md
* License: MIT (http://www.opensource.org/licenses/mit-license.php)
* Compiled At: 02/08/2013 11:45:49
***********************************************/

(function(window) {
'use strict';

/***********************************************
* FILE: ..\src\namespace.js
***********************************************/
if (!window.ng) {
    window.ng = {};
}
window.ngGrid = {};
window.ngGrid.i18n = {};
var ngGridServices = angular.module('ngGrid.services', []);
var ngGridDirectives = angular.module('ngGrid.directives', []);
var ngGridFilters = angular.module('ngGrid.filters', []);
// Declare app level module which depends on filters, and services

/***********************************************
* FILE: ..\src\constants.js
***********************************************/
// the # of rows we want to add to the top and bottom of the rendered grid rows 
var EXCESS_ROWS = 2;
var ASC = "asc";
// constant for sorting direction
var DESC = "desc";
// constant for sorting direction
var NG_FIELD = '_ng_field_';
var NG_DEPTH = '_ng_depth_';
var NG_HIDDEN = '_ng_hidden_';
var NG_COLUMN = '_ng_column_';
var CUSTOM_FILTERS = /CUSTOM_FILTERS/g;
var COL_FIELD = /COL_FIELD/g;
var DISPLAY_CELL_TEMPLATE = /DISPLAY_CELL_TEMPLATE/g;
var EDITABLE_CELL_TEMPLATE = /EDITABLE_CELL_TEMPLATE/g;
var TEMPLATE_REGEXP = /<.+>/;

/***********************************************
* FILE: ..\src\navigation.js
***********************************************/
//set event binding on the grid so we can select using the up/down keys
ng.moveSelectionHandler = function($scope, elm, evt, domUtilityService) {
    if ($scope.selectionService.selectedItems === undefined) {
        return true;
    }
    var charCode = evt.which || evt.keyCode;
	
	var newColumnIndex;
	if($scope.enableCellSelection){
		if(charCode == 9){ //tab key
			evt.preventDefault();
		}
		var focusedOnFirstColumn = $scope.displaySelectionCheckbox && $scope.col.index == 1 || !$scope.displaySelectionCheckbox && $scope.col.index == 0;
		var focusedOnLastColumn = $scope.col.index == $scope.columns.length - 1;	
		newColumnIndex = $scope.col.index;
		if((charCode == 37 || charCode ==  9 && evt.shiftKey) && !focusedOnFirstColumn){
			newColumnIndex -= 1;
		} else if((charCode == 39 || charCode ==  9 && !evt.shiftKey) && !focusedOnLastColumn){			
			newColumnIndex += 1;
		}
	}
		
	var offset = 0;
	if(charCode == 38 || (charCode == 13 && evt.shiftKey)){ //arrow key up or shift enter
		offset = -1;
	} else if(charCode == 40 || charCode == 13){//arrow key down or enter
		offset = 1;
	} else if(charCode != 37 && charCode != 39 && charCode != 9){
		return true;
	}	
	
    var items = $scope.renderedRows;
    var index = items.indexOf($scope.selectionService.lastClickedRow) + offset;
    if (index < 0 || index >= items.length) {
        return true;
    }
	if(charCode != 37 && charCode != 39 && charCode != 9){
		$scope.selectionService.ChangeSelection(items[index], evt);
	}
	
	if($scope.enableCellSelection){ 
		$scope.domAccessProvider.focusCellElement($scope, newColumnIndex);
		$scope.$emit('ngGridEventDigestGridParent');
	} else {	
		if (index >= items.length - EXCESS_ROWS - 1) {
			elm.scrollTop(elm.scrollTop() + ($scope.rowHeight * 2));
		} else if (index <= EXCESS_ROWS) {
			elm.scrollTop(elm.scrollTop() - ($scope.rowHeight * 2));
		}	
		$scope.$emit('ngGridEventDigestGrid');
	}
    return false;
};

/***********************************************
* FILE: ..\src\utils.js
***********************************************/
if (!String.prototype.trim) {
    String.prototype.trim = function() {
        return this.replace(/^\s+|\s+$/g, '');
    };
}
if (!Array.prototype.indexOf) {
    Array.prototype.indexOf = function(elt /*, from*/) {
        var len = this.length >>> 0;
        var from = Number(arguments[1]) || 0;
        from = (from < 0) ? Math.ceil(from) : Math.floor(from);
        if (from < 0) {
            from += len;
        }
        for (; from < len; from++) {
            if (from in this && this[from] === elt) {
                return from;
            }
        }
        return -1;
    };
}
if (!Array.prototype.filter) {
    Array.prototype.filter = function(fun /*, thisp */) {
        "use strict";
        var t = Object(this);
        var len = t.length >>> 0;
        if (typeof fun !== "function") {
            throw new TypeError();
        }
        var res = [];
        var thisp = arguments[1];
        for (var i = 0; i < len; i++) {
            if (i in t) {
                var val = t[i]; // in case fun mutates this
                if (fun.call(thisp, val, i, t)) {
                    res.push(val);
                }
            }
        }
        return res;
    };
}
ng.utils = {
    visualLength: function(node) {
        var elem = document.getElementById('testDataLength');
        if (!elem) {
            elem = document.createElement('SPAN');
            elem.id = "testDataLength";
            elem.style.visibility = "hidden";
            document.body.appendChild(elem);
        }
        $(elem).css('font', $(node).css('font'));
        elem.innerHTML = $(node).text();
        return elem.offsetWidth;
    },
    forIn: function(obj, action) {
        for (var prop in obj) {
            if (obj.hasOwnProperty(prop)) {
                action(obj[prop], prop);
            }
        }
    },
    evalProperty: function(entity, path) {
        var propPath = path.split('.'), i = 0;
        var tempProp = entity[propPath[i]], links = propPath.length;
        i++;
        while (tempProp && i < links) {
            tempProp = tempProp[propPath[i]];
            i++;
        }
        return tempProp;
    },
    endsWith: function(str, suffix) {
        if (!str || !suffix || typeof str != "string") {
            return false;
        }
        return str.indexOf(suffix, str.length - suffix.length) !== -1;
    },
    isNullOrUndefined: function(obj) {
        if (obj === undefined || obj === null) {
            return true;
        }
        return false;
    },
    getElementsByClassName: function(cl) {
        var retnode = [];
        var myclass = new RegExp('\\b' + cl + '\\b');
        var elem = document.getElementsByTagName('*');
        for (var i = 0; i < elem.length; i++) {
            var classes = elem[i].className;
            if (myclass.test(classes)) {
                retnode.push(elem[i]);
            }
        }
        return retnode;
    },
    newId: (function() {
        var seedId = new Date().getTime();
        return function() {
            return seedId += 1;
        };
    })(),
    seti18n: function($scope, language) {
        var $langPack = window.ngGrid.i18n[language];
        for (var label in $langPack) {
            $scope.i18n[label] = $langPack[label];
        }
    },
    
    // we copy KO's ie detection here bc it isn't exported in the min versions of KO
    // Detect IE versions for workarounds (uses IE conditionals, not UA string, for robustness) 
    ieVersion: (function() {
        var version = 3, div = document.createElement('div'), iElems = div.getElementsByTagName('i');
        // Keep constructing conditional HTML blocks until we hit one that resolves to an empty fragment
        while (div.innerHTML = '<!--[if gt IE ' + (++version) + ']><i></i><![endif]-->',
        iElems[0]);
        return version > 4 ? version : undefined;
    })()
};

$.extend(ng.utils, {
    isIe6: (function() {
        return ng.utils.ieVersion === 6;
    })(),
    isIe7: (function() {
        return ng.utils.ieVersion === 7;
    })(),
    isIe: (function() {
        return ng.utils.ieVersion !== undefined;
    })()
});

/***********************************************
* FILE: ..\src\filters\ngColumns.js
***********************************************/
ngGridFilters.filter('ngColumns', function() {
    return function(input) {
        return input.filter(function(col) {
            return !col.isAggCol;
        });
    };
});

/***********************************************
* FILE: ..\src\filters\checkmark.js
***********************************************/
ngGridFilters.filter('checkmark', function() {
    return function(input) {
        return input ? '\u2714' : '\u2718';
    };
});

/***********************************************
* FILE: ..\src\services\SortService.js
***********************************************/
ngGridServices.factory('SortService', function() {
    var sortService = {};
    sortService.colSortFnCache = {}; // cache of sorting functions. Once we create them, we don't want to keep re-doing it
    sortService.dateRE = /^(\d\d?)[\/\.-](\d\d?)[\/\.-]((\d\d)?\d\d)$/; // nasty regex for date parsing
    // this takes an piece of data from the cell and tries to determine its type and what sorting
    // function to use for it
    // @item - the cell data
    sortService.guessSortFn = function(item) {
        var sortFn, // sorting function that is guessed
            itemType, // the typeof item
            dateParts, // for date parsing
            month, // for date parsing
            day; // for date parsing

        if (item === undefined || item === null || item === '') {
            return null;
        }
        itemType = typeof(item);
        //check for numbers and booleans
        switch (itemType) {
            case "number":
                sortFn = sortService.sortNumber;
                break;
            case "boolean":
                sortFn = sortService.sortBool;
                break;
            default:
                sortFn = undefined;
                break;
        }
        //if we found one, return it
        if (sortFn) {
            return sortFn;
        }
        //check if the item is a valid Date
        if (Object.prototype.toString.call(item) === '[object Date]') {
            return sortService.sortDate;
        }
        // if we aren't left with a string, return a basic sorting function...
        if (itemType !== "string") {
            return sortService.basicSort;
        }
        // now lets string check..
        //check if the item data is a valid number
        if (item.match(/^-?[£$¤]?[\d,.]+%?$/)) {
            return sortService.sortNumberStr;
        }
        // check for a date: dd/mm/yyyy or dd/mm/yy
        // can have / or . or - as separator
        // can be mm/dd as well
        dateParts = item.match(sortService.dateRE);
        if (dateParts) {
            // looks like a date
            month = parseInt(dateParts[1], 10);
            day = parseInt(dateParts[2], 10);
            if (month > 12) {
                // definitely dd/mm
                return sortService.sortDDMMStr;
            } else if (day > 12) {
                return sortService.sortMMDDStr;
            } else {
                // looks like a date, but we can't tell which, so assume that it's MM/DD
                return sortService.sortMMDDStr;
            }
        }
        //finally just sort the normal string...
        return sortService.sortAlpha;
    };
    //#region Sorting Functions
    sortService.basicSort = function(a, b) {
        if (a == b) {
            return 0;
        }
        if (a < b) {
            return -1;
        }
        return 1;
    };
    sortService.sortNumber = function(a, b) {
        return a - b;
    };
    sortService.sortNumberStr = function(a, b) {
        var numA, numB, badA = false, badB = false;
        numA = parseFloat(a.replace(/[^0-9.-]/g, ''));
        if (isNaN(numA)) {
            badA = true;
        }
        numB = parseFloat(b.replace(/[^0-9.-]/g, ''));
        if (isNaN(numB)) {
            badB = true;
        }
        // we want bad ones to get pushed to the bottom... which effectively is "greater than"
        if (badA && badB) {
            return 0;
        }
        if (badA) {
            return 1;
        }
        if (badB) {
            return -1;
        }
        return numA - numB;
    };
    sortService.sortAlpha = function(a, b) {
        var strA = a.toLowerCase(),
            strB = b.toLowerCase();
        return strA == strB ? 0 : (strA < strB ? -1 : 1);
    };
    sortService.sortDate = function(a, b) {
        var timeA = a.getTime(),
            timeB = b.getTime();
        return timeA == timeB ? 0 : (timeA < timeB ? -1 : 1);
    };
    sortService.sortBool = function(a, b) {
        if (a && b) {
            return 0;
        }
        if (!a && !b) {
            return 0;
        } else {
            return a ? 1 : -1;
        }
    };
    sortService.sortDDMMStr = function(a, b) {
        var dateA, dateB, mtch, m, d, y;
        mtch = a.match(sortService.dateRE);
        y = mtch[3];
        m = mtch[2];
        d = mtch[1];
        if (m.length == 1) {
            m = '0' + m;
        }
        if (d.length == 1) {
            d = '0' + d;
        }
        dateA = y + m + d;
        mtch = b.match(sortService.dateRE);
        y = mtch[3];
        m = mtch[2];
        d = mtch[1];
        if (m.length == 1) {
            m = '0' + m;
        }
        if (d.length == 1) {
            d = '0' + d;
        }
        dateB = y + m + d;
        if (dateA == dateB) {
            return 0;
        }
        if (dateA < dateB) {
            return -1;
        }
        return 1;
    };
    sortService.sortMMDDStr = function(a, b) {
        var dateA, dateB, mtch, m, d, y;
        mtch = a.match(sortService.dateRE);
        y = mtch[3];
        d = mtch[2];
        m = mtch[1];
        if (m.length == 1) {
            m = '0' + m;
        }
        if (d.length == 1) {
            d = '0' + d;
        }
        dateA = y + m + d;
        mtch = b.match(sortService.dateRE);
        y = mtch[3];
        d = mtch[2];
        m = mtch[1];
        if (m.length == 1) {
            m = '0' + m;
        }
        if (d.length == 1) {
            d = '0' + d;
        }
        dateB = y + m + d;
        if (dateA == dateB) {
            return 0;
        }
        if (dateA < dateB) {
            return -1;
        }
        return 1;
    };
    //#endregion
    // the core sorting logic trigger
    sortService.sortData = function(data /*datasource*/, sortInfo) {
        // first make sure we are even supposed to do work
        if (!data || !sortInfo) {
            return;
        }
        // grab the metadata for the rest of the logic
        var col = sortInfo.column,
            direction = sortInfo.direction,
            sortFn,
            item;

        //see if we already figured out what to use to sort the column
        if (sortService.colSortFnCache[col.field]) {
            sortFn = sortService.colSortFnCache[col.field];
        } else if (col.sortingAlgorithm != undefined) {
            sortFn = col.sortingAlgorithm;
            sortService.colSortFnCache[col.field] = col.sortingAlgorithm;
        } else { // try and guess what sort function to use
            item = data[0];
            if (!item) {
                return;
            }
            sortFn = sortService.guessSortFn(item[col.field]);
            //cache it
            if (sortFn) {
                sortService.colSortFnCache[col.field] = sortFn;
            } else {
                // we assign the alpha sort because anything that is null/undefined will never get passed to
                // the actual sorting function. It will get caught in our null check and returned to be sorted
                // down to the bottom
                sortFn = sortService.sortAlpha;
            }
        }
        //now actually sort the data
        data.sort(function(itemA, itemB) {
            var propA = ng.utils.evalProperty(itemA, col.field);
            var propB = ng.utils.evalProperty(itemB, col.field);
            // we want to allow zero values to be evaluated in the sort function
            if ((!propA && propA != 0) || (!propB && propB != 0)) {
              // we want to force nulls and such to the bottom when we sort... which effectively is "greater than"
              if (!propB && !propA) {
                  return 0;
              } else if (!propA) {
                  return 1;
              } else if (!propB) {
                  return -1;
              }
            }
            //made it this far, we don't have to worry about null & undefined
            if (direction === ASC) {
                return sortFn(propA, propB);
            } else {
                return 0 - sortFn(propA, propB);
            }
        });
        return;
    };
    sortService.Sort = function(sortInfo, data) {
        if (sortService.isSorting) {
            return;
        }
        sortService.isSorting = true;
        sortService.sortData(data, sortInfo);
        sortService.isSorting = false;
    };
    return sortService;
});

/***********************************************
* FILE: ..\src\services\DomUtilityService.js
***********************************************/
ngGridServices.factory('DomUtilityService', function() {
    var domUtilityService = {};
    var getWidths = function() {
        var $testContainer = $('<div></div>');
        $testContainer.appendTo('body');
        // 1. Run all the following measurements on startup!
        //measure Scroll Bars
        $testContainer.height(100).width(100).css("position", "absolute").css("overflow", "scroll");
        $testContainer.append('<div style="height: 400px; width: 400px;"></div>');
        domUtilityService.ScrollH = ($testContainer.height() - $testContainer[0].clientHeight);
        domUtilityService.ScrollW = ($testContainer.width() - $testContainer[0].clientWidth);
        $testContainer.empty();
        //clear styles
        $testContainer.attr('style', '');
        //measure letter sizes using a pretty typical font size and fat font-family
        $testContainer.append('<span style="font-family: Verdana, Helvetica, Sans-Serif; font-size: 14px;"><strong>M</strong></span>');
        domUtilityService.LetterW = $testContainer.children().first().width();
        $testContainer.remove();
    };
    domUtilityService.eventStorage = {};
    domUtilityService.AssignGridContainers = function($scope, rootEl, grid) {
        grid.$root = $(rootEl);
        //Headers
        grid.$topPanel = grid.$root.find(".ngTopPanel");
        grid.$groupPanel = grid.$root.find(".ngGroupPanel");
        grid.$headerContainer = grid.$topPanel.find(".ngHeaderContainer");
        grid.$headerScroller = grid.$topPanel.find(".ngHeaderScroller");
        grid.$headers = grid.$headerScroller.children();
        //Viewport
        grid.$viewport = grid.$root.find(".ngViewport");
        //Canvas
        grid.$canvas = grid.$viewport.find(".ngCanvas");
        //Footers
        grid.$footerPanel = grid.$root.find(".ngFooterPanel");
        domUtilityService.UpdateGridLayout($scope, grid);
    };
    domUtilityService.getRealWidth = function (obj) {
        var width = 0;
        var props = { visibility: "hidden", display: "block" };
        var hiddenParents = obj.parents().andSelf().not(':visible');
        $.swap(hiddenParents[0], props, function () {
            width = obj.outerWidth();
        });
        return width;
    };
    domUtilityService.UpdateGridLayout = function($scope, grid) {
        //catch this so we can return the viewer to their original scroll after the resize!
        var scrollTop = grid.$viewport.scrollTop();
        grid.elementDims.rootMaxW = grid.$root.width();
        if (grid.$root.is(':hidden')) {
            grid.elementDims.rootMaxW = domUtilityService.getRealWidth(grid.$root);
        }
        grid.elementDims.rootMaxH = grid.$root.height();
        //check to see if anything has changed
        grid.refreshDomSizes();
        $scope.adjustScrollTop(scrollTop, true); //ensure that the user stays scrolled where they were
    };
    domUtilityService.numberOfGrids = 0;
    domUtilityService.BuildStyles = function($scope, grid, digest) {
        var rowHeight = grid.config.rowHeight,
            $style = grid.$styleSheet,
            gridId = grid.gridId,
            css,
            cols = $scope.visibleColumns(),
            sumWidth = 0;

        if (!$style) {
            $style = $('#' + gridId);
            if (!$style[0]) {
                $style = $("<style id='" + gridId + "' type='text/css' rel='stylesheet' />").appendTo(grid.$root);
            }
        }
        $style.empty();
        var trw = $scope.totalRowWidth();
        css = "." + gridId + " .ngCanvas { width: " + trw + "px; }" +
            "." + gridId + " .ngRow { width: " + trw + "px; }" +
            "." + gridId + " .ngCanvas { width: " + trw + "px; }" +
            "." + gridId + " .ngHeaderScroller { width: " + (trw + domUtilityService.scrollH + 2) + "px}";
        angular.forEach(cols, function(col, i) {
            css += "." + gridId + " .col" + i + " { width: " + col.width + "px; left: " + sumWidth + "px; right: " + (trw - sumWidth - col.width) + "px; height: " + rowHeight + "px }" +
                "." + gridId + " .colt" + i + " { width: " + col.width + "px; }";
            sumWidth += col.width;
        });
        if (ng.utils.isIe) { // IE
            $style[0].styleSheet.cssText = css;
        } else {
            $style[0].appendChild(document.createTextNode(css));
        }
        grid.$styleSheet = $style;
        if (digest) {
            domUtilityService.digest($scope);
        }
    };
	
	domUtilityService.RebuildGrid = function($scope,grid){
		domUtilityService.UpdateGridLayout($scope, grid);
		if (grid.config.maintainColumnRatios) {
			grid.configureColumnWidths();
		}
		domUtilityService.BuildStyles($scope, grid, true);
	};

    domUtilityService.digest = function($scope) {
        if (!$scope.$$phase) {
            $scope.$digest();
        }
    };
    domUtilityService.ScrollH = 17; // default in IE, Chrome, & most browsers
    domUtilityService.ScrollW = 17; // default in IE, Chrome, & most browsers
    domUtilityService.LetterW = 10;
    getWidths();
    return domUtilityService;
});

/***********************************************
* FILE: ..\src\templates\gridTemplate.html
***********************************************/
ng.gridTemplate = function(){ return '<div class="ngTopPanel" ng-class="{\'ui-widget-header\':jqueryUITheme, \'ui-corner-top\': jqueryUITheme}" ng-style="topPanelStyle()"><div class="ngGroupPanel" ng-show="showGroupPanel()" ng-style="headerStyle()"><div class="ngGroupPanelDescription" ng-show="configGroups.length == 0">{{i18n.ngGroupPanelDescription}}</div><ul ng-show="configGroups.length > 0" class="ngGroupList"><li class="ngGroupItem" ng-repeat="group in configGroups"><span class="ngGroupElement"><span class="ngGroupName">{{group.displayName}}<span ng-click="removeGroup($index)" class="ngRemoveGroup">x</span></span><span ng-hide="$last" class="ngGroupArrow"></span></span></li></ul></div><div class="ngHeaderContainer" ng-style="headerStyle()"><div class="ngHeaderScroller" ng-style="headerScrollerStyle()" ng-header-row></div></div><div class="ngHeaderButton" ng-show="showColumnMenu || showFilter" ng-click="toggleShowMenu()"><div class="ngHeaderButtonArrow" ng-click=""></div></div><div ng-show="showMenu" class="ngColMenu"><div ng-show="showFilter"><input placeholder="{{i18n.ngSearchPlaceHolder}}" type="text" ng-model="filterText"/></div><div ng-show="showColumnMenu"><span class="ngMenuText">{{i18n.ngMenuText}}</span><ul class="ngColList"><li class="ngColListItem" ng-repeat="col in columns | ngColumns"><label><input type="checkbox" class="ngColListCheckbox" ng-model="col.visible"/>{{col.displayName}}</label><a title="Group By" ng-class="col.groupedByClass()" ng-show="col.groupable && col.visible" ng-click="groupBy(col)"></a><span class="ngGroupingNumber" ng-show="col.groupIndex > 0">{{col.groupIndex}}</span></li></ul></div></div></div><div class="ngViewport" unselectable="on" ng-viewport ng-class="{\'ui-widget-content\': jqueryUITheme}" ng-style="viewportStyle()"><div class="ngCanvas" ng-style="canvasStyle()"><div ng-style="rowStyle(row)" ng-repeat="row in renderedRows" ng-click="row.toggleSelected($event)" class="ngRow" ng-class="row.alternatingRowClass()" ng-row></div></div></div><div class="ngFooterPanel" ng-class="{\'ui-widget-content\': jqueryUITheme, \'ui-corner-bottom\': jqueryUITheme}" ng-style="footerStyle()"><div class="ngTotalSelectContainer" ng-show="footerVisible"><div class="ngFooterTotalItems" ng-class="{\'ngNoMultiSelect\': !multiSelect}" ><span class="ngLabel">{{i18n.ngTotalItemsLabel}} {{maxRows()}}</span><span ng-show="filterText.length > 0" class="ngLabel">({{i18n.ngShowingItemsLabel}} {{totalFilteredItemsLength()}})</span></div><div class="ngFooterSelectedItems" ng-show="multiSelect"><span class="ngLabel">{{i18n.ngSelectedItemsLabel}} {{selectedItems.length}}</span></div></div><div class="ngPagerContainer" style="float: right; margin-top: 10px;" ng-show="footerVisible && enablePaging" ng-class="{\'ngNoMultiSelect\': !multiSelect}"><div style="float:left; margin-right: 10px;" class="ngRowCountPicker"><span style="float: left; margin-top: 3px;" class="ngLabel">{{i18n.ngPageSizeLabel}}</span><select style="float: left;height: 27px; width: 100px" ng-model="pagingOptions.pageSize" ><option ng-repeat="size in pagingOptions.pageSizes">{{size}}</option></select></div><div style="float:left; margin-right: 10px; line-height:25px;" class="ngPagerControl" style="float: left; min-width: 135px;"><button class="ngPagerButton" ng-click="pageToFirst()" ng-disabled="cantPageBackward()" title="{{i18n.ngPagerFirstTitle}}"><div class="ngPagerFirstTriangle"><div class="ngPagerFirstBar"></div></div></button><button class="ngPagerButton" ng-click="pageBackward()" ng-disabled="cantPageBackward()" title="{{i18n.ngPagerPrevTitle}}"><div class="ngPagerFirstTriangle ngPagerPrevTriangle"></div></button><input class="ngPagerCurrent" type="text" style="width:50px; height: 24px; margin-top: 1px; padding: 0px 4px;" ng-model="pagingOptions.currentPage"/><button class="ngPagerButton" ng-click="pageForward()" ng-disabled="cantPageForward()" title="{{i18n.ngPagerNextTitle}}"><div class="ngPagerLastTriangle ngPagerNextTriangle"></div></button><button class="ngPagerButton" ng-click="pageToLast()" ng-disabled="cantPageToLast()" title="{{i18n.ngPagerLastTitle}}"><div class="ngPagerLastTriangle"><div class="ngPagerLastBar"></div></div></button></div></div></div>';};

/***********************************************
* FILE: ..\src\templates\rowTemplate.html
***********************************************/
ng.rowTemplate = function(){ return '<div ng-style="{\'cursor\': row.cursor}" ng-repeat="col in visibleColumns()" class="ngCell col{{$index}} {{col.cellClass}}" ng-cell></div>';};

/***********************************************
* FILE: ..\src\templates\cellTemplate.html
***********************************************/
ng.cellTemplate = function(){ return '<div ng-class="\'ngCellText colt\' + $index"><span ng-cell-text>{{COL_FIELD CUSTOM_FILTERS}}</span></div>';};

/***********************************************
* FILE: ..\src\templates\checkboxCellTemplate.html
***********************************************/
ng.checkboxCellTemplate = function(){ return '<div class="ngSelectionCell"><input tabindex="-1" class="ngSelectionCheckbox" type="checkbox" ng-checked="row.selected" /></div>';};

/***********************************************
* FILE: ..\src\templates\checkboxHeaderTemplate.html
***********************************************/
ng.checkboxHeaderTemplate = function(){ return '<input class="ngSelectionHeader" type="checkbox" ng-show="multiSelect" ng-model="allSelected" ng-change="toggleSelectAll(allSelected)"/>';};

/***********************************************
* FILE: ..\src\templates\editableCellTemplate.html
***********************************************/
ng.editableCellTemplate = function(){ return '<input ng-cell-input ng-class="\'colt\' + $index" ng-model="COL_FIELD" />';};

/***********************************************
* FILE: ..\src\templates\focusedCellEditTemplate.html
***********************************************/
ng.focusedCellEditTemplate = function(){ return '<div ng-cell-has-focus><div ng-if="!isFocused">DISPLAY_CELL_TEMPLATE</div><div ng-if="isFocused">EDITABLE_CELL_TEMPLATE</div></div>';};

/***********************************************
* FILE: ..\src\templates\aggregateTemplate.html
***********************************************/
ng.aggregateTemplate = function(){ return '<div ng-click="row.toggleExpand()" ng-style="{\'left\': row.offsetleft}" class="ngAggregate"><span class="ngAggregateText">{{row.label CUSTOM_FILTERS}} ({{row.totalChildren()}} {{AggItemsLabel}})</span><div class="{{row.aggClass()}}"></div></div>';};

/***********************************************
* FILE: ..\src\templates\headerRowTemplate.html
***********************************************/
ng.headerRowTemplate = function(){ return '<div ng-repeat="col in visibleColumns()" class="ngHeaderCell col{{$index}}" ng-header-cell></div>';};

/***********************************************
* FILE: ..\src\templates\headerCellTemplate.html
***********************************************/
ng.headerCellTemplate = function(){ return '<div ng-click="col.sort()" class="ngHeaderSortColumn {{col.headerClass}}" ng-style="{\'cursor\': col.cursor}" ng-class="{ \'ngSorted\': !noSortVisible }"><div class="ngHeaderText colt{{$index}}">{{col.displayName}}</div><div class="ngSortButtonDown" ng-show="col.showSortButtonDown()"></div><div class="ngSortButtonUp" ng-show="col.showSortButtonUp()"></div></div><div ng-show="col.resizable" class="ngHeaderGrip" ng-click="col.gripClick($event)" ng-mousedown="col.gripOnMouseDown($event)"></div>';};

/***********************************************
* FILE: ..\src\classes\aggregate.js
***********************************************/
ng.Aggregate = function (aggEntity, rowFactory, config) {
    var self = this;
    self.rowIndex = 0;
    self.offsetTop = self.rowIndex * config.rowHeight;
    self.entity = aggEntity;
    self.label = aggEntity.gLabel;
    self.field = aggEntity.gField;
    self.depth = aggEntity.gDepth;
    self.parent = aggEntity.parent;
    self.children = aggEntity.children;
    self.aggChildren = aggEntity.aggChildren;
    self.aggIndex = aggEntity.aggIndex;
    self.collapsed = true;
    self.isAggRow = true;
    self.offsetleft = aggEntity.gDepth * 25;
    self.aggLabelFilter = aggEntity.aggLabelFilter;
    self.toggleExpand = function() {
        self.collapsed = self.collapsed ? false : true;
        self.notifyChildren();
    };
    self.setExpand = function(state) {
        self.collapsed = state;
        self.notifyChildren();
    };
    self.notifyChildren = function() {
        angular.forEach(self.aggChildren, function(child) {
            child.entity[NG_HIDDEN] = self.collapsed;
            if (self.collapsed) {
                child.setExpand(self.collapsed);
            }
        });
        angular.forEach(self.children, function(child) {
            child[NG_HIDDEN] = self.collapsed;
        });
        var foundMyself = false;
        angular.forEach(rowFactory.aggCache, function(agg, i) {
            if (foundMyself) {
                var offset = (30 * self.children.length);
                agg.offsetTop = self.collapsed ? agg.offsetTop - offset : agg.offsetTop + offset;
            } else {
                if (i == self.aggIndex) {
                    foundMyself = true;
                }
            }
        });
        rowFactory.renderedChange();
    };
    self.aggClass = function() {
        return self.collapsed ? "ngAggArrowCollapsed" : "ngAggArrowExpanded";
    };
    self.totalChildren = function() {
        if (self.aggChildren.length > 0) {
            var i = 0;
            var recurse = function(cur) {
                if (cur.aggChildren.length > 0) {
                    angular.forEach(cur.aggChildren, function(a) {
                        recurse(a);
                    });
                } else {
                    i += cur.children.length;
                }
            };
            recurse(self);
            return i;
        } else {
            return self.children.length;
        }
    };
};

/***********************************************
* FILE: ..\src\classes\eventProvider.js
***********************************************/
ng.EventProvider = function(grid, $scope, domUtilityService) {
    var self = this;
    // The init method gets called during the ng-grid directive execution.
    self.colToMove = undefined;
    self.groupToMove = undefined;
    self.assignEvents = function() {
        // Here we set the onmousedown event handler to the header container.
        if (grid.config.jqueryUIDraggable) {
            grid.$groupPanel.droppable({
                addClasses: false,
                drop: function(event) {
                    self.onGroupDrop(event);
                }
            });
            $scope.$evalAsync(self.setDraggables);
        } else {
            grid.$groupPanel.on('mousedown', self.onGroupMouseDown).on('dragover', self.dragOver).on('drop', self.onGroupDrop);
            grid.$headerScroller.on('mousedown', self.onHeaderMouseDown).on('dragover', self.dragOver);
            if (grid.config.enableColumnReordering) {
                grid.$headerScroller.on('drop', self.onHeaderDrop);
            }
            if (grid.config.enableRowReordering) {
                grid.$viewport.on('mousedown', self.onRowMouseDown).on('dragover', self.dragOver).on('drop', self.onRowDrop);
            }
        }
        $scope.$watch('columns', self.setDraggables, true);
    };
	self.dragStart = function(evt){		
		//FireFox requires there to be dataTransfer if you want to drag and drop.
		evt.dataTransfer.setData('text', ''); //cannot be empty string
	};
    self.dragOver = function(evt) {
        evt.preventDefault();
    };
    //For JQueryUI
    self.setDraggables = function() {
        if (!grid.config.jqueryUIDraggable) {
			//Fix for FireFox. Instead of using jQuery on('dragstart', function) on find, we have to use addEventListeners for each column.
            var columns = grid.$root.find('.ngHeaderSortColumn'); //have to iterate if using addEventListener
			angular.forEach(columns, function(col){
				col.setAttribute('draggable', 'true');
				//jQuery 'on' function doesn't have  dataTransfer as part of event in handler unless added to event props, which is not recommended
				//See more here: http://api.jquery.com/category/events/event-object/
				if (col.addEventListener) { //IE8 doesn't have drag drop or event listeners
					col.addEventListener('dragstart', self.dragStart);
				}
			});
			if (navigator.userAgent.indexOf("MSIE") != -1){
         		//call native IE dragDrop() to start dragging
				grid.$root.find('.ngHeaderSortColumn').bind('selectstart', function () { 
					this.dragDrop(); 
					return false; 
				});	
      		}
        } else {
            grid.$root.find('.ngHeaderSortColumn').draggable({
                helper: 'clone',
                appendTo: 'body',
                stack: 'div',
                addClasses: false,
                start: function(event) {
                    self.onHeaderMouseDown(event);
                }
            }).droppable({
                drop: function(event) {
                    self.onHeaderDrop(event);
                }
            });
        }
    };
    self.onGroupMouseDown = function(event) {
        var groupItem = $(event.target);
        // Get the scope from the header container
        if (groupItem[0].className != 'ngRemoveGroup') {
            var groupItemScope = angular.element(groupItem).scope();
            if (groupItemScope) {
                // set draggable events
                if (!grid.config.jqueryUIDraggable) {
                    groupItem.attr('draggable', 'true');
					if(this.addEventListener){//IE8 doesn't have drag drop or event listeners
						this.addEventListener('dragstart', self.dragStart); 
					}
					if (navigator.userAgent.indexOf("MSIE") != -1){
						//call native IE dragDrop() to start dragging
						groupItem.bind('selectstart', function () { 
							this.dragDrop(); 
							return false; 
						});	
					}
                }
                // Save the column for later.
                self.groupToMove = { header: groupItem, groupName: groupItemScope.group, index: groupItemScope.$index };
            }
        } else {
            self.groupToMove = undefined;
        }
    };
    self.onGroupDrop = function(event) {
        event.stopPropagation();
        // clear out the colToMove object
        var groupContainer;
        var groupScope;
        if (self.groupToMove) {
            // Get the closest header to where we dropped
            groupContainer = $(event.target).closest('.ngGroupElement'); // Get the scope from the header.
            if (groupContainer.context.className == 'ngGroupPanel') {
                $scope.configGroups.splice(self.groupToMove.index, 1);
                $scope.configGroups.push(self.groupToMove.groupName);
            } else {
                groupScope = angular.element(groupContainer).scope();
                if (groupScope) {
                    // If we have the same column, do nothing.
                    if (self.groupToMove.index != groupScope.$index) {
                        // Splice the columns
                        $scope.configGroups.splice(self.groupToMove.index, 1);
                        $scope.configGroups.splice(groupScope.$index, 0, self.groupToMove.groupName);
                    }
                }
            }
            self.groupToMove = undefined;
            grid.fixGroupIndexes();
        } else if (self.colToMove) {
            if ($scope.configGroups.indexOf(self.colToMove.col) == -1) {
                groupContainer = $(event.target).closest('.ngGroupElement'); // Get the scope from the header.
                if (groupContainer.context.className == 'ngGroupPanel' || groupContainer.context.className == 'ngGroupPanelDescription ng-binding') {
                    $scope.groupBy(self.colToMove.col);
                } else {
                    groupScope = angular.element(groupContainer).scope();
                    if (groupScope) {
                        // Splice the columns
                        $scope.removeGroup(groupScope.$index);
                    }
                }
            }
            self.colToMove = undefined;
        }
        if (!$scope.$$phase) {
            $scope.$apply();
        }
    };
    //Header functions
    self.onHeaderMouseDown = function(event) {
        // Get the closest header container from where we clicked.
        var headerContainer = $(event.target).closest('.ngHeaderSortColumn');
        // Get the scope from the header container
        var headerScope = angular.element(headerContainer).scope();
        if (headerScope) {
            // Save the column for later.
            self.colToMove = { header: headerContainer, col: headerScope.col };
        }
    };
    self.onHeaderDrop = function(event) {
        if (!self.colToMove) {
            return;
        }
        // Get the closest header to where we dropped
        var headerContainer = $(event.target).closest('.ngHeaderSortColumn');
        // Get the scope from the header.
        var headerScope = angular.element(headerContainer).scope();
        if (headerScope) {
            // If we have the same column, do nothing.
            if (self.colToMove.col == headerScope.col) {
                return;
            }
            // Splice the columns
            $scope.columns.splice(self.colToMove.col.index, 1);
            $scope.columns.splice(headerScope.col.index, 0, self.colToMove.col);
            grid.fixColumnIndexes();
            // Finally, rebuild the CSS styles.
            domUtilityService.BuildStyles($scope, grid, true);
            // clear out the colToMove object
            self.colToMove = undefined;
        }
    };
    // Row functions
    self.onRowMouseDown = function(event) {
        // Get the closest row element from where we clicked.
        var targetRow = $(event.target).closest('.ngRow');
        // Get the scope from the row element
        var rowScope = angular.element(targetRow).scope();
        if (rowScope) {
            // set draggable events
            targetRow.attr('draggable', 'true');
            // Save the row for later.
            domUtilityService.eventStorage.rowToMove = { targetRow: targetRow, scope: rowScope };
        }
    };
    self.onRowDrop = function(event) {
        // Get the closest row to where we dropped
        var targetRow = $(event.target).closest('.ngRow');
        // Get the scope from the row element.
        var rowScope = angular.element(targetRow).scope();
        if (rowScope) {
            // If we have the same Row, do nothing.
            var prevRow = domUtilityService.eventStorage.rowToMove;
            if (prevRow.scope.row == rowScope.row) {
                return;
            }
            // Splice the Rows via the actual datasource
            var i = grid.rowCache.indexOf(prevRow.scope.row);
            var j = grid.rowCache.indexOf(rowScope.row);
            grid.rowCache.splice(i, 1);
            grid.rowCache.splice(j, 0, prevRow.scope.row);
            grid.searchProvider.evalFilter();
            // clear out the rowToMove object
            domUtilityService.eventStorage.rowToMove = undefined;
            // if there isn't an apply already in progress lets start one
        }
    };

    self.assignGridEventHandlers = function() {
        //Chrome and firefox both need a tab index so the grid can recieve focus.
        //need to give the grid a tabindex if it doesn't already have one so
        //we'll just give it a tab index of the corresponding gridcache index 
        //that way we'll get the same result every time it is run.
        //configurable within the options.
        if (grid.config.tabIndex === -1) {
            grid.$viewport.attr('tabIndex', domUtilityService.numberOfGrids);
            domUtilityService.numberOfGrids++;
        } else {
            grid.$viewport.attr('tabIndex', grid.config.tabIndex);
        }
        $(window).resize(function() {
            domUtilityService.RebuildGrid($scope,grid);
        });
    };
    // In this example we want to assign grid events.
    self.assignGridEventHandlers();
    self.assignEvents();
};

/***********************************************
* FILE: ..\src\classes\column.js
***********************************************/
ng.Column = function(config, $scope, grid, domUtilityService) {
    var self = this,
        colDef = config.colDef,
        delay = 500,
        clicks = 0,
        timer = null;
    self.width = colDef.width;
    self.groupIndex = 0;
    self.isGroupedBy = false;
    self.minWidth = !colDef.minWidth ? 50 : colDef.minWidth;
    self.maxWidth = !colDef.maxWidth ? 9000 : colDef.maxWidth;
	self.enableFocusedCellEdit = colDef.enableFocusedCellEdit;
    self.headerRowHeight = config.headerRowHeight;
    self.displayName = colDef.displayName || colDef.field;
    self.index = config.index;
    self.isAggCol = config.isAggCol;
    self.cellClass = colDef.cellClass;
    self.cellFilter = colDef.cellFilter ? colDef.cellFilter : "";
    self.field = colDef.field;
    self.aggLabelFilter = colDef.cellFilter || colDef.aggLabelFilter;
    self.visible = ng.utils.isNullOrUndefined(colDef.visible) || colDef.visible;
    self.sortable = false;
    self.resizable = false;
    self.groupable = ng.utils.isNullOrUndefined(colDef.groupable) || colDef.sortable;
    if (config.enableSort) {
        self.sortable = ng.utils.isNullOrUndefined(colDef.sortable) || colDef.sortable;
    }
    if (config.enableResize) {
        self.resizable = ng.utils.isNullOrUndefined(colDef.resizable) || colDef.resizable;
    }
    self.sortDirection = undefined;
    self.sortingAlgorithm = colDef.sortFn;
    self.headerClass = colDef.headerClass;
    self.cursor = self.sortable ? 'pointer' : 'default';
    self.headerCellTemplate = colDef.headerCellTemplate || ng.headerCellTemplate();
    self.cellTemplate = colDef.cellTemplate || ng.cellTemplate().replace(CUSTOM_FILTERS, self.cellFilter ? "|" + self.cellFilter : "");
	if(self.enableFocusedCellEdit) {
	    self.focusedCellEditTemplate = ng.focusedCellEditTemplate();
		self.editableCellTemplate = colDef.editableCellTemplate || ng.editableCellTemplate();
	}
    if (colDef.cellTemplate && !TEMPLATE_REGEXP.test(colDef.cellTemplate)) {
        self.cellTemplate = $.ajax({
            type: "GET",
            url: colDef.cellTemplate,
            async: false
        }).responseText;
    }
	if (self.enableFocusedCellEdit && colDef.editableCellTemplate && !TEMPLATE_REGEXP.test(colDef.cellTemplate)) {
        self.editableCellTemplate = $.ajax({
            type: "GET",
            url: colDef.editableCellTemplate,
            async: false
        }).responseText;
    }
    if (colDef.headerCellTemplate && !TEMPLATE_REGEXP.test(colDef.headerCellTemplate)) {
        self.headerCellTemplate = $.ajax({
            type: "GET",
            url: colDef.headerCellTemplate,
            async: false
        }).responseText;
    }
    self.groupedByClass = function() {
        return self.isGroupedBy ? "ngGroupedByIcon" : "ngGroupIcon";
    };
    self.toggleVisible = function() {
        self.visible = !self.visible;
    };
    self.showSortButtonUp = function() {
        return self.sortable ? self.sortDirection === DESC : self.sortable;
    };
    self.showSortButtonDown = function() {
        return self.sortable ? self.sortDirection === ASC : self.sortable;
    };
    self.noSortVisible = function() {
        return !self.sortDirection;
    };
    self.sort = function() {
        if (!self.sortable) {
            return true; // column sorting is disabled, do nothing
        }
        var dir = self.sortDirection === ASC ? DESC : ASC;
        self.sortDirection = dir;
        config.sortCallback(self);
        return false;
    };
    self.gripClick = function() {
        clicks++; //count clicks
        if (clicks === 1) {
            timer = setTimeout(function() {
                //Here you can add a single click action.
                clicks = 0; //after action performed, reset counter
            }, delay);
        } else {
            clearTimeout(timer); //prevent single-click action
            config.resizeOnDataCallback(self); //perform double-click action
            clicks = 0; //after action performed, reset counter
        }
    };
    self.gripOnMouseDown = function(event) {
        if (event.ctrlKey) {
            self.toggleVisible();
            domUtilityService.BuildStyles($scope, grid);
            return true;
        }
        event.target.parentElement.style.cursor = 'col-resize';
        self.startMousePosition = event.clientX;
        self.origWidth = self.width;
        $(document).mousemove(self.onMouseMove);
        $(document).mouseup(self.gripOnMouseUp);
        return false;
    };
    self.onMouseMove = function(event) {
        var diff = event.clientX - self.startMousePosition;
        var newWidth = diff + self.origWidth;
        self.width = (newWidth < self.minWidth ? self.minWidth : (newWidth > self.maxWidth ? self.maxWidth : newWidth));
        domUtilityService.BuildStyles($scope, grid);
        return false;
    };
    self.gripOnMouseUp = function (event) {
        $(document).off('mousemove', self.onMouseMove);
        $(document).off('mouseup', self.gripOnMouseUp);
        event.target.parentElement.style.cursor = 'default';
        domUtilityService.digest($scope);
        return false;
    };
};

/***********************************************
* FILE: ..\src\classes\dimension.js
***********************************************/
ng.Dimension = function(options) {
    this.outerHeight = null;
    this.outerWidth = null;
    $.extend(this, options);
};

/***********************************************
* FILE: ..\src\classes\footer.js
***********************************************/
ng.Footer = function($scope, grid) {
    $scope.maxRows = function () {
        var ret = Math.max($scope.pagingOptions.totalServerItems, grid.data.length);
        return ret;
    };
    
    $scope.multiSelect = (grid.config.canSelectRows && grid.config.multiSelect);
    $scope.selectedItemCount = grid.selectedItemCount;
    $scope.maxPages = function () {
        return Math.ceil($scope.maxRows() / $scope.pagingOptions.pageSize);
    };

    $scope.pageForward = function() {
        var page = $scope.pagingOptions.currentPage;
        if ($scope.pagingOptions.totalServerItems > 0) {
            $scope.pagingOptions.currentPage = Math.min(page + 1, $scope.maxPages());
        } else {
            $scope.pagingOptions.currentPage++;
        }
    };

    $scope.pageBackward = function() {
        var page = $scope.pagingOptions.currentPage;
        $scope.pagingOptions.currentPage = Math.max(page - 1, 1);
    };

    $scope.pageToFirst = function() {
        $scope.pagingOptions.currentPage = 1;
    };

    $scope.pageToLast = function() {
        var maxPages = $scope.maxPages();
        $scope.pagingOptions.currentPage = maxPages;
    };

    $scope.cantPageForward = function() {
        var curPage = $scope.pagingOptions.currentPage;
        var maxPages = $scope.maxPages();
        if ($scope.pagingOptions.totalServerItems > 0) {
            return !(curPage < maxPages);
        } else {
            return grid.data.length < 1;
        }

    };
    $scope.cantPageToLast = function() {
        if ($scope.pagingOptions.totalServerItems > 0) {
            return $scope.cantPageForward();
        } else {
            return true;
        }
    };
    
    $scope.cantPageBackward = function() {
        var curPage = $scope.pagingOptions.currentPage;
        return !(curPage > 1);
    };
};

/***********************************************
* FILE: ..\src\classes\rowFactory.js
***********************************************/
ng.RowFactory = function(grid, $scope) {
    var self = this;
    // we cache rows when they are built, and then blow the cache away when sorting
    self.aggCache = {};
    self.parentCache = []; // Used for grouping and is cleared each time groups are calulated.
    self.dataChanged = true;
    self.parsedData = [];
    self.rowConfig = {};
    self.selectionService = $scope.selectionService;
    self.rowHeight = 30;
    self.numberOfAggregates = 0;
    self.groupedData = undefined;
    self.rowHeight = grid.config.rowHeight;
    self.rowConfig = {
        canSelectRows: grid.config.canSelectRows,
        rowClasses: grid.config.rowClasses,
        selectedItems: $scope.selectedItems,
        selectWithCheckboxOnly: grid.config.selectWithCheckboxOnly,
        beforeSelectionChangeCallback: grid.config.beforeSelectionChange,
        afterSelectionChangeCallback: grid.config.afterSelectionChange,
        jqueryUITheme: grid.config.jqueryUITheme,
        enableCellSelection: grid.config.enableCellSelection,
        rowHeight: grid.config.rowHeight
    };

    self.renderedRange = new ng.Range(0, grid.minRowsToRender() + EXCESS_ROWS);

    // @entity - the data item
    // @rowIndex - the index of the row
    self.buildEntityRow = function(entity, rowIndex) {
        // build the row
        return new ng.Row(entity, self.rowConfig, self.selectionService, rowIndex);
    };

    self.buildAggregateRow = function(aggEntity, rowIndex) {
        var agg = self.aggCache[aggEntity.aggIndex]; // first check to see if we've already built it 
        if (!agg) {
            // build the row
            agg = new ng.Aggregate(aggEntity, self, self.rowConfig, rowIndex);
            self.aggCache[aggEntity.aggIndex] = agg;
        }
        agg.rowIndex = rowIndex;
        agg.offsetTop = rowIndex * self.rowConfig.rowHeight;
        return agg;
    };
    self.UpdateViewableRange = function(newRange) {
        self.renderedRange = newRange;
        self.renderedChange();
    };
    self.filteredRowsChanged = function() {
        // check for latebound autogenerated columns
        if (grid.lateBoundColumns && grid.filteredRows.length > 0) {
            grid.config.columnDefs = undefined;
            grid.buildColumns();
            grid.lateBoundColumns = false;
        }
        self.dataChanged = true;
        if (grid.config.groups.length > 0) {
            self.getGrouping(grid.config.groups);
        }
        self.UpdateViewableRange(self.renderedRange);
    };

    self.renderedChange = function() {
        if (!self.groupedData || grid.config.groups.length < 1) {
            self.renderedChangeNoGroups();
            grid.refreshDomSizes();
            return;
        }
        self.wasGrouped = true;
        self.parentCache = [];
        var rowArr = [];
        var dataArray = self.parsedData.filter(function(e) {
            return e[NG_HIDDEN] === false;
        }).slice(self.renderedRange.topRow, self.renderedRange.bottomRow);
        angular.forEach(dataArray, function(item, indx) {
            var row;
            if (item.isAggRow) {
                row = self.buildAggregateRow(item, self.renderedRange.topRow + indx);
            } else {
                var i = self.renderedRange.topRow + indx;
                row = grid.rowCache[i];
                row.offsetTop = i * self.rowConfig.rowHeight;
                row.entity = item;
            }
            //add the row to our return array
            rowArr.push(row);
        });
        grid.setRenderedRows(rowArr);
    };

    self.renderedChangeNoGroups = function() {
        var rowArr = grid.filteredRows.slice(self.renderedRange.topRow, self.renderedRange.bottomRow);
        if (self.wasGrouped) {
            angular.forEach(grid.data, function (item, indx) {
                var row = grid.rowCache[indx];
                row.offsetTop = indx * self.rowConfig.rowHeight;
                row.entity = item;
            });
            self.wasGrouped = false;
        }
        grid.setRenderedRows(rowArr);
    };

    //magical recursion. it works. I swear it. I figured it out in the shower one day.
    self.parseGroupData = function(g) {
        if (g.values) {
            angular.forEach(g.values, function(item) {
                // get the last parent in the array because that's where our children want to be
                self.parentCache[self.parentCache.length - 1].children.push(item);
                //add the row to our return array
                self.parsedData.push(item);
            });
        } else {
            for (var prop in g) {
                // exclude the meta properties.
                if (prop == NG_FIELD || prop == NG_DEPTH || prop == NG_COLUMN) {
                    continue;
                } else if (g.hasOwnProperty(prop)) {
                    //build the aggregate row
                    var agg = self.buildAggregateRow({
                        gField: g[NG_FIELD],
                        gLabel: prop,
                        gDepth: g[NG_DEPTH],
                        isAggRow: true,
                        '_ng_hidden_': false,
                        children: [],
                        aggChildren: [],
                        aggIndex: self.numberOfAggregates,
                        aggLabelFilter: g[NG_COLUMN].aggLabelFilter
                    }, 0);
                    self.numberOfAggregates++;
                    //set the aggregate parent to the parent in the array that is one less deep.
                    agg.parent = self.parentCache[agg.depth - 1];
                    // if we have a parent, set the parent to not be collapsed and append the current agg to its children
                    if (agg.parent) {
                        agg.parent.collapsed = false;
                        agg.parent.aggChildren.push(agg);
                    }
                    // add the aggregate row to the parsed data.
                    self.parsedData.push(agg.entity);
                    // the current aggregate now the parent of the current depth
                    self.parentCache[agg.depth] = agg;
                    // dig deeper for more aggregates or children.
                    self.parseGroupData(g[prop]);
                }
            }
        }
    };
    //Shuffle the data into their respective groupings.
    self.getGrouping = function(groups) {
        self.aggCache = [];
        self.numberOfAggregates = 0;
        self.groupedData = {};
        // Here we set the onmousedown event handler to the header container.
        var rows = grid.filteredRows;
        var maxDepth = groups.length;
        var cols = $scope.columns;

        angular.forEach(rows, function (item) {
            var model = item.entity;
            model[NG_HIDDEN] = true;
            var ptr = self.groupedData;
            angular.forEach(groups, function(group, depth) {
                var col = cols.filter(function(c) {
                    return c.field == group;
                })[0];
                var val = ng.utils.evalProperty(model, group);
                val = val ? val.toString() : 'null';
                if (!ptr[val]) {
                    ptr[val] = {};
                }
                if (!ptr[NG_FIELD]) {
                    ptr[NG_FIELD] = group;
                }
                if (!ptr[NG_DEPTH]) {
                    ptr[NG_DEPTH] = depth;
                }
                if (!ptr[NG_COLUMN]) {
                    ptr[NG_COLUMN] = col;
                }
                ptr = ptr[val];
            });
            if (!ptr.values) {
                ptr.values = [];
            }
            ptr.values.push(model);
        });
		//moved out of above loops due to if no data initially, but has initial grouping, columns won't be added
		angular.forEach(groups, function(group, depth) {
			if (!cols[depth].isAggCol && depth <= maxDepth) {
				cols.splice(0, 0, new ng.Column({
					colDef: {
						field: '',
						width: 25,
						sortable: false,
						resizable: false,
						headerCellTemplate: '<div class="ngAggHeader"></div>'
					},
					isAggCol: true,
					headerRowHeight: grid.config.headerRowHeight
				}));
			}
		});
        grid.fixColumnIndexes();
        self.parsedData.length = 0;
        self.parseGroupData(self.groupedData);
    };

    if (grid.config.groups.length > 0 && grid.filteredRows.length > 0) {
        self.getGrouping(grid.config.groups);
    }
};

/***********************************************
* FILE: ..\src\classes\grid.js
***********************************************/
ng.Grid = function($scope, options, sortService, domUtilityService, $filter) {
    var defaults = {
        //Define an aggregate template to customize the rows when grouped. See github wiki for more details.
        aggregateTemplate: undefined,
        
        //Callback for when you want to validate something after selection.
        afterSelectionChange: function() {
        }, 

        /* Callback if you want to inspect something before selection,
        return false if you want to cancel the selection. return true otherwise. 
        If you need to wait for an async call to proceed with selection you can 
        use rowItem.changeSelection(event) method after returning false initially. 
        Note: when shift+ Selecting multiple items in the grid this will only get called
        once and the rowItem will be an array of items that are queued to be selected. */
        beforeSelectionChange: function() {
            return true;
        },

        //To be able to have selectable rows in grid.
        canSelectRows: true, 

        //checkbox templates.
        checkboxCellTemplate: undefined,
        checkboxHeaderTemplate: undefined,
        
        //definitions of columns as an array [], if not defines columns are auto-generated. See github wiki for more details.
        columnDefs: undefined,

        //*Data being displayed in the grid. Each item in the array is mapped to a row being displayed.
        data: [],

        //Row selection check boxes appear as the first column.
        displaySelectionCheckbox: true, 
		
        //Enables cell selection.
        enableCellSelection: false,

        //Enable or disable resizing of columns
        enableColumnResize: true,

        //Enable or disable resizing of columns
        enableColumnReordering: true,

        //Enables the server-side paging feature
        enablePaging: false,

        //Enable drag and drop row reordering. Only works in HTML5 compliant browsers.
        enableRowReordering: true,

        //Enables or disables sorting in grid.
        enableSorting: true,

        /* filterOptions -
        filterText: The text bound to the built-in search box. 
        useExternalFilter: Bypass internal filtering if you want to roll your own filtering mechanism but want to use builtin search box.
        */
        filterOptions: {
            filterText: "",
            useExternalFilter: false
        },
        
        //Defining the height of the footer in pixels.
        footerRowHeight: 55,

        //Show or hide the footer alltogether the footer is enabled by default
        displayFooter: undefined,
        footerVisible: true, // depricated

        //Initial fields to group data by. Array of field names, not displayName.
        groups: [],

        //The height of the header row in pixels.
        headerRowHeight: 30,

        //Define a header row template for further customization. See github wiki for more details.
        headerRowTemplate: undefined,

        /*Enables the use of jquery UI reaggable/droppable plugin. requires jqueryUI to work if enabled. 
        Useful if you want drag + drop but your users insist on crappy browsers. */
        jqueryUIDraggable: false,

        //Enable the use jqueryUIThemes
        jqueryUITheme: false,

        //Prevent unselections when in single selection mode.
        keepLastSelected: true,

        /*Maintains the column widths while resizing. 
        Defaults to true when using *'s or undefined widths. Can be ovverriden by setting to false.*/
        maintainColumnRatios: undefined,

        //Set this to false if you only want one item selected at a time
        multiSelect: true,

        // pagingOptions -

        pagingOptions: {
            // pageSizes: list of available page sizes.
            pageSizes: [250, 500, 1000], 
            //pageSize: currently selected page size. 
            pageSize: 250,
            //totalServerItems: Total items are on the server. 
            totalServerItems: 0,
            //currentPage: the uhm... current page.
            currentPage: 1
        },

        //Array of plugin functions to register in ng-grid
        plugins: [],

        //Row height of rows in grid.
        rowHeight: 30,
        
        //Define a row template to customize output. See github wiki for more details.
        rowTemplate: undefined,
        
        //all of the items selected in the grid. In single select mode there will only be one item in the array.
        selectedItems: [],
        
        //Disable row selections by clicking on the row and only when the checkbox is clicked.
        selectWithCheckboxOnly: false,
        
        /*Enables menu to choose which columns to display and group by. 
        If both showColumnMenu and showFilter are false the menu button will not display.*/
        showColumnMenu: true,

        /*Enables display of the filterbox in the column menu. 
        If both showColumnMenu and showFilter are false the menu button will not display.*/
        showFilter: true,

        //Show the dropzone for drag and drop grouping
        showGroupPanel: false,
        
        /*Define a sortInfo object to specify a default sorting state. 
        You can also observe this variable to utilize server-side sorting (see useExternalSorting).
        Syntax is sortinfo: { field: 'fieldName', direction: 'ASC'/'asc' || 'desc'/'DESC'}*/
        sortInfo: undefined,

        //Set the tab index of the Vieport.
        tabIndex: -1,
        /*Prevents the internal sorting from executing. 
        The sortInfo object will be updated with the sorting information so you can handle sorting (see sortInfo)*/
        useExternalSorting: false,
        
        /*i18n language support. choose from the installed or included languages, en, fr, sp, etc...*/
        i18n: 'en',
        
        //the threshold in rows to force virtualization on
        virtualizationThreshold: 50
    },
        self = this;

    self.maxCanvasHt = 0;
    //self vars
    self.config = $.extend(defaults, window.ngGrid.config, options);
    if (typeof options.columnDefs == "string") {
        self.config.columnDefs = $scope.$eval(options.columnDefs);
    }
    self.rowCache = [];
    self.rowMap = [];
    self.gridId = "ng" + ng.utils.newId();
    self.$root = null; //this is the root element that is passed in with the binding handler
    self.$groupPanel = null;
    self.$topPanel = null;
    self.$headerContainer = null;
    self.$headerScroller = null;
    self.$headers = null;
    self.$viewport = null;
    self.$canvas = null;
    self.rootDim = self.config.gridDim;
    self.sortInfo = self.config.sortInfo;
    self.data = [];
    self.lateBindColumns = false;
    self.filteredRows = [];
    if (typeof self.config.data == "object") {
        self.data = self.config.data; // we cannot watch for updates if you don't pass the string name
    }
    self.lastSortedColumn = undefined;
    self.calcMaxCanvasHeight = function() {
        return (self.config.groups.length > 0) ? (self.rowFactory.parsedData.filter(function(e) {
            return e[NG_HIDDEN] === false;
        }).length * self.config.rowHeight) : (self.filteredRows.length * self.config.rowHeight);
    };
    self.elementDims = {
        scrollW: 0,
        scrollH: 0,
        rowIndexCellW: 25,
        rowSelectedCellW: 25,
        rootMaxW: 0,
        rootMaxH: 0
    };
    //self funcs
    self.setRenderedRows = function(newRows) {
        $scope.renderedRows = newRows;
        self.refreshDomSizes();
        $scope.$emit('ngGridEventRows', newRows);
    };
    self.minRowsToRender = function() {
        var viewportH = $scope.viewportDimHeight() || 1;
        return Math.floor(viewportH / self.config.rowHeight);
    };
    self.refreshDomSizes = function() {
        var dim = new ng.Dimension();
        dim.outerWidth = self.elementDims.rootMaxW;
        dim.outerHeight = self.elementDims.rootMaxH;
        self.rootDim = dim;
        self.maxCanvasHt = self.calcMaxCanvasHeight();
    };
    self.buildColumnDefsFromData = function() {
        if (!self.config.columnDefs) {
            self.config.columnDefs = [];
        }
        if (!self.data || !self.data[0]) {
            self.lateBoundColumns = true;
            return;
        }
        var item;
        item = self.data[0];

        ng.utils.forIn(item, function(prop, propName) {
            self.config.columnDefs.push({
                field: propName
            });
        });
    };
    self.buildColumns = function() {
        var columnDefs = self.config.columnDefs,
            cols = [];
		var indexOffset = self.config.displaySelectionCheckbox ? self.config.groups.length + 1 : self.config.groups.length;       
        if (!columnDefs) {
            self.buildColumnDefsFromData();
            columnDefs = self.config.columnDefs;
        }
        if (self.config.displaySelectionCheckbox) {
            cols.push(new ng.Column({
                colDef: {
                    field: '\u2714',
                    width: self.elementDims.rowSelectedCellW,
                    sortable: false,
                    resizable: false,
                    groupable: false,
                    headerCellTemplate: $scope.checkboxHeaderTemplate,
                    cellTemplate: $scope.checkboxCellTemplate
                },
                index: 0,
                headerRowHeight: self.config.headerRowHeight,
                sortCallback: self.sortData,
                resizeOnDataCallback: self.resizeOnData,
                enableResize: self.config.enableColumnResize,
                enableSort: self.config.enableSorting
            }, $scope, self, domUtilityService, $filter));
        }
        if (columnDefs.length > 0) {
			$scope.configGroups.length = 0;
            angular.forEach(columnDefs, function(colDef, i) {
                i += indexOffset;
                var column = new ng.Column({
                    colDef: colDef,
                    index: i,
                    headerRowHeight: self.config.headerRowHeight,
                    sortCallback: self.sortData,
                    resizeOnDataCallback: self.resizeOnData,
                    enableResize: self.config.enableColumnResize,
                    enableSort: self.config.enableSorting
                }, $scope, self, domUtilityService);
                var indx = self.config.groups.indexOf(colDef.field);
                if (indx != -1) {
					column.isGroupedBy = true;
                    $scope.configGroups.splice(indx, 0, column);
					column.groupIndex = $scope.configGroups.length;
                }
                cols.push(column);
            });
            $scope.columns = cols;
        }
    };
    self.configureColumnWidths = function() {
        var cols = self.config.columnDefs;
        var indexOffset = self.config.displaySelectionCheckbox ? $scope.configGroups.length + 1 : $scope.configGroups.length;
        var numOfCols = cols.length + indexOffset,
            asterisksArray = [],
            percentArray = [],
            asteriskNum = 0,
            totalWidth = 0;
        totalWidth += self.config.displaySelectionCheckbox ? 25 : 0;
        angular.forEach(cols, function(col, i) {
            i += indexOffset;
            var isPercent = false, t = undefined;
            //if width is not defined, set it to a single star
            if (ng.utils.isNullOrUndefined(col.width)) {
                col.width = "*";
            } else { // get column width
                isPercent = isNaN(col.width) ? ng.utils.endsWith(col.width, "%") : false;
                t = isPercent ? col.width : parseInt(col.width, 10);
            }
            // check if it is a number
            if (isNaN(t)) {
                t = col.width;
                // figure out if the width is defined or if we need to calculate it
                if (t == 'auto') { // set it for now until we have data and subscribe when it changes so we can set the width.
                    $scope.columns[i].width = col.minWidth;
                    totalWidth += $scope.columns[i].width;
                    var temp = $scope.columns[i];
                    $scope.$evalAsync(function() {
                        self.resizeOnData(temp, true);
                    });
                    return;
                } else if (t.indexOf("*") != -1) { //  we need to save it until the end to do the calulations on the remaining width.
                    asteriskNum += t.length;
                    col.index = i;
                    asterisksArray.push(col);
                    return;
                } else if (isPercent) { // If the width is a percentage, save it until the very last.
                    col.index = i;
                    percentArray.push(col);
                    return;
                } else { // we can't parse the width so lets throw an error.
                    throw "unable to parse column width, use percentage (\"10%\",\"20%\", etc...) or \"*\" to use remaining width of grid";
                }
            } else {
                totalWidth += $scope.columns[i].width = parseInt(col.width, 10);
            }
        });
        // check if we saved any asterisk columns for calculating later
        if (asterisksArray.length > 0) {
            self.config.maintainColumnRatios === false ? angular.noop() : self.config.maintainColumnRatios = true;
            // get the remaining width
            var remainigWidth = self.rootDim.outerWidth - totalWidth;
            // calculate the weight of each asterisk rounded down
            var asteriskVal = Math.floor(remainigWidth / asteriskNum);
            // set the width of each column based on the number of stars
            angular.forEach(asterisksArray, function(col) {
                var t = col.width.length;
                $scope.columns[col.index].width = asteriskVal * t;
                //check if we are on the last column
                if (col.index + 1 == numOfCols) {
                    var offset = 2; //We're going to remove 2 px so we won't overlflow the viwport by default
                    // are we overflowing?
                    if (self.maxCanvasHt > $scope.viewportDimHeight()) {
                        //compensate for scrollbar
                        offset += domUtilityService.ScrollW;
                    }
                    $scope.columns[col.index].width -= offset;
                }
                totalWidth += $scope.columns[col.index].width;
            });
        }
        // Now we check if we saved any percentage columns for calculating last
        if (percentArray.length > 0) {
            // do the math
            angular.forEach(percentArray, function(col) {
                var t = col.width;
                $scope.columns[col.index].width = Math.floor(self.rootDim.outerWidth * (parseInt(t.slice(0, -1), 10) / 100));
            });
        }
    };
    self.init = function() {
        //factories and services
        $scope.selectionService = new ng.SelectionService(self);
		$scope.domAccessProvider = new ng.DomAccessProvider(domUtilityService);
        self.rowFactory = new ng.RowFactory(self, $scope);
        self.searchProvider = new ng.SearchProvider($scope, self, $filter);
        self.styleProvider = new ng.StyleProvider($scope, self, domUtilityService);
        $scope.$watch('configGroups', function(a) {
			var tempArr = [];
			angular.forEach(a, function(item) {
				tempArr.push(item.field || item);
			});
			self.config.groups = tempArr;
            self.rowFactory.filteredRowsChanged();
			$scope.$emit('ngGridEventGroups', a);
        }, true);
        $scope.$watch('columns', function(a) {
            domUtilityService.BuildStyles($scope, self, true);
            $scope.$emit('ngGridEventColumns', a);
        }, true);
        $scope.$watch(function() {
            return options.i18n;
        }, function(newLang) {
            ng.utils.seti18n($scope, newLang);
        });
        self.maxCanvasHt = self.calcMaxCanvasHeight();
        if (self.config.sortInfo) {
            self.config.sortInfo.column = $scope.columns.filter(function(c) {
                return c.field == self.config.sortInfo.field;
            })[0];
            self.config.sortInfo.column.sortDirection = self.config.sortInfo.direction.toUpperCase();
            self.sortData(self.config.sortInfo.column);
        }
    };
   
    self.resizeOnData = function(col) {
        // we calculate the longest data.
        var longest = col.minWidth;
        var arr = ng.utils.getElementsByClassName('col' + col.index);
        angular.forEach(arr, function(elem, index) {
            var i;
            if (index === 0) {
                var kgHeaderText = $(elem).find('.ngHeaderText');
                i = ng.utils.visualLength(kgHeaderText) + 10; // +10 some margin
            } else {
                var ngCellText = $(elem).find('.ngCellText');
                i = ng.utils.visualLength(ngCellText) + 10; // +10 some margin
            }
            if (i > longest) {
                longest = i;
            }
        });
        col.width = col.longest = Math.min(col.maxWidth, longest + 7); // + 7 px to make it look decent.
        domUtilityService.BuildStyles($scope, self, true);
    };
    self.sortData = function(col) {
        if(self.config.sortInfo) {
            self.config.sortInfo.column    = col;
            self.config.sortInfo.field     = col.field;
            self.config.sortInfo.direction = col.sortDirection;
        } else {
            self.config.sortInfo = {
                column: col,
                field: col.field,
                direction: col.sortDirection
            };
        }
        self.clearSortingData(col);
        if (!self.config.useExternalSorting) {
            var tempData = self.data.slice(0);
            angular.forEach(tempData, function (item, i) {
                item.preSortSelected = self.rowCache[self.rowMap[i]].selected;
                item.preSortIndex = i;
            });
            sortService.Sort(self.config.sortInfo, tempData);
            angular.forEach(tempData, function(item, i) {
                self.rowCache[i].entity = item;
                self.rowCache[i].selected = item.preSortSelected;
                self.rowMap[item.preSortIndex] = i;
                delete item.preSortSelected;
                delete item.preSortIndex;
            });
        }
        self.lastSortedColumn = col;
        self.searchProvider.evalFilter();
        $scope.$emit('ngGridEventSorted', col);
    };
    self.clearSortingData = function(col) {
        if (!col) {
            angular.forEach($scope.columns, function(c) {
                c.sortDirection = "";
            });
        } else if (self.lastSortedColumn && col != self.lastSortedColumn) {
            self.lastSortedColumn.sortDirection = "";
        }
    };
    self.fixColumnIndexes = function() {
        //fix column indexes
        angular.forEach($scope.columns, function(col, i) {
            col.index = i;
        });
    };
    self.fixGroupIndexes = function() {
        angular.forEach($scope.configGroups, function(item, i) {
            item.groupIndex = i + 1;
        });
    };
    //$scope vars
    $scope.elementsNeedMeasuring = true;
    $scope.columns = [];
    $scope.renderedRows = [];
    $scope.headerRow = null;
    $scope.rowHeight = self.config.rowHeight;
    $scope.jqueryUITheme = self.config.jqueryUITheme;
	$scope.displaySelectionCheckbox = self.config.displaySelectionCheckbox;
	$scope.enableCellSelection = self.config.enableCellSelection;
    $scope.footer = null;
    $scope.selectedItems = self.config.selectedItems;
    $scope.multiSelect = self.config.multiSelect;
    $scope.footerVisible = ng.utils.isNullOrUndefined(self.config.displayFooter) ? self.config.footerVisible : self.config.displayFooter;
    $scope.footerRowHeight = $scope.footerVisible ? self.config.footerRowHeight : 0;
    $scope.showColumnMenu = self.config.showColumnMenu;
    $scope.showMenu = false;
    $scope.configGroups = [];
    //Paging
    $scope.enablePaging = self.config.enablePaging;
    $scope.pagingOptions = self.config.pagingOptions;
    //Templates
    // test templates for urls and get the tempaltes via synchronous ajax calls
    var getTemplate = function (key) {
        var t = self.config[key];
        if (t && !TEMPLATE_REGEXP.test(t)) {
            $scope[key] = $.ajax({
                type: "GET",
                url: t,
                async: false
            }).responseText;
        } else if (t) {
            $scope[key] = self.config[key];
        } else {
            $scope[key] = ng[key]();
        }
    };
    getTemplate('rowTemplate');
    getTemplate('aggregateTemplate');
    getTemplate('headerRowTemplate');
    getTemplate('checkboxCellTemplate');
    getTemplate('checkboxHeaderTemplate');
    //i18n support
    $scope.i18n = {};
    ng.utils.seti18n($scope, self.config.i18n);
    $scope.adjustScrollLeft = function(scrollLeft) {
        if (self.$headerContainer) {
            self.$headerContainer.scrollLeft(scrollLeft);
        }
    };
    self.prevScrollTop = 0;
    self.prevScrollIndex = 0;
    $scope.adjustScrollTop = function(scrollTop, force) {
        if (self.prevScrollTop === scrollTop && !force) {
            return;
        }
        if (scrollTop > 0 && self.$viewport[0].scrollHeight - scrollTop <= self.$viewport.outerHeight()) {
            $scope.$emit('ngGridEventScroll');
        }
        var rowIndex = Math.floor(scrollTop / self.config.rowHeight);
	    var newRange;
	    if (self.filteredRows.length > self.config.virtualizationThreshold) {
	        // Have we hit the threshold going down?
	        if (self.prevScrollTop < scrollTop && rowIndex < self.prevScrollIndex + EXCESS_ROWS) {
	            return;
	        }
	        //Have we hit the threshold going up?
	        if (self.prevScrollTop > scrollTop && rowIndex > self.prevScrollIndex - EXCESS_ROWS) {
	            return;
	        }
	        newRange = new ng.Range(Math.max(0, rowIndex - EXCESS_ROWS), rowIndex + self.minRowsToRender() + EXCESS_ROWS);
	    } else {
			newRange = new ng.Range(0, Math.max(self.data.length,self.minRowsToRender() + EXCESS_ROWS));
	    }
	    self.prevScrollTop = scrollTop;
	    self.rowFactory.UpdateViewableRange(newRange);
	    self.prevScrollIndex = rowIndex;
    };

    //scope funcs
    $scope.visibleColumns = function() {
        return $scope.columns.filter(function(col) {
            return col.visible;
        });
    };
    $scope.toggleShowMenu = function() {
        $scope.showMenu = !$scope.showMenu;
    };
    $scope.toggleSelectAll = function(a) {
        $scope.selectionService.toggleSelectAll(a);
    };
    $scope.totalFilteredItemsLength = function() {
        return self.filteredRows.length;
    };
    $scope.showGroupPanel = function() {
        return self.config.showGroupPanel;
    };
    $scope.topPanelHeight = function() {
        return self.config.showGroupPanel === true ? self.config.headerRowHeight * 2 : self.config.headerRowHeight;
    };

    $scope.viewportDimHeight = function() {
        return Math.max(0, self.rootDim.outerHeight - $scope.topPanelHeight() - $scope.footerRowHeight - 2);
    };
    $scope.groupBy = function(col) {
        if (self.data.length < 1 || !col.groupable  || !col.field) {
            return;
        }
        var indx = $scope.configGroups.indexOf(col);
        if (indx == -1) {
            col.isGroupedBy = true;
            $scope.configGroups.push(col);
            col.groupIndex = $scope.configGroups.length;
        } else {
            $scope.removeGroup(indx);
        }
    };
    $scope.removeGroup = function(index) {
        var col = $scope.columns.filter(function(item) {
            return item.groupIndex == (index + 1);
        })[0];
        col.isGroupedBy = false;
        col.groupIndex = 0;
        if ($scope.columns[index].isAggCol) {
            $scope.columns.splice(index, 1);
            $scope.configGroups.splice(index, 1);
            self.fixGroupIndexes();
        }
        if ($scope.configGroups.length === 0) {
            self.fixColumnIndexes();
            domUtilityService.digest($scope);
        }
    };
    $scope.totalRowWidth = function() {
        var totalWidth = 0,
            cols = $scope.visibleColumns();
        angular.forEach(cols, function(col) {
            totalWidth += col.width;
        });
        return totalWidth;
    };
    $scope.headerScrollerDim = function() {
        var viewportH = $scope.viewportDimHeight(),
            maxHeight = self.maxCanvasHt,
            vScrollBarIsOpen = (maxHeight > viewportH),
            newDim = new ng.Dimension();

        newDim.autoFitHeight = true;
        newDim.outerWidth = $scope.totalRowWidth();
        if (vScrollBarIsOpen) {
            newDim.outerWidth += self.elementDims.scrollW;
        } else if ((maxHeight - viewportH) <= self.elementDims.scrollH) { //if the horizontal scroll is open it forces the viewport to be smaller
            newDim.outerWidth += self.elementDims.scrollW;
        }
        return newDim;
    };
    //call init
    self.init();
};

/***********************************************
* FILE: ..\src\classes\range.js
***********************************************/
ng.Range = function(top, bottom) {
    this.topRow = top;
    this.bottomRow = bottom;
};

/***********************************************
* FILE: ..\src\classes\row.js
***********************************************/
ng.Row = function (entity, config, selectionService, rowIndex) {
    var self = this, // constant for the selection property that we add to each data item
        canSelectRows = config.canSelectRows;

    self.jqueryUITheme = config.jqueryUITheme;
    self.rowClasses = config.rowClasses;
    self.entity = entity;
    self.modelIndex = 0;
    self.selectionService = selectionService;
	self.selected = null;
    self.cursor = canSelectRows ? 'pointer' : 'default';
	self.setSelection = function(isSelected) {
		self.selectionService.setSelection(self, isSelected);
		self.selectionService.lastClickedRow = self;
	};
    self.continueSelection = function(event) {
        self.selectionService.ChangeSelection(self, event);
    };
    self.toggleSelected = function(event) {
        if (!canSelectRows && !config.enableCellSelection) {
            return true;
        }
        var element = event.target || event;
        //check and make sure its not the bubbling up of our checked 'click' event 
        if (element.type == "checkbox" && element.parentElement.className != "ngSelectionCell ng-scope") {
            return true;
        }
        if (config.selectWithCheckboxOnly && element.type != "checkbox") {
            return true;
        } else {
            if (self.beforeSelectionChange(self, event)) {
                self.continueSelection(event);
                return self.afterSelectionChange(self, event);
            }
        }
        return false;
    };
    self.rowIndex = rowIndex;
    self.offsetTop = self.rowIndex * config.rowHeight;
    self.rowDisplayIndex = 0;
    self.alternatingRowClass = function () {
        var isEven = (self.rowIndex % 2) === 0;
        var classes = {
            'selected': self.selected,
            'ui-state-default': self.jqueryUITheme && isEven,
            'ui-state-active': self.jqueryUITheme && !isEven,
            'even': isEven,
            'odd': !isEven
        };
        return classes;
    };
    self.beforeSelectionChange = config.beforeSelectionChangeCallback;
    self.afterSelectionChange = config.afterSelectionChangeCallback;

    self.getProperty = function(path) {
        return ng.utils.evalProperty(self.entity, path);
    };
};

/***********************************************
* FILE: ..\src\classes\searchProvider.js
***********************************************/
ng.SearchProvider = function ($scope, grid, $filter) {
    var self = this,
        searchConditions = [];
    self.extFilter = grid.config.filterOptions.useExternalFilter;
    $scope.showFilter = grid.config.showFilter;
    $scope.filterText = '';

    self.fieldMap = {};

    self.evalFilter = function () {
        if (searchConditions.length === 0) {
            grid.filteredRows = grid.rowCache;
        } else {
            grid.filteredRows = grid.rowCache.filter(function (row) {
                var item = row.entity;
                for (var i = 0, len = searchConditions.length; i < len; i++) {
                    var condition = searchConditions[i];
                    //Search entire row
                    var result;
                    if (!condition.column) {
                        for (var prop in item) {
                            if (item.hasOwnProperty(prop)) {
                                var c = self.fieldMap[prop];
                                if (!c) continue;
                                var f = (c && c.cellFilter) ? $filter(c.cellFilter) : null;
                                var pVal = item[prop];
								if(pVal != null){
								    if(typeof f == 'function'){
										var filterRes = f(typeof pVal === 'object' ? evalObject(pVal, c.field) : pVal).toString();
										result = condition.regex.test(filterRes);
									} else {
										result = condition.regex.test(typeof pVal === 'object' ? evalObject(pVal, c.field).toString() : pVal.toString());
								    }
									if (pVal &&  result) {
										return true;
									}
								}
                            }
                        }
                        return false;
                    }
                    //Search by column.
                    var col = self.fieldMap[condition.columnDisplay];
                    if (!col) {
                        return false;
                    }
                    var filter = col.cellFilter ? $filter(col.cellFilter) : null;
                    var value = item[condition.column] || item[col.field.split('.')[0]];                  
					if(value == null) return false;
                    if(typeof filter == 'function'){
						var filterResults = filter(typeof value === 'object' ? evalObject(value, col.field) : value).toString();
						result = condition.regex.test(filterResults);
					} else {
						result = condition.regex.test(typeof value === 'object' ? evalObject(value, col.field).toString() : value.toString());
                    }
					if (!value || !result) {
						return false;
					}				
                }
                return true;
            });
        }
        angular.forEach(grid.filteredRows, function (row, i) {
            row.rowIndex = i;
        });
        grid.rowFactory.filteredRowsChanged();
    };

    //Traversing through the object to find the value that we want. If fail, then return the original object.
    var evalObject = function (obj, columnName) {
        if (typeof obj != 'object' || typeof columnName != 'string')
            return obj;
        var args = columnName.split('.');
        var cObj = obj;
        if (args.length > 1) {
            for (var i = 1, len = args.length; i < len; i++) {
                cObj = cObj[args[i]];
                if (!cObj)
                    return obj;
            }
            return cObj;
        }
        return obj;
    };
    var getRegExp = function (str, modifiers) {
        try {
            return new RegExp(str, modifiers);
        } catch (err) {
            //Escape all RegExp metacharacters.
            return new RegExp(str.replace(/(\^|\$|\(|\)|\<|\>|\[|\]|\{|\}|\\|\||\.|\*|\+|\?)/g, '\\$1'));
        }
    };
    var buildSearchConditions = function (a) {
        //reset.
        searchConditions = [];
        var qStr;
        if (!(qStr = $.trim(a))) {
            return;
        }
        var columnFilters = qStr.split(";");
        angular.forEach(columnFilters, function (filter) {
            var args = filter.split(':');
            if (args.length > 1) {
                var columnName = $.trim(args[0]);
                var columnValue = $.trim(args[1]);
                if (columnName && columnValue) {
                    searchConditions.push({
                        column: columnName,
                        columnDisplay: columnName.replace(/\s+/g, '').toLowerCase(),
                        regex: getRegExp(columnValue, 'i')
                    });
                }
            } else {
                var val = $.trim(args[0]);
                if (val) {
                    searchConditions.push({
                        column: '',
                        regex: getRegExp(val, 'i')
                    });
                }
            }
        });
    };
	$scope.$watch(grid.config.filterOptions.filterText, function(a){
		$scope.filterText = a;
	});
	$scope.$watch('filterText', function(a){
		if(!self.extFilter){
			$scope.$emit('ngGridEventFilter', a);
            buildSearchConditions(a);
            self.evalFilter();
        }
	});
    if (!self.extFilter) {
        $scope.$watch('columns', function (a) {
            angular.forEach(a, function (col) {
				if(col.field)
					self.fieldMap[col.field.split('.')[0]] = col;
				if(col.displayName)
					self.fieldMap[col.displayName.toLowerCase().replace(/\s+/g, '')] = col;
            });
        });
    }
};

/***********************************************
* FILE: ..\src\classes\domAccessProvider.js
***********************************************/
ng.DomAccessProvider = function(domUtilityService) {	
	var self = this, previousColumn;
	self.inputSelection = function(elm){
		var node = elm.nodeName.toLowerCase();
		if(node == 'input' || node == 'textarea' || node == 'select'){
			elm.select();
		}
	};
	
	self.focusCellElement = function($scope, index){	
		var columnIndex = index != undefined ? index : previousColumn;
		if(columnIndex != undefined && $scope.selectionService.lastClickedRow.elm){
			var columns = angular.element($scope.selectionService.lastClickedRow.elm[0].children).filter(function() { return this.nodeType != 8 }); //Remove html comments for IE8
			var nextFocusedCellElement = columns[columnIndex];
			nextFocusedCellElement.children[0].focus();
			self.inputSelection(nextFocusedCellElement);
			previousColumn = columnIndex;
		}
	};
	
	var changeUserSelect = function(elm, value) {
		elm.css({
			'-webkit-touch-callout': value,
			'-webkit-user-select': value,
			'-khtml-user-select': value,
			'-moz-user-select': value == 'none'
				? '-moz-none'
				: value,
			'-ms-user-select': value,
			'user-select': value
		});
	};
	
	self.selectionHandlers = function($scope, elm){
		var doingKeyDown = false;
		elm.bind('keydown', function(evt) {
			if (evt.keyCode == 16) { //shift key
				changeUserSelect(elm, 'none', evt);
				return true;
			} else if (!doingKeyDown) {
				doingKeyDown = true;
				var ret = ng.moveSelectionHandler($scope, elm, evt, domUtilityService);
				doingKeyDown = false;
				return ret;
			}
			return false;
		});
		elm.bind('keyup', function(evt) {
			if (evt.keyCode == 16) { //shift key
				changeUserSelect(elm, 'text', evt);
			}
			return true;
		});
	};
};

/***********************************************
* FILE: ..\src\classes\selectionService.js
***********************************************/
ng.SelectionService = function(grid) {
    var self = this;
    self.multi = grid.config.multiSelect;
    self.selectedItems = grid.config.selectedItems;
    self.selectedIndex = grid.config.selectedIndex;
    self.lastClickedRow = undefined;
    self.ignoreSelectedItemChanges = false; // flag to prevent circular event loops keeping single-select var in sync

    // function to manage the selection action of a data item (entity)
    self.ChangeSelection = function(rowItem, evt) {
        if (evt && evt.shiftKey && !evt.keyCode && self.multi && grid.config.canSelectRows) {
            if (self.lastClickedRow) {
                var thisIndx = grid.filteredRows.indexOf(rowItem);
                var prevIndx = grid.filteredRows.indexOf(self.lastClickedRow);
                self.lastClickedRow = rowItem;
                if (thisIndx == prevIndx) {
                    return false;
                }
                if (thisIndx < prevIndx) {
                    thisIndx = thisIndx ^ prevIndx;
                    prevIndx = thisIndx ^ prevIndx;
                    thisIndx = thisIndx ^ prevIndx;
					thisIndx--;
                } else {
					prevIndx++;
				}
                var rows = [];
                for (; prevIndx <= thisIndx; prevIndx++) {
                    rows.push(grid.filteredRows[prevIndx]);
                }
                if (rows[rows.length - 1].beforeSelectionChange(rows, evt)) {
                    angular.forEach(rows, function(ri) {
						var selectionState = ri.selected;
                        ri.selected = !selectionState;
						var index = self.selectedItems.indexOf(ri.entity);
                        if (index === -1) {
                            self.selectedItems.push(ri.entity);
                        } else {
							self.selectedItems.splice(index,1);
						}
                    });
                    rows[rows.length - 1].afterSelectionChange(rows, evt);
                }
                return true;
            }
        } else if (!self.multi) {
            if (self.lastClickedRow) {
				self.setSelection(self.lastClickedRow, false);
				if(self.lastClickedRow == rowItem){ 
					self.lastClickedRow = undefined; //deselect row
					return true;
				}
            }
		    self.setSelection(rowItem, grid.config.keepLastSelected ? true : !rowItem.selected);
        } else if (!evt.keyCode) {
            self.setSelection(rowItem, !rowItem.selected);
        }
		self.lastClickedRow = rowItem;
        return true;
    };

    // just call this func and hand it the rowItem you want to select (or de-select)    
    self.setSelection = function(rowItem, isSelected) {
		if(grid.config.canSelectRows){
			rowItem.selected = isSelected;
			if (!isSelected) {
				var indx = self.selectedItems.indexOf(rowItem.entity);
				if(indx != -1){
					self.selectedItems.splice(indx, 1);
				}
			} else {
				if (self.selectedItems.indexOf(rowItem.entity) === -1) {
					if(!self.multi && self.selectedItems.length > 0){
						self.toggleSelectAll(false);
						rowItem.selected = isSelected;
					}
					self.selectedItems.push(rowItem.entity);
				}
			}
		}
    };
    // @return - boolean indicating if all items are selected or not
    // @val - boolean indicating whether to select all/de-select all
    self.toggleSelectAll = function (checkAll) {
        if (grid.config.beforeSelectionChange(grid.rowCache)) {
            var selectedlength = self.selectedItems.length;
            if (selectedlength > 0) {
                self.selectedItems.splice(0, selectedlength);
            }
            angular.forEach(grid.filteredRows, function (row) {
                row.selected = checkAll;
                if (checkAll) {
                    self.selectedItems.push(row.entity);
                }
            });
            grid.config.afterSelectionChange(grid.rowCache);
        }
    };
};

/***********************************************
* FILE: ..\src\classes\styleProvider.js
***********************************************/
ng.StyleProvider = function($scope, grid, domUtilityService) {
    $scope.headerCellStyle = function(col) {
        return { "height": col.headerRowHeight + "px" };
    };
    $scope.rowStyle = function(row) {
        return { "top": row.offsetTop + "px", "height": $scope.rowHeight + "px" };
    };
    $scope.canvasStyle = function() {
        return { "height": grid.maxCanvasHt.toString() + "px" };
    };
    $scope.headerScrollerStyle = function() {
        return { "height": grid.config.headerRowHeight + "px" };
    };
    $scope.topPanelStyle = function() {
        return { "width": grid.rootDim.outerWidth + "px", "height": $scope.topPanelHeight() + "px" };
    };
    $scope.headerStyle = function() {
        return { "width": (grid.rootDim.outerWidth - domUtilityService.ScrollW) + "px", "height": grid.config.headerRowHeight + "px" };
    };
    $scope.viewportStyle = function() {
        return { "width": grid.rootDim.outerWidth + "px", "height": $scope.viewportDimHeight() + "px" };
    };
    $scope.footerStyle = function() {
        return { "width": grid.rootDim.outerWidth + "px", "height": $scope.footerRowHeight + "px" };
    };
};

/***********************************************
* FILE: ..\src\directives\ng-grid.js
***********************************************/
ngGridDirectives.directive('ngGrid', ['$compile', '$filter', 'SortService', 'DomUtilityService', function($compile, $filter, sortService, domUtilityService) {
    var ngGrid = {
        scope: true,
        compile: function() {
            return {
                pre: function($scope, iElement, iAttrs) {
                    var $element = $(iElement);
                    var options = $scope.$eval(iAttrs.ngGrid);
                    options.gridDim = new ng.Dimension({ outerHeight: $($element).height(), outerWidth: $($element).width() });
                    var grid = new ng.Grid($scope, options, sortService, domUtilityService, $filter);

                    // if columndefs are a string of a property ont he scope watch for changes and rebuild columns.
                    if (typeof options.columnDefs == "string") {
                        $scope.$parent.$watch(options.columnDefs, function(a) {
                            $scope.columns = [];
                            grid.config.columnDefs = a;
                            grid.buildColumns();
                            grid.eventProvider.assignEvents();
							domUtilityService.RebuildGrid($scope,grid);
                        });
                    } else {
						grid.buildColumns();
					}
					
                    // if it is a string we can watch for data changes. otherwise you won't be able to update the grid data
                    if (typeof options.data == "string") {
                        $scope.$parent.$watch(options.data, function (a) {
                            // make a temporary copy of the data
                            grid.data = $.extend(true, [], a);
                            var diff = grid.data.length - grid.rowCache.length;
                            if (diff < 0) {
                                grid.rowCache.length = grid.rowMap.length = grid.data.length;
                            } else {
                                for (var i = grid.rowCache.length; i < grid.data.length; i++) {
                                    grid.rowCache[i] = grid.rowFactory.buildEntityRow(grid.data[i], i);
                                }
                            }
                            angular.forEach(grid.data, function (item, j) {
                                if (grid.rowCache[j]) {
                                    if (!angular.equals(grid.rowCache[j].entity, item)) {
                                        grid.rowCache[j].entity = item;
                                        grid.rowCache[j].modelIndex = j;
                                        grid.rowCache[j].setSelection(false);
                                    }
                                    grid.rowMap[j] = j;
                                }
                            });
                            grid.searchProvider.evalFilter();
                            grid.configureColumnWidths();
                            grid.refreshDomSizes();
                            if (grid.config.sortInfo) {
                                if (!grid.config.sortInfo.column) {
                                    grid.config.sortInfo.column = $scope.columns.filter(function(c) {
                                        return c.field == grid.config.sortInfo.field;
                                    })[0];
                                    if (!grid.config.sortInfo.column) {
                                        return;
                                    }
                                }
                                grid.config.sortInfo.column.sortDirection = grid.config.sortInfo.direction.toLowerCase();
                                grid.sortData(grid.config.sortInfo.column);
                            }
                            $scope.$emit("ngGridEventData");
                        }, true);
                    }
					
                    grid.footerController = new ng.Footer($scope, grid);
                    //set the right styling on the container
                    iElement.addClass("ngGrid").addClass(grid.gridId.toString());
                    if (options.jqueryUITheme) {
                        iElement.addClass('ui-widget');
                    }
                    iElement.append($compile(ng.gridTemplate())($scope)); // make sure that if any of these change, we re-fire the calc logic
                    //walk the element's graph and the correct properties on the grid
                    domUtilityService.AssignGridContainers($scope, iElement, grid);
                    //now use the manager to assign the event handlers
                    grid.eventProvider = new ng.EventProvider(grid, $scope, domUtilityService);
                    //initialize plugins.
                    angular.forEach(options.plugins, function (p) {
                        if (typeof p === 'function') {
                            p.call(this, []).init($scope.$new(), grid, { SortService: sortService, DomUtilityService: domUtilityService });
                        } else {
                            p.init($scope.$new(), grid, { SortService: sortService, DomUtilityService: domUtilityService });
                        }
                    });
                    // method for user to select a specific row programatically
                    options.selectRow = function (rowIndex, state) {
                        if (grid.rowCache[rowIndex]) {
                            grid.rowCache[rowIndex].setSelection(state ? true : false);
                        }
                    };
                    // method for user to select the row by data item programatically
                    options.selectItem = function (itemIndex, state) {
                        options.selectRow(grid.rowMap[itemIndex], state);
                    };					
					
					$scope.$on('ngGridEventDigestGrid', function(){
						domUtilityService.digest($scope.$parent);
					});			
					
					$scope.$on('ngGridEventDigestGridParent', function(){
						domUtilityService.digest($scope.$parent);
					});

                    return null;
                }
            };
        }
    };
    return ngGrid;
}]);

/***********************************************
* FILE: ..\src\directives\ng-row.js
***********************************************/
ngGridDirectives.directive('ngRow', ['$compile', 'DomUtilityService', function($compile, domUtilityService) {
    var ngRow = {
        scope: false,
        compile: function() {
            return {
                pre: function($scope, iElement) {
					$scope.row.elm = iElement;
                    if ($scope.row.isAggRow) {
                        var html = $scope.aggregateTemplate;
                        if ($scope.row.aggLabelFilter) {
                            html = html.replace(CUSTOM_FILTERS, '| ' + $scope.row.aggLabelFilter);
                        } else {
                            html = html.replace(CUSTOM_FILTERS, "");
                        }
                        iElement.append($compile(html)($scope));
                    } else {
                        iElement.append($compile($scope.rowTemplate)($scope));
                    }
					$scope.$on('ngGridEventDigestRow', function(){
						domUtilityService.digest($scope);
					});
                }
            };
        }
    };
    return ngRow;
}]);

/***********************************************
* FILE: ..\src\directives\ng-cell.js
***********************************************/
ngGridDirectives.directive('ngCell', ['$compile', 'DomUtilityService', function($compile, domUtilityService) {
    var ngCell = {
        scope: false,
        compile: function() {
            return {
                pre: function($scope, iElement) {
					var html;
					if($scope.col.enableFocusedCellEdit){
						html =  $scope.col.focusedCellEditTemplate;
						html = html.replace(DISPLAY_CELL_TEMPLATE, $scope.col.cellTemplate);
						html = html.replace(EDITABLE_CELL_TEMPLATE, $scope.col.editableCellTemplate);
					} else {
						html = $scope.col.cellTemplate;
					}
                    html = html.replace(COL_FIELD, 'row.entity.' + $scope.col.field);
					var cellElement = $compile(html)($scope);
					if($scope.enableCellSelection && cellElement[0].className.indexOf('ngSelectionCell') == -1){
						cellElement[0].setAttribute('tabindex', 0);
						cellElement.addClass('ngCellElement');
					}
                    iElement.append(cellElement);
                },
				post: function($scope, iElement){	
					if($scope.enableCellSelection){
						$scope.domAccessProvider.selectionHandlers($scope, iElement);
					}
					
					$scope.$on('ngGridEventDigestCell', function(){
						domUtilityService.digest($scope);
					});
				}
            };
        }
    };
    return ngCell;
}]);

/***********************************************
* FILE: ..\src\directives\ng-header-row.js
***********************************************/
ngGridDirectives.directive('ngHeaderRow', ['$compile', function($compile) {
    var ngHeaderRow = {
        scope: false,
        compile: function() {
            return {
                pre: function($scope, iElement) {
                    if (iElement.children().length === 0) {
                       iElement.append($compile($scope.headerRowTemplate)($scope));
                    }
                }
            };
        }
    };
    return ngHeaderRow;
}]);

/***********************************************
* FILE: ..\src\directives\ng-header-cell.js
***********************************************/
ngGridDirectives.directive('ngHeaderCell', ['$compile', function($compile) {
    var ngHeaderCell = {
        scope: false,
        compile: function() {
            return {
                pre: function($scope, iElement) {
                    iElement.append($compile($scope.col.headerCellTemplate)($scope));
                }
            };
        }
    };
    return ngHeaderCell;
}]);

/***********************************************
* FILE: ..\src\directives\ng-viewport.js
***********************************************/
ngGridDirectives.directive('ngViewport', [function () {
    return function($scope, elm) {
		var isMouseWheelActive = false;
		elm.bind('scroll', function (evt) {
			$scope.$apply(function(){
		        var scrollLeft = evt.target.scrollLeft,
		            scrollTop = evt.target.scrollTop;
		        $scope.adjustScrollLeft(scrollLeft);
		        $scope.adjustScrollTop(scrollTop);
			});
			if ($scope.enableCellSelection && (document.activeElement == null || document.activeElement.className.indexOf('ngViewport') == -1) && !isMouseWheelActive) {
				$scope.domAccessProvider.focusCellElement($scope);
			}
			isMouseWheelActive = false;
			return true;
		});
		elm.bind("mousewheel DOMMouseScroll", function(evt) {
			isMouseWheelActive = true;
			return true;
		});
		if(!$scope.enableCellSelection){
			$scope.domAccessProvider.selectionHandlers($scope, elm);
		}
    };
}]);

/***********************************************
* FILE: ..\src\directives\ng-cell-text.js
***********************************************/
ngGridDirectives.directive('ngCellText',
  function () {
      return function(scope, elm) {
          elm.bind('mouseover', function(evt) {
              evt.preventDefault();
              elm.css({
                  'cursor': 'text'
              });
          });
          elm.bind('mouseleave', function(evt) {
              evt.preventDefault();
              elm.css({
                  'cursor': 'default'
              });
          });
      };
  });

/***********************************************
* FILE: ..\src\directives\ng-cell-has-focus.js
***********************************************/
ngGridDirectives.directive('ngCellHasFocus', ['DomUtilityService',
	function (domUtilityService) {
		var focusOnInputElement = function($scope, elm){
			$scope.isFocused = true;
			domUtilityService.digest($scope);	
			var elementWithoutComments = angular.element(elm[0].children).filter(function() { return this.nodeType != 8 });//Remove html comments for IE8
			var inputElement = angular.element(elementWithoutComments[0].children[0]); 
			if(inputElement.length > 0){
				angular.element(inputElement).focus();
				$scope.domAccessProvider.inputSelection(inputElement[0]);
				angular.element(inputElement).bind('blur', function(evt){	
					$scope.isFocused = false;	
					domUtilityService.digest($scope);
					return true;
				});	
			}
		};
		return function($scope, elm) {
			$scope.isFocused = false;
			elm.bind('mousedown', function(evt){
				evt.preventDefault();
				$scope.$parent.row.toggleSelected(evt);
				domUtilityService.digest($scope.$parent.$parent);
				focusOnInputElement($scope, elm);
				return true;
			});			
			elm.bind('focus', function(evt){
				focusOnInputElement($scope, elm);
				return true;
			});
		};
	}]);

/***********************************************
* FILE: ..\src\directives\ng-cell-input.js
***********************************************/
ngGridDirectives.directive('ngCellInput',
	function () {
		return function($scope, elm) {
			elm.bind('keydown', function(evt){
				switch(evt.keyCode){
					case 37:
					case 38:
					case 39:
					case 40:
						evt.stopPropagation();
						break;
					default:
						break;
				}
				return true;
			});
		};
	});

/***********************************************
* FILE: ..\src\directives\ng-if.js
***********************************************/
/*
 * Defines the ui-if tag. This removes/adds an element from the dom depending on a condition
 * Originally created by @tigbro, for the @jquery-mobile-angular-adapter
 * https://github.com/tigbro/jquery-mobile-angular-adapter
 */
ngGridDirectives.directive('ngIf', [function () {
  return {
    transclude: 'element',
    priority: 1000,
    terminal: true,
    restrict: 'A',
    compile: function (element, attr, transclude) {
      return function (scope, element, attr) {

        var childElement;
        var childScope;
 
        scope.$watch(attr['ngIf'], function (newValue) {
          if (childElement) {
            childElement.remove();
            childElement = undefined;
          }
          if (childScope) {
            childScope.$destroy();
            childScope = undefined;
          }

          if (newValue) {
            childScope = scope.$new();
            transclude(childScope, function (clone) {
              childElement = clone;
              element.after(clone);
            });
          }
        });
      };
    }
  };
}]);

/***********************************************
* FILE: ..\src\init.js
***********************************************/
// initialization of services into the main module
angular.module('ngGrid', ['ngGrid.services', 'ngGrid.directives', 'ngGrid.filters']);

/***********************************************
* LANGUAGE: en.js
***********************************************/
window.ngGrid.i18n['en'] = {
    ngAggregateLabel: 'items',
    ngGroupPanelDescription: 'Drag a column header here and drop it to group by that column.',
    ngSearchPlaceHolder: 'Search...',
    ngMenuText: 'Choose Columns:',
    ngShowingItemsLabel: 'Showing Items:',
    ngTotalItemsLabel: 'Total Items:',
    ngSelectedItemsLabel: 'Selected Items:',
    ngPageSizeLabel: 'Page Size:',
    ngPagerFirstTitle: 'First Page',
    ngPagerNextTitle: 'Next Page',
    ngPagerPrevTitle: 'Previous Page',
    ngPagerLastTitle: 'Last Page'
};
}(window));
