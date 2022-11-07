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

import BaseClass from "./BaseClass";
import IDataDescriptor from "./DataDescriptor";
import {IDataAccessor} from "../DataAccessor";
import {RequestQuery} from "../DataQuery";
import {Log, logDescriptor} from "./Log";

export type StepUrl = {
  name: string;
  url: string;
}

export class Step extends BaseClass {
  stepid!: number;
  buildid!: number;
  complete!: boolean;
  complete_at!: number|null;
  hidden!: boolean;
  name!: string;
  number!: number;
  results!: number;
  started_at!: number|null;
  state_string!: string;
  urls!: StepUrl[];

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.stepid));
    this.update(object);
  }

  update(object: any) {
    this.stepid = object.stepid;
    this.buildid = object.buildid;
    this.complete = object.complete;
    this.complete_at = object.complete_at;
    this.hidden = object.hidden;
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
