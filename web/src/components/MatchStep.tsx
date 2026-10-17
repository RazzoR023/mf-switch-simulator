import { useState } from 'react';
import { Alert, Anchor, Code, Group, Stack, Text } from '@mantine/core';
import { IconAlertTriangle, IconCircleCheck } from '@tabler/icons-react';

import * as fmt from '../format';
import type { Fund, MatchProblem, StatementFund } from '../types';
import { FundPicker } from './FundPicker';
import { StepLabel } from './StepLabel';

const PROBLEM_TEXT: Record<MatchProblem, (isin: string | null) => string> = {
  no_isin: () => 'the statement has no ISIN for it',
  isin_not_found: (isin) => `ISIN ${isin} isn't in the fund list`,
  no_nav: (isin) => `ISIN ${isin} matches a scheme with no NAV history`,
};

function FundMatch({
  fund,
  chosen,
  onChoose,
}: {
  fund: StatementFund;
  chosen: Fund | null;
  onChoose: (f: Fund | null) => void;
}) {
  const [changing, setChanging] = useState(false);
  const matched = chosen ?? fund.match;
  const picker = (
    <FundPicker
      label={`Scheme for "${fund.name}"`}
      initialQuery={fund.name.slice(0, 50)}
      value={chosen}
      onChange={(f) => {
        onChoose(f);
        if (f) setChanging(false);
      }}
    />
  );

  if (matched && !changing) {
    return (
      <Alert color="green" icon={<IconCircleCheck size={18} />} p="sm">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Text size="sm">
            <b>{fund.name}</b> → {fmt.fundTitle(matched)} <Code>{matched.code}</Code>
            {chosen ? ' (picked by you)' : ' (matched by ISIN)'}
          </Text>
          <Anchor component="button" size="sm" onClick={() => setChanging(true)}>
            Change
          </Anchor>
        </Group>
      </Alert>
    );
  }
  return (
    <Alert
      color="yellow"
      icon={<IconAlertTriangle size={18} />}
      p="sm"
      title={
        matched ? (
          <Group justify="space-between">
            <span>Pick a different scheme for {fund.name}</span>
            <Anchor component="button" size="sm" onClick={() => setChanging(false)}>
              Cancel
            </Anchor>
          </Group>
        ) : (
          `${fund.name}: ${fund.match_problem ? PROBLEM_TEXT[fund.match_problem](fund.isin) : 'not matched'}. Find it below.`
        )
      }
    >
      {picker}
    </Alert>
  );
}

interface Props {
  funds: StatementFund[];
  overrides: Record<string, Fund>;
  onOverride: (name: string, fund: Fund | null) => void;
}

export function MatchStep({ funds, overrides, onOverride }: Props) {
  const unmatched = funds.filter((f) => !(overrides[f.name] ?? f.match)).length;
  return (
    <section>
      <StepLabel>Step 3 · Match your fund(s) in the AMFI database</StepLabel>
      <Stack gap="xs">
        {funds.map((f) => (
          <FundMatch
            key={f.name}
            fund={f}
            chosen={overrides[f.name] ?? null}
            onChoose={(fund) => onOverride(f.name, fund)}
          />
        ))}
        {unmatched > 0 && (
          <Text size="sm" c="dimmed">
            {funds.length - unmatched} of {funds.length} fund(s) matched. Match the rest to enable
            the comparison.
          </Text>
        )}
      </Stack>
    </section>
  );
}
