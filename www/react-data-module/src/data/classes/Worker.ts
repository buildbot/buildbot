/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import BaseClass from "./BaseClass";
import IDataDescriptor from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";

export type ConfiguredBuilder = {
  builderid: number,
  masterid: number
}

export type ConnectedMaster = {
  masterid: number;
}

export class Worker extends BaseClass {
  workerid!: number;
  configured_on!: ConfiguredBuilder[];
  connected_to!: ConnectedMaster[];
  name!: string;
  paused!: boolean;
  graceful!: boolean;
  workerinfo!: {[key: string]: any};

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.workerid));
    this.update(object);
  }

  update(object: any) {
    this.workerid = object.workerid;
    this.configured_on = object.configured_on;
    this.connected_to = object.connected_to;
    this.name = object.name;
    this.paused = object.paused;
    this.graceful = object.graceful;
    this.workerinfo = object.workerinfo;
  }

  toObject() {
    return {
      workerid: this.workerid,
      configured_on: this.configured_on,
      connected_to: this.connected_to,
      name: this.name,
      paused: this.paused,
      graceful: this.graceful,
      workerinfo: this.workerinfo,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Worker>("workers", query, workerDescriptor);
  }
}

export class WorkerDescriptor implements IDataDescriptor<Worker> {
  restArrayField = "workers";
  fieldId: string = "workerid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Worker(accessor, endpoint, object);
  }
}

export const workerDescriptor = new WorkerDescriptor();
