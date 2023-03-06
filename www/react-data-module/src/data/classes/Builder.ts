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
import {Build, buildDescriptor} from "./Build";
import {Buildrequest, buildrequestDescriptor} from "./Buildrequest";
import {Forcescheduler, forceschedulerDescriptor} from "./Forcescheduler";
import {Worker, workerDescriptor} from "./Worker";
import {Master, masterDescriptor} from "./Master";

export class Builder extends BaseClass {
  builderid!: number;
  description!: string|null;
  masterids!: string[];
  name!: string;
  tags!: string[];

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.builderid));
    this.update(object);
  }

  update(object: any) {
    this.builderid = object.builderid;
    this.description = object.description;
    this.masterids = object.masterids;
    this.name = object.name;
    this.tags = object.tags;
  }

  toObject() {
    return {
      builderid: this.builderid,
      description: this.description,
      masterids: this.masterids,
      name: this.name,
      tags: this.tags,
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