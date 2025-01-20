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
import {CodebaseCommit, codebaseCommitDescriptor} from "./CodebaseCommit";
import {CodebaseBranch, codebaseBranchDescriptor} from "./CodebaseBranch";

export class Codebase extends BaseClass {
  @observable codebaseid!: number;
  @observable name!: string;
  @observable slug!: string;
  @observable projectid!: number;

  constructor(accessor: IDataAccessor, endpoint: string, object: any) {
    super(accessor, endpoint, String(object.codebaseid));
    this.update(object);
    makeObservable(this);
  }

  @action update(object: any) {
    this.codebaseid = object.codebaseid;
    this.name = object.name;
    this.slug = object.slug;
    this.projectid = object.projectid;
  }

  toObject() {
    return {
      codebaseid: this.codebaseid,
      name: this.name,
      slug: this.slug,
      projectid: this.projectid,
    };
  }

  getCommits(query: RequestQuery = {}) {
    return this.get<CodebaseCommit>("commits", query, codebaseCommitDescriptor);
  }

  getBranches(query: RequestQuery = {}) {
    return this.get<CodebaseBranch>("branches", query, codebaseBranchDescriptor);
  }

  static getAll(accessor: IDataAccessor, query: RequestQuery = {}) {
    return accessor.get("codebases", query, codebaseDescriptor);
  }
}

export class CodebaseDescriptor implements IDataDescriptor<Codebase> {
  restArrayField = "codebases";
  fieldId: string = "codebaseid";

  parse(accessor: IDataAccessor, endpoint: string, object: any) {
    return new Codebase(accessor, endpoint, object);
  }
}

export const codebaseDescriptor = new CodebaseDescriptor();
