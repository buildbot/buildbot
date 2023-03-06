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

export class Sourcestamp extends BaseClass {
  ssid!: number;
  branch!: string|null;
  codebase!: string;
  created_at!: number;
  patch!: string|null; // TODO
  project!: string;
  repository!: string;
  revision!: string|null;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.ssid));
    this.update(object);
  }

  update(object: any) {
    this.ssid = object.ssid;
    this.branch = object.branch;
    this.codebase = object.codebase;
    this.created_at = object.created_at;
    this.patch = object.patch;
    this.project = object.project;
    this.repository = object.repository;
    this.revision = object.revision;
  }

  toObject() {
    return {
      ssid: this.ssid,
      branch: this.branch,
      codebase: this.codebase,
      created_at: this.created_at,
      patch: this.patch,
      project: this.project,
      repository: this.repository,
      revision: this.revision,
    };
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get<Sourcestamp>("sourcestamps", query, sourcestampDescriptor);
  }
}

export class SourcestampDescriptor implements IDataDescriptor<Sourcestamp> {
  restArrayField = "sourcestamps";
  fieldId: string = "ssid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Sourcestamp(accessor, endpoint, object);
  }
}

export const sourcestampDescriptor = new SourcestampDescriptor();
