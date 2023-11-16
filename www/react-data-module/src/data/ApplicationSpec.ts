/*
  This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the
  MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.

  Copyright Buildbot Team Members
*/

import {DataClient} from "./DataClient";
import {useEffect, useState} from "react";

export type EndpointFieldSpec = {
  name: string;
  type: string;
  type_spec: EndpointTypeSpec;
}

export type EndpointTypeSpec = {
  name?: string;
  type?: string;
  can_be_null?: boolean;
  of?: EndpointTypeSpec;
  fields?: EndpointFieldSpec[];
}

export type EndpointDescription = {
  path: string;
  plural: string;
  type: string;
  type_spec: EndpointTypeSpec;
}

export const useApplicationSpec = (dataClient: DataClient) => {
  const [result, setResult] = useState<EndpointDescription[]>([]);

  useEffect(() => {
    const performRequest = async () => {
      const response = await dataClient.restClient.get('application.spec');
      setResult(response.specs as EndpointDescription[]);
    }
    performRequest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return result;
}
