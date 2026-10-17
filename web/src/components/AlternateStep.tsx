import { Alert, Badge, Loader, Stack, Text } from '@mantine/core';

import * as fmt from '../format';
import type { Coverage, Fund } from '../types';
import { FundPicker } from './FundPicker';
import { StepLabel } from './StepLabel';

interface Props {
  fundsWithNav: number | undefined;
  value: Fund | null;
  onChange: (f: Fund | null) => void;
  coverage: Coverage | null;
  coverageLoading: boolean;
}

export function AlternateStep({ fundsWithNav, value, onChange, coverage, coverageLoading }: Props) {
  return (
    <section>
      <StepLabel>Step 4 · Pick the alternate fund to compare</StepLabel>
      <Stack gap="sm">
        <FundPicker
          label="Alternate fund"
          description={
            fundsWithNav ? `${fmt.count(fundsWithNav)} schemes with NAV data` : undefined
          }
          placeholder="Type to search, e.g. Parag Parikh Flexi Cap Direct Growth"
          value={value}
          onChange={onChange}
        />
        {value && coverageLoading && <Loader size="sm" />}
        {value && coverage && !coverageLoading && (
          <Alert color={coverage.n_before ? 'yellow' : 'green'} p="sm">
            <Stack gap={6}>
              <Text size="sm">
                <b>Alternate fund NAV data:</b>{' '}
                <Badge variant="default" radius="sm" tt="none" fw={400} className="mono">
                  {fmt.day(coverage.fund.nav_start)} → {fmt.day(coverage.fund.nav_end)}
                </Badge>
              </Text>
              <Text size="sm">
                {coverage.n_before
                  ? `${coverage.n_before} of your transactions (${fmt.day(coverage.first_before)} – ${fmt.day(coverage.last_before)}) predate this fund's NAV history. They are left out of the comparison.`
                  : "All your transaction dates fall within this fund's NAV history."}
              </Text>
            </Stack>
          </Alert>
        )}
      </Stack>
    </section>
  );
}
