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
import {
  findOrNull,
  useDataAccessor,
  useDataApiDynamicQuery,
  useDataApiQuery,
  useDataApiSingleElementQuery
} from "../../data/ReactUtils";
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
import {Change} from "../../data/classes/Change";
import {useFavIcon} from "../../util/FavIcon";
import {getPropertyValueOrDefault, parseChangeAuthorNameAndEmail} from "../../util/Properties";
import {getBuildOrStepResults, results2class, UNKNOWN} from "../../util/Results";
import {dateFormat, durationFromNowFormat, useCurrentTime} from "../../util/Moment";
import BadgeRound from "../../components/BadgeRound/BadgeRound";
import RawData from "../../components/RawData/RawData";
import PropertiesTable from "../../components/PropertiesTable/PropertiesTable";
import ChangesTable from "../../components/ChangesTable/ChangesTable";
import BuildSummary from "../../components/BuildSummary/BuildSummary";
import ChangeUserAvatar from "../../components/ChangeUserAvatar/ChangeUserAvatar";
import {Tab, Table, Tabs} from "react-bootstrap";
import TableHeading from "../../components/TableHeading/TableHeading";

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
                             changesQuery: DataCollection<Change>) => {
  const responsibleUsers: {[name: string]: string | null} = {};
  if (getPropertyValueOrDefault(propertiesQuery.properties, "scheduler", "") === "force") {
    const owner = getPropertyValueOrDefault(propertiesQuery.properties, "owner", "");
    if (owner.match(/^.+<.+@.+\..+>.*$/)) {
      const splitResult = owner.split(new RegExp('<|>'));
      if (splitResult.length === 2) {
        const name = splitResult[0];
        const email = splitResult[1];
        responsibleUsers[name] = email;
      }
    }
  }

  for (const change of changesQuery.array) {
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
        number__eq: [buildnumber - 1, buildnumber, buildnumber + 1]}
    }));

  const prevBuild = findOrNull(buildsQuery.array, b => b.number === buildnumber - 1);
  const build = findOrNull(buildsQuery.array, b => b.number === buildnumber);
  const nextBuild = findOrNull(buildsQuery.array, b => b.number === buildnumber + 1);

  const changesQuery = useDataApiSingleElementQuery(build, b => b.getChanges());
  const buildrequestsQuery = useDataApiSingleElementQuery(build,
    b => b.buildrequestid === null
      ? new DataCollection<Buildrequest>()
      : Buildrequest.getAll(accessor, {id: b.buildrequestid.toString()}));

  const buildsetsQuery = useDataApiQuery(() => buildrequestsQuery.getRelated(
    br => Buildset.getAll(accessor, {id: br.buildsetid.toString()})));
  const parentBuildQuery = useDataApiQuery(() => buildsetsQuery.getRelated(
    bs => bs.parent_buildid === null
      ? new DataCollection<Build>()
      : Build.getAll(accessor, {id: bs.parent_buildid.toString()})));
  const propertiesQuery = useDataApiDynamicQuery([build === null],
    () => build === null ? new DataPropertiesCollection() : build.getProperties());

  const workersQuery = useDataApiSingleElementQuery(build,
    b => Worker.getAll(accessor, {id: b.workerid.toString()}));

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
      navigate(`/buildrequests/${brid}?redirect_to_build=true`);
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

  useTopbarItems(stores.topbar, [
    {caption: "Builders", route: "/builders"},
    {caption: builder === null ? "..." : builder.name, route: `/builders/${builderid}`},
    {caption: buildnumber.toString(), route: `/builders/${builderid}/builds/${buildnumber}`},
  ]);

  const actions = buildTopbarActions(build, isRebuilding, isStopping, doRebuild, doStop);

  useTopbarActions(stores.topbarActions, actions);
  useFavIcon(getBuildOrStepResults(build, UNKNOWN));

  const renderPager = (build: Build|null) => {
    const renderPrevLink = () => {
      if (buildnumber > 1 && prevBuild !== null && build !== null) {
        return (
          <Link to={`/builders/${builderid}/builds/${prevBuild.number}`}
                className="bb-build-view-nav-button">
            <BadgeRound className={results2class(prevBuild, 'pulse')}>←</BadgeRound>
            <span className="nomobile">&nbsp;Previous</span>
          </Link>
        );
      }
      return (
        <span className="bb-build-view-nav-button">&larr;
          <span className="nomobile">&nbsp;Previous</span>
        </span>
      );
    }

    const renderCompleteTime = () => {
      if (build === null || !build.complete) {
        return <li>&nbsp;</li>;
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
          <Link to={`/builders/${builderid}/builds/${nextBuild.number}`}
                className="bb-build-view-nav-button">
            <span className="nomobile">Next&nbsp;</span>
            <BadgeRound className={results2class(nextBuild, 'pulse')}>→</BadgeRound>
          </Link>
        )
      }

      return (
        <span className="bb-build-view-nav-button">
          <span className="nomobile">Next&nbsp;</span>
          <span>&rarr;</span>
        </span>
      )
    }

    return (
      <ul className="bb-build-view-pager">
        <li className={"previous " + ((build === null || build.number === 1) ? " disabled" : "")}>
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
    return Object.entries(responsibleUsers).map(([author, email], index) => (
      <li key={index} className="list-group-item">
        <ChangeUserAvatar name={author} email={email} showName={true}/>
      </li>
    ));
  };

  const renderDebugInfo = () => {
    if (buildrequest === null || buildset === null) {
      return <TableHeading>Buildrequest:</TableHeading>;
    }

    return (
      <>
        <TableHeading>
          <Link to={`/buildrequests/${buildrequest.id}`}>Buildrequest:</Link>
        </TableHeading>
        <RawData data={buildrequest.toObject()}/>
        <TableHeading>Buildset:</TableHeading>
        <RawData data={buildset.toObject()}/>
      </>
    );
  }

  return (
    <div className="container bb-build-view">
      <AlertNotification text={errorMsg}/>
      <nav>
        {renderPager(build)}
      </nav>
      <Tabs>
        <Tab eventKey="build-steps" title="Build steps">
          { build !== null
            ? <BuildSummary build={build} condensed={false} parentBuild={parentBuild}
                            parentRelationship={buildset === null ? null : buildset.parent_relationship}/>
            : <></>
          }
        </Tab>
        <Tab eventKey="properties" title="Build Properties">
          <PropertiesTable properties={propertiesQuery.properties}/>
        </Tab>
        <Tab eventKey="worker" title={`Worker: ${workerName}`}>
          <Table hover striped size="sm">
            <tbody>
              <tr>
                <td className="text-left">name</td>
                <td className="text-center">{workerName}</td>
              </tr>
              {renderWorkerInfo()}
            </tbody>
          </Table>
        </Tab>
        <Tab eventKey="responsible" title="Responsible Users">
          <ul className="list-group">
            {renderResponsibleUsers()}
          </ul>
        </Tab>
        <Tab eventKey="changes" title="Changes">
          {build !== null
            ? <ChangesTable changes={changesQuery}/>
            : <></>
          }
        </Tab>
        <Tab eventKey="debug" title="Debug">
          {renderDebugInfo()}
        </Tab>
      </Tabs>
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
