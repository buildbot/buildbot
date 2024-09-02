import { afterEach } from 'vitest';
import { cleanup, configure } from '@testing-library/react';

configure({testIdAttribute: 'data-bb-test-id'})

afterEach(() => {
  cleanup();
});
