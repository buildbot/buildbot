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

import './BuildView.scss';
import {observer} from "mobx-react";
import {globalRoutes} from "../../plugins/GlobalRoutes";
import {globalSettings} from "../../plugins/GlobalSettings";
import AlertNotification from "../../components/AlertNotification/AlertNotification";
import {useContext, useState} from "react";
import {useTopbarItems} from "../../stores/TopbarStore";
import {StoresContext} from "../../contexts/Stores";
import {Link, useNavigate, useParams} from "react-router-dom";
import {useDataAccessor, useDataApiDynamicQuery, useDataApiQuery} from "../../data/ReactUtils";
import {Builder} from "../../data/classes/Builder";
import {Build} from "../../data/classes/Build";
import {Worker} from "../../data/classes/Worker";
import {useTopbarActions} from "../../stores/TopbarActionsStore";
import {TopbarAction} from "../../components/TopbarActions/TopbarActions";
import {Buildrequest} from "../../data/classes/Buildrequest";
import DataCollection from "../../data/DataCollection";
import {Buildset} from "../../data/classes/Buildset";
import DataPropertiesCollection from "../../data/DataPropertiesCollection";
import {computed} from "mobx";
import DataMultiCollection from "../../data/DataMultiCollection";
import {Change} from "../../data/classes/Change";
import {getPropertyValueOrDefault, parseChangeAuthorNameAndEmail} from "../../util/Properties";
import {results2class} from "../../util/Results";
import {dateFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import BadgeRound from "../../components/BadgeRound/BadgeRound";
import RawData from "../../components/RawData/RawData";
import PropertiesTable from "../../components/PropertiesTable/PropertiesTable";
import ChangesTable from "../../components/ChangesTable/ChangesTable";
import BuildSummary from "../../components/BuildSummary/BuildSummary";
import ChangeUserAvatar from "../../components/ChangeUserAvatar/ChangeUserAvatar";
import {Tab, TabList, TabPanel, Tabs} from "react-tabs";

const buildTopbarActions = (build: Build | null, isRebuilding: boolean, isStopping: boolean,
                            doRebuild: () => void, doStop: () => void) => {
  const actions: TopbarAction[] = [];
  if (build === null) {
    return actions;
  }

  if (build.complete) {
    if (isRebuilding) {
      actions.push({
        caption: "Rebuilding...",
        icon: "spinner fa-spin",
        action: doRebuild
      });
    } else {
      actions.push({
        caption: "Rebuild",
        action: doRebuild
      });
    }
  } else {
    if (isStopping) {
      actions.push({
        caption: "Stopping...",
        icon: "spinner fa-spin",
        action: doStop
      });
    } else {
      actions.push({
        caption: "Stop",
        action: doStop
      });
    }
  }
  return actions;
}

const getResponsibleUsers = (propertiesQuery: DataPropertiesCollection,
                             changesQuery: DataMultiCollection<Build, Change>) => {
  const responsibleUsers: {[name: string]: string | null} = {};
  if (getPropertyValueOrDefault(propertiesQuery.properties, "scheduler", "") === "force") {
    const owner = getPropertyValueOrDefault(propertiesQuery.properties, "owner", "");
    if (owner.match(/^.+\<.+\@.+\..+\>.*$/)) {
      const splitResult = owner.split(new RegExp('<|>'));
      if (splitResult.length === 2) {
        const name = splitResult[0];
        const email = splitResult[1];
        responsibleUsers[name] = email;
      }
    }
  }

  for (const change of changesQuery.getAll()) {
    const [name, email] = parseChangeAuthorNameAndEmail(change.author);
    if (email !== null || !(name in responsibleUsers)) {
      responsibleUsers[name] = email;
    }
  }

  return responsibleUsers;
}

const BuildView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const buildnumber = Number.parseInt(useParams<"buildnumber">().buildnumber ?? "");
  const navigate = useNavigate();

  const stores = useContext(StoresContext);
  const accessor = useDataAccessor([builderid, buildnumber]);

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: builderid.toString()}));
  const builder = buildersQuery.getNthOrNull(0);

  const now = useCurrentTime();

  // get the build plus the previous and next
  // note that this registers to the updates for all the builds for that builder
  // need to see how that scales
  const buildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
        builderid: builderid,
        number__eq: buildnumber}
    }));
  const nextBuildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
      builderid: builderid,
      number__eq: buildnumber + 1}
  }));
  const prevBuildsQuery = useDataApiQuery(() => Build.getAll(accessor, {query: {
      builderid: builderid,
      number__eq: buildnumber - 1}
  }));

  const prevBuild = prevBuildsQuery.getNthOrNull(0);
  const build = buildsQuery.getNthOrNull(0);
  const nextBuild = nextBuildsQuery.getNthOrNull(0);

  const changesQuery = useDataApiQuery(() => buildsQuery.getRelated(b => b.getChanges()));
  const buildrequestsQuery = useDataApiQuery(() => buildsQuery.getRelated(
    b => b.buildrequestid === null
      ? new DataCollection<Buildrequest>()
      : Buildrequest.getAll(accessor, {id: b.buildrequestid.toString()})));
  const buildsetsQuery = useDataApiQuery(() => buildrequestsQuery.getRelated(
    br => Buildset.getAll(accessor, {id: br.buildsetid.toString()})));
  const parentBuildQuery = useDataApiQuery(() => buildsetsQuery.getRelated(
    bs => bs.parent_buildid === null
      ? new DataCollection<Build>()
      : Build.getAll(accessor, {id: bs.parent_buildid.toString()})));
  const propertiesQuery = useDataApiDynamicQuery([build === null],
    () => build === null ? new DataPropertiesCollection() : build.getProperties());

  const workersQuery = useDataApiQuery(() => buildsQuery.getRelated(
    b => Worker.getAll(accessor, {id: b.workerid.toString()})));

  const buildrequest = buildrequestsQuery.getNthOrNull(0);
  const buildset = buildsetsQuery.getNthOrNull(0);
  const parentBuild = parentBuildQuery.getNthOrNull(0);
  const worker = workersQuery.getNthOrNull(0);

  if (buildsQuery.resolved && build === null) {
    navigate(`/builders/${builderid}`);
  }

  const responsibleUsers = computed(() => getResponsibleUsers(propertiesQuery, changesQuery)).get();
  /*
    $window.document.title = $state.current.data.pageTitle({builder: builder['name'], build: buildnumber});
   */

  const lastBuild = nextBuild === null;

  const [isStopping, setIsStopping] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const doRebuild = function() {
    setIsRebuilding(true);

    build!.control('rebuild').then((res) => {
      const brid = Object.values(res.result[1])[0];
      navigate(`/buildrequest/${brid}?redirect_to_build=true`);
    }, (reason) => {
      setIsRebuilding(false);
      setErrorMsg(`Cannot rebuild: ${reason.error.message}`);
    });
  };

  const doStop = function() {
    setIsStopping(true);

    build!.control('stop').then(() => {}, (reason) => {
      setIsStopping(false);
      setErrorMsg(`Cannot Stop: ${reason.error.message}`);
    });
  };

  // FIXME: faviconService.setFavIcon($scope.build);

  useTopbarItems(stores.topbar, [
    {caption: "Builders", route: "/builders"},
    {caption: builder === null ? "..." : builder.name, route: `/builders/${builderid}`},
    {caption: buildnumber.toString(), route: `/builders/${builderid}/builds/${buildnumber}`},
  ]);

  const actions = buildTopbarActions(build, isRebuilding, isStopping, doRebuild, doStop);

  useTopbarActions(stores.topbarActions, actions);

  const renderPager = (build: Build) => {
    const renderPrevLink = () => {
      if (buildnumber > 1 && prevBuild !== null) {
        return (
          <Link to={`/builders/${builderid}/builds/${prevBuild.number}`}>
            <BadgeRound className={results2class(prevBuild, 'pulse')}>←</BadgeRound>
            <span className="nomobile">&nbsp;Previous</span>
          </Link>
        );
      }
      return (
        <span>&larr;
          <span className="nomobile">&nbsp;Previous</span>
        </span>
      );
    }

    const renderCompleteTime = () => {
      if (!build.complete) {
        return null;
      }
      return (
        <li title={dateFormat(build.complete_at!)}>
          Finished {durationFromNowFormat(build.complete_at!, now)}
        </li>
      );
    }

    const renderNextLink = () => {
      if (!lastBuild && nextBuild !== null) {
        return (
          <Link to={`/builders/${builderid}/builds/${nextBuild.number}`}>
            <span className="nomobile">&nbsp;Next</span>
            <BadgeRound className={results2class(nextBuild, 'pulse')}>→</BadgeRound>
          </Link>
        )
      }

      return (
        <span>
          <span className="nomobile">Next&nbsp;</span>
          <span>&rarr;</span>
        </span>
      )
    }

    return (
      <ul className="bb-build-view-pager">
        <li className={"previous " + (build.number === 1 ? " disabled" : "")}>
          {renderPrevLink()}
        </li>
        {renderCompleteTime()}
        <li className={"next" + (lastBuild ? " disabled" : "")}>
          {renderNextLink()}
        </li>
      </ul>
    );
  }

  const workerName = worker === null ? "(loading ...)" : worker.name;
  const renderWorkerInfo = () => {
    if (worker === null) {
      return <></>;
    }

    return Object.entries(worker.workerinfo).map(([name, value]) => (
      <tr key={name}>
        <td className="text-left">{name}</td>
        <td className="text-right">{JSON.stringify(value)}</td>
      </tr>
    ));
  }

  const renderResponsibleUsers = () => {
    return Object.entries(responsibleUsers).map(([author, email]) => (
      <li className="list-group-item">
        <ChangeUserAvatar name={author} email={email} showName={true}/>
      </li>
    ));
  };

  const renderDebugInfo = () => {
    if (buildrequest === null || buildset === null) {
      return <h4>Buildrequest:</h4>;
    }

    return (
      <>
        <h4>
          <Link to={`/buildrequests/${buildrequest.id}`}>Buildrequest:</Link>
        </h4>
        <RawData data={buildrequest.toObject()}/>
        <h4>Buildset:</h4>
        <RawData data={buildset.toObject()}/>
      </>
    );
  }

  return (
    <div className="container">
      <AlertNotification text={errorMsg}/>
      <nav>
        {build !== null ? renderPager(build) : <></>}
      </nav>
      <div className="row">
        <Tabs className="bb-build-view-tabs">
          <TabList>
            <Tab>Build steps</Tab>
            <Tab>Build Properties</Tab>
            <Tab>{`Worker: ${workerName}`}</Tab>
            <Tab>Responsible Users</Tab>
            <Tab>Changes</Tab>
            <Tab>Debug</Tab>
          </TabList>
          <TabPanel>
            { build !== null
              ? <BuildSummary build={build} condensed={false} parentBuild={parentBuild}
                              parentRelationship={buildset === null ? null : buildset.parent_relationship}/>
              : <></>
            }
          </TabPanel>
          <TabPanel>
            <PropertiesTable properties={propertiesQuery.properties}/>
          </TabPanel>
          <TabPanel>
            <table className="table table-hover table-striped table-condensed">
              <tbody>
                <tr>
                  <td className="text-left">name</td>
                  <td className="text-center">{workerName}</td>
                </tr>
                {renderWorkerInfo()}
              </tbody>
            </table>
          </TabPanel>
          <TabPanel>
            <ul className="list-group">
              {renderResponsibleUsers()}
            </ul>
          </TabPanel>
          <TabPanel>
            {build !== null
              ? <ChangesTable changes={changesQuery.getParentCollectionOrEmpty(build.id)}/>
              : <></>
            }
          </TabPanel>
          <TabPanel>
            {renderDebugInfo()}
          </TabPanel>
        </Tabs>
      </div>
    </div>
  );
});

globalRoutes.addRoute({
  route: "builders/:builderid/builds/:buildnumber",
  group: null,
  element: () => <BuildView/>,
});

globalSettings.addGroup({
  name:'Build',
  caption: 'Build page related settings',
  items:[{
      type: 'integer',
      name: 'trigger_step_page_size',
      caption: 'Number of builds to show per page in trigger step',
      defaultValue: 20
    }, {
      type: 'boolean',
      name: 'show_urls',
      caption: 'Always show URLs in step',
      defaultValue: true
    }
  ]});
