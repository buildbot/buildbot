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
import {useState} from "react";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {
  Build,
  Builder,
  Buildrequest,
  DataCollection,
  Forcescheduler,
  Project,
  useDataAccessor,
  useDataApiQuery
} from "buildbot-data-js";
import {getBuildLinkDisplayProperties, TopbarAction, useTopbarItems, useTopbarActions, WorkerBadge} from "buildbot-ui";
import {BuildsTable} from "../../components/BuildsTable/BuildsTable";
import {BuildRequestsTable} from "../../components/BuildrequestsTable/BuildrequestsTable";
import {useNavigate, useParams} from "react-router-dom";
import {AlertNotification} from "../../components/AlertNotification/AlertNotification";
import {ForceBuildModal} from "../../components/ForceBuildModal/ForceBuildModal";
import {TableHeading} from "../../components/TableHeading/TableHeading";
import {FaStop, FaSpinner} from "react-icons/fa";
import {buildTopbarItemsForBuilder} from "../../util/TopbarUtils";
import { Tab, Tabs } from "react-bootstrap";
import { LoadingSpan } from "../../components/LoadingSpan/LoadingSpan";

const anyCancellableBuilds = (builds: DataCollection<Build>,
                              buildrequests: DataCollection<Buildrequest>) => {
  let cancellable = false;
  for (const build of builds.array) {
    if (!build.complete) {
      cancellable = true;
    }
  }
  for (const buildrequest of buildrequests.array) {
    if (!buildrequest.claimed) {
      cancellable = true;
    }
  }
  return cancellable;
}

const buildTopbarActions = (builds: DataCollection<Build>,
                            buildrequests: DataCollection<Buildrequest>,
                            forceschedulers: DataCollection<Forcescheduler>,
                            isCancelling: boolean,
                            cancelWholeQueue: () => void,
                            invokeScheduler: (sch: Forcescheduler) => void) => {
  const actions: TopbarAction[] = [];

  if (anyCancellableBuilds(builds, buildrequests)) {
    if (isCancelling) {
      actions.push({
        caption: "Cancelling...",
        icon: <FaSpinner/>,
        action: cancelWholeQueue
      });
    } else {
      actions.push({
        caption: "Cancel whole queue",
        variant: "danger",
        icon: <FaStop/>,
        action: cancelWholeQueue
      });
    }
  }

  for (const sch of forceschedulers.array) {
    actions.push({
      caption: sch.button_name,
      variant: "primary",
      action: () => { invokeScheduler(sch); }
    });
  }

  return actions;
}

export const BuilderView = observer(() => {
  const builderid = Number.parseInt(useParams<"builderid">().builderid ?? "");
  const navigate = useNavigate();

  const accessor = useDataAccessor([builderid]);

  const numBuilds = 200;

  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor, {id: builderid.toString()}));
  const buildsQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => Build.getAll(accessor, {query: {
        builderid: builder.builderid,
        property: ["owners", "workername", "branch", "revision", ...getBuildLinkDisplayProperties()],
        limit: numBuilds,
        order: '-number'
      }
    })));
  const buildrequestsQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => Buildrequest.getAll(accessor, {query: {
        builderid: builder.builderid,
        claimed: false
      }
    })));
  const forceSchedulersQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => builder.getForceschedulers({query: {order: "name"}})));

  const projectsQuery = useDataApiQuery(() => buildersQuery.getRelated(builder => {
    return builder.projectid === null
    ? new DataCollection<Project>()
    : Project.getAll(accessor, {id: builder.projectid.toString()})
  }));

  const workersQuery = useDataApiQuery(() =>
    buildersQuery.getRelated(builder => builder.getWorkers({query: {
      order: 'name'
    }
  })));

  const builder = buildersQuery.getNthOrNull(0);
  const builds = buildsQuery.getParentCollectionOrEmpty(builderid.toString());
  const buildrequests = buildrequestsQuery.getParentCollectionOrEmpty(builderid.toString());
  const forceschedulers = forceSchedulersQuery.getParentCollectionOrEmpty(builderid.toString());
  const project = projectsQuery.getNthOrNull(0);
  const workers = workersQuery.getParentCollectionOrEmpty(builderid.toString());

  const [isCancelling, setIsCancelling] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useTopbarItems(buildTopbarItemsForBuilder(builder, project, []));

  const cancelWholeQueue = () => {
    if (isCancelling) {
      return;
    }
    if (!window.confirm("Are you sure you want to cancel all builds?")) {
      return;
    }
    setIsCancelling(true);

    const dl: Promise<void>[] = [];
    for (const buildrequest of buildrequests.array) {
      if (!buildrequest.claimed) {
        dl.push(buildrequest.control('cancel'));
      }
    }
    for (const build of builds.array) {
      if (!build.complete) {
        dl.push(build.control('stop'));
      }
    }
    Promise.all(dl).then(() => {
      setIsCancelling(false);
    }, (reason) => {
      setIsCancelling(false);
      setErrorMsg(`Cannot cancel: ${reason.error.message}`);
    })
  };

  const [shownForceScheduler, setShownForceScheduler] = useState<null|Forcescheduler>(null);

  const actions = buildTopbarActions(builds, buildrequests, forceschedulers, isCancelling,
    cancelWholeQueue, (sch) => setShownForceScheduler(sch));

  useTopbarActions(actions);

  const onForceBuildModalClose = (buildRequestNumber: string | null) => {
    if (buildRequestNumber === null) {
      setShownForceScheduler(null);
    } else {
      navigate(`/buildrequests/${buildRequestNumber}?redirect_to_build=true`);
    }
  };

  const renderDescription = (builder: Builder) => {
    if (builder.description_format !== null && builder.description_html !== null) {
      return (
        <div><TableHeading>Description:</TableHeading>
          <div dangerouslySetInnerHTML={{__html: builder.description_html}}/>
        </div>
      )
    } else {
      return (
        <div><TableHeading>Description:</TableHeading>{builder.description}</div>
      );
    }
  };

  const renderWorkers = () => {
    return (
    <ul className="list-inline bb-builder-workers-container">
    {
      !workers.isResolved() ? <LoadingSpan/> :
      workers.array.length === 0 ? <span>None</span> :
      workers.array.map(worker => (
        <li><WorkerBadge key={worker.name} worker={worker} showWorkerName={true}/></li>
      ))
    }
    </ul>);
  };

  return (
    <div className="container">
      <AlertNotification text={errorMsg}/>
      {builder !== null && builder.description !== null
        ? renderDescription(builder)
        : <></>
      }
      <div>
        <Tabs defaultActiveKey={1}>
          <Tab eventKey={1} title="Builds">
            <TableHeading>Builds requests:</TableHeading>
            <BuildRequestsTable buildrequests={buildrequests}/>
            <BuildsTable builds={builds} builders={null}/>
          </Tab>
          <Tab eventKey={2} title="Workers">
            {renderWorkers()}
          </Tab>
        </Tabs>
      </div>

      {shownForceScheduler !== null
        ? <ForceBuildModal scheduler={shownForceScheduler} builderid={builderid}
                           onClose={onForceBuildModalClose}/>
        : <></>
      }
    </div>
  );
  // TODO: reimplement build duration tab
  // TODO: display more than 100 builds
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "builders/:builderid",
      group: null,
      element: () => <BuilderView/>,
  });
});
