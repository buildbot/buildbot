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
import {Build, buildDescriptor} from "./Build";
import {Buildrequest, buildrequestDescriptor} from "./Buildrequest";
import {Forcescheduler, forceschedulerDescriptor} from "./Forcescheduler";
import {Worker, workerDescriptor} from "./Worker";
import {Master, masterDescriptor} from "./Master";

export class Builder extends BaseClass {
  @observable builderid!: number;
  @observable description!: string|null;
  @observable description_format!: string|null;
  @observable description_html!: string|null;
  @observable masterids!: number[];
  @observable name!: string;
  @observable tags!: string[];
  @observable projectid!: string|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.builderid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.builderid = object.builderid;
    this.description = object.description;
    this.description_format = object.description_format;
    this.description_html = object.description_html;
    this.masterids = object.masterids;
    this.name = object.name;
    this.tags = object.tags;
    this.projectid = object.projectid;
  }

  toObject() {
    return {
      builderid: this.builderid,
      description: this.description,
      masterids: this.masterids,
      name: this.name,
      tags: this.tags,
      projectid: this.projectid,
    };
  }

  getBuilds(query: RequestQuery = {}) {
    return this.get<Build>("builds", query, buildDescriptor);
  }

  getBuildrequests(query: RequestQuery = {}) {
    return this.get<Buildrequest>("buildrequests", query, buildrequestDescriptor);
  }

  getForceschedulers(query: RequestQuery = {}) {
    return this.get<Forcescheduler>("forceschedulers", query, forceschedulerDescriptor);
  }

  getWorkers(query: RequestQuery = {}) {
    return this.get<Worker>("workers", query, workerDescriptor);
  }

  getMasters(query: RequestQuery = {}) {
    return this.get<Master>("masters", query, masterDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Builder>("builders", query, builderDescriptor);
  }
}

export class BuilderDescriptor implements IDataDescriptor<Builder> {
  restArrayField = "builders";
  fieldId: string = "builderid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Builder(accessor, endpoint, object);
  }
}

export const builderDescriptor = new BuilderDescriptor();
