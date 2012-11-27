// This file is part of Buildbot.  Buildbot is free software: you can
// redistribute it and/or modify it under the terms of the GNU General Public
// License as published by the Free Software Foundation, version 2.
//
// This program is distributed in the hope that it will be useful, but WITHOUT
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
// FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
// details.
//
// You should have received a copy of the GNU General Public License along with
// this program; if not, write to the Free Software Foundation, Inc., 51
// Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
//
// Copyright Buildbot Team Members

define(["dojo/main", "doh/main", "bb/tests/utils"], function(dojo, doh, utils){
    utils.registerBBTests(doh, "/masters", "masters",[
	function baseConfig(t) {
	    /* look at the dom and see if we have what we are supposed to */
	    utils.assertDomText(t,"inactivemaster",  "#dgrid_0-row-13 td.field-name");
	    utils.assertDomText(t,"master",          "#dgrid_0-row-14 td.field-name");
	    utils.assertDomText(t,"othermaster",     "#dgrid_0-row-15 td.field-name");
	    utils.assertDomText(t,"Yes",             "#dgrid_0-row-15 td.field-active");
	    utils.assertDomText(t,"Yes",              "#dgrid_0-row-14 td.field-active");
	    utils.assertDomText(t,"No",              "#dgrid_0-row-13 td.field-active");
	    /* make sure we at least have a link to the api on the master 14 */
	    var api = utils.getBaseUrl() + "api/v2/master/14";
	    utils.assertDomText(t,api,              "#dgrid_0-row-14 a[href='"+api+"']");
	},
	function stopMaster(t) {
	    var query = "#dgrid_0-row-14 td.field-active";
	    return utils.when(
		utils.playTestScenarioWaitForDomChange(
		    "buildbot.test.scenarios.base.BaseScenario.stopMaster",
		    query),
		function() {
		    utils.assertDomText(t,"No", query);
		});
	}
    ]);
});
