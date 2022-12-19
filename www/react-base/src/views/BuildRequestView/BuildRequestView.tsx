/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {observer} from "mobx-react";
import {
  useDataAccessor,
  useDataApiQuery,
  useDataApiSinglePropertiesQuery
} from "../../data/ReactUtils";
import {Builder} from "../../data/classes/Builder";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {useNavigate, useParams, useSearchParams} from "react-router-dom";
import {Buildrequest} from "../../data/classes/Buildrequest";
import {Tab, Tabs} from "react-bootstrap";
import RawData from "../../components/RawData/RawData";
import {TopbarAction} from "../../components/TopbarActions/TopbarActions";
import {useContext, useState} from "react";
import {StoresContext} from "../../contexts/Stores";
import {useTopbarActions} from "../../stores/TopbarActionsStore";
import {useTopbarItems} from "../../stores/TopbarStore";
import AlertNotification from "../../components/AlertNotification/AlertNotification";
import {Build} from "../../data/classes/Build";
import BuildSummary from "../../components/BuildSummary/BuildSummary";
import PropertiesTable from "../../components/PropertiesTable/PropertiesTable";
import {Buildset} from "../../data/classes/Buildset";
import TableHeading from "../../components/TableHeading/TableHeading";

const buildTopbarActions = (builder: Builder | null,
                            buildRequest: Buildrequest | null,
                            isCancelling: boolean,
                            cancelBuildRequest: () => void) => {
  if (builder === null || buildRequest === null || buildRequest.complete) {
    return [];
  }

  const actions: TopbarAction[] = [];

  if (isCancelling) {
    actions.push({
      caption: "Cancelling...",
      icon: "spinner fa-spin",
      action: cancelBuildRequest
    });
  } else {
    actions.push({
      caption: "Cancel",
      icon: "stop",
      action: cancelBuildRequest
    });
  }

  return actions;
}

const BuildRequestView = observer(() => {
  const buildRequestId = Number.parseInt(useParams<"buildrequestid">().buildrequestid ?? "");
  const [searchParams] = useSearchParams();
  const redirectToBuild = searchParams.get("redirect_to_build") === "true";

  const accessor = useDataAccessor([buildRequestId]);

  const navigate = useNavigate();

  const stores = useContext(StoresContext);

  const buildRequestsQuery = useDataApiQuery(() =>
    Buildrequest.getAll(accessor, {id: buildRequestId.toString()}));

  const builderQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(buildRequest =>
      Builder.getAll(accessor, {id: buildRequest.builderid.toString()})));

  const buildsetQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(buildRequest =>
      Buildset.getAll(accessor, {id: buildRequest.buildsetid.toString()})));

  const buildsQuery = useDataApiQuery(() =>
      Build.getAll(accessor, {query: {buildrequestid__eq: buildRequestId}}));

  const buildRequest = buildRequestsQuery.getNthOrNull(0);
  const builder = builderQuery.getNthOrNull(0);
  const buildset = buildsetQuery.getNthOrNull(0);

  const buildsetPropertiesQuery = useDataApiSinglePropertiesQuery(buildset,
    bs => bs.getProperties());

  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useTopbarItems(stores.topbar, [
    {caption: "Builders", route: "/builders"},
    {caption: "Build requests", route: null},
    {caption: buildRequestId.toString(), route: `/buildrequests/${buildRequestId}`},
  ]);

  if (buildsQuery.array.length > 0 && redirectToBuild) {
    const build = buildsQuery.getNthOrNull(0);
    navigate(`/builders/${build?.builderid}/builds/${build?.number}`);
  }

  const cancelBuildRequest = () => {
    if (isCancelling) {
      return;
    }
    setIsCancelling(true);
    const dl: Promise<void>[] = [];
    if (buildRequest !== null && !buildRequest.claimed) {
      dl.push(buildRequest.control('cancel'));
    }

    Promise.all(dl).then(() => {
      setIsCancelling(false);
    }, (reason) => {
      setIsCancelling(false);
      setErrorMsg(`Cannot cancel: ${reason.error.message}`);
    })
  };

  const actions = buildTopbarActions(builder, buildRequest, isCancelling, cancelBuildRequest);
  useTopbarActions(stores.topbarActions, actions);

  const buildTabs = buildsQuery.array.map(build => (
    <Tab eventKey={`build-${build.number}`} title={`build ${build.number}`}>
      <BuildSummary build={build} parentBuild={null} parentRelationship={null} condensed={false}/>
    </Tab>
  ));

  const buildRawData = buildsQuery.array.map(build => (
    <>
      <TableHeading>Build {build.number}</TableHeading>
      <RawData data={build.toObject()}/>
    </>
  ));

  return (
    <div className="container">
      <AlertNotification text={errorMsg}/>
      <Tabs id="bb-buildrequest-view-tabs">
        {buildTabs}
        <Tab eventKey="properties" title="properties">
          <PropertiesTable properties={buildsetPropertiesQuery.properties}/>
        </Tab>
        <Tab eventKey="debug" title="Debug">
          <TableHeading>Buildrequest</TableHeading>
          <RawData data={buildRequest !== null ? buildRequest.toObject() : {}}/>
          <TableHeading>Buildset</TableHeading>
          <RawData data={buildset !== null ? buildset.toObject() : {}}/>
          <TableHeading>Builder</TableHeading>
          <RawData data={builder !== null ? builder.toObject() : {}}/>
          {buildRawData}
        </Tab>
      </Tabs>
    </div>
  );
});

globalRoutes.addRoute({
  route: "buildrequests/:buildrequestid",
  group: "builds",
  element: () => <BuildRequestView/>,
});

export default BuildRequestView;
