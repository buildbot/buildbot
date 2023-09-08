/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {action, makeObservable, observable} from "mobx";
import {BaseClass} from "./BaseClass";
import {IDataDescriptor} from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";
import {Log, logDescriptor} from "./Log";

export type StepUrl = {
  name: string;
  url: string;
}

export class Step extends BaseClass {
  @observable stepid!: number;
  @observable buildid!: number;
  @observable complete!: boolean;
  @observable complete_at!: number|null;
  @observable hidden!: boolean;
  @observable locks_acquired_at!: number|null;
  @observable name!: string;
  @observable number!: number;
  @observable results!: number;
  @observable started_at!: number|null;
  @observable state_string!: string;
  @observable urls!: StepUrl[];

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.stepid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.stepid = object.stepid;
    this.buildid = object.buildid;
    this.complete = object.complete;
    this.complete_at = object.complete_at;
    this.hidden = object.hidden;
    this.locks_acquired_at = object.locks_acquired_at;
    this.name = object.name;
    this.number = object.number;
    this.results = object.results;
    this.started_at = object.started_at;
    this.state_string = object.state_string;
    this.urls = object.urls;
  }

  toObject() {
    return {
      stepid: this.stepid,
      buildid: this.buildid,
      complete: this.complete,
      complete_at: this.complete_at,
      hidden: this.hidden,
      locks_acquired_at: this.locks_acquired_at,
      name: this.name,
      number: this.number,
      results: this.results,
      started_at: this.started_at,
      state_string: this.state_string,
      urls: this.urls,
    };
  }

  getLogs(query: RequestQuery = {}) {
    return this.get<Log>("logs", query, logDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Step>("steps", query, stepDescriptor);
  }
}

export class StepDescriptor implements IDataDescriptor<Step> {
  restArrayField = "steps";
  fieldId: string = "stepid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Step(accessor, endpoint, object);
  }
}

export const stepDescriptor = new StepDescriptor();
