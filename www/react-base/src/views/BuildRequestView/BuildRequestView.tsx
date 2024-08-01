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
import {FaSpinner, FaStop} from "react-icons/fa";
import {Fragment, useEffect, useState} from "react";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Builder,
  Buildrequest,
  Buildset,
  DataCollection,
  Project,
  useDataAccessor,
  useDataApiQuery,
  useDataApiSinglePropertiesQuery
} from "buildbot-data-js";
import {useNavigate, useParams, useSearchParams} from "react-router-dom";
import {Tab, Tabs} from "react-bootstrap";
import {TopbarAction, TopbarItem, useTopbarActions, useTopbarItems} from "buildbot-ui";
import {RawData} from "../../components/RawData/RawData";
import {AlertNotification} from "../../components/AlertNotification/AlertNotification";
import {BuildSummary} from "../../components/BuildSummary/BuildSummary";
import {PropertiesTable} from "../../components/PropertiesTable/PropertiesTable";
import {TableHeading} from "../../components/TableHeading/TableHeading";
import {buildTopbarItemsForBuilder} from "../../util/TopbarUtils";

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
      icon: <FaSpinner/>,
      action: cancelBuildRequest
    });
  } else {
    actions.push({
      caption: "Cancel",
      icon: <FaStop/>,
      action: cancelBuildRequest
    });
  }

  return actions;
}

export const BuildRequestView = observer(() => {
  const buildRequestId = Number.parseInt(useParams<"buildrequestid">().buildrequestid ?? "");
  const [searchParams] = useSearchParams();
  const redirectToBuild = searchParams.get("redirect_to_build") === "true";

  const accessor = useDataAccessor([buildRequestId]);

  const navigate = useNavigate();

  const buildRequestsQuery = useDataApiQuery(() =>
    Buildrequest.getAll(accessor, {id: buildRequestId.toString()}));

  const builderQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(buildRequest =>
      Builder.getAll(accessor, {id: buildRequest.builderid.toString()})));

  const projectsQuery = useDataApiQuery(() => builderQuery.getRelated(builder => {
    return builder.projectid === null
      ? new DataCollection<Project>()
      : Project.getAll(accessor, {id: builder.projectid.toString()})
  }));

  const buildsetQuery = useDataApiQuery(() =>
    buildRequestsQuery.getRelated(buildRequest =>
      Buildset.getAll(accessor, {id: buildRequest.buildsetid.toString()})));

  const buildsQuery = useDataApiQuery(() =>
      Build.getAll(accessor, {query: {buildrequestid__eq: buildRequestId}}));

  const buildRequest = buildRequestsQuery.getNthOrNull(0);
  const builder = builderQuery.getNthOrNull(0);
  const project = projectsQuery.getNthOrNull(0);
  const buildset = buildsetQuery.getNthOrNull(0);

  const buildsetPropertiesQuery = useDataApiSinglePropertiesQuery(buildset, [],
    bs => bs.getProperties());

  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useTopbarItems(buildTopbarItemsForBuilder(builder, project, [
    {caption: "Build requests", route: null},
    {caption: buildRequestId.toString(), route: `/buildrequests/${buildRequestId}`},
  ]));

  useEffect(() => {
    if (buildsQuery.array.length > 0 && redirectToBuild) {
      const build = buildsQuery.getNthOrNull(0);
      navigate(`/builders/${build?.builderid}/builds/${build?.number}`);
    }
  }, [buildsQuery.array.length > 0]);

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
  useTopbarActions(actions);

  const buildTabs = buildsQuery.array.map(build => (
    <Tab key={build.id} eventKey={`build-${build.number}`} title={`build ${build.number}`}>
      <BuildSummary build={build} parentBuild={null} parentRelationship={null} condensed={false}/>
    </Tab>
  ));

  const buildRawData = buildsQuery.array.map(build => (
    <Fragment key={build.id}>
      <TableHeading>Build {build.number}</TableHeading>
      <RawData data={build.toObject()}/>
    </Fragment>
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

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "buildrequests/:buildrequestid",
    group: "builds",
    element: () => <BuildRequestView/>,
  });
});
