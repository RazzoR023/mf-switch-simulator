import { useEffect, useState } from 'react';
import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';

import * as api from '../api';
import * as fmt from '../format';
import { showError } from '../notify';
import type { Fund, MatchProblem, Portfolio, StatementFund } from '../types';
import { FundPicker } from './FundPicker';

export const PROBLEM_TEXT: Record<MatchProblem, (isin: string | null) => string> = {
  no_isin: () => 'The statement has no ISIN for this fund.',
  isin_not_found: (isin) => `ISIN ${isin} isn't in the AMFI fund list.`,
  no_nav: (isin) => `ISIN ${isin} matches a scheme with no NAV history.`,
};

interface Props {
  fund: StatementFund | null;
  onClose: () => void;
  onPortfolio: (p: Portfolio) => void;
}

/** Picks the AMFI scheme a statement fund is replayed in. The choice is saved per user. */
export function MatchModal({ fund, onClose, onPortfolio }: Props) {
  const [pick, setPick] = useState<Fund | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setPick(fund?.match ?? null), [fund]);

  const save = async (code: number | null) => {
    if (!fund) return;
    setBusy(true);
    try {
      onPortfolio(await api.setMatch(fund.name, code));
      onClose();
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={!!fund} onClose={onClose} title="Match fund to a scheme" size="lg" centered>
      {fund && (
        <Stack>
          <div>
            <Text fw={600}>{fund.name}</Text>
            <Text size="sm" c="dimmed">
              {fund.isin ?? 'No ISIN'} · {fmt.txnBlurb(fund)} · {fmt.day(fund.first_date)} →{' '}
              {fmt.day(fund.last_date)}
            </Text>
          </div>
          {fund.match_problem && fund.match_source !== 'user' && (
            <Alert color="yellow" p="sm">
              {PROBLEM_TEXT[fund.match_problem](fund.isin)} Search for it below.
            </Alert>
          )}
          <FundPicker
            label="AMFI scheme"
            initialQuery={fund.match ? undefined : fund.name.slice(0, 50)}
            value={pick}
            onChange={setPick}
          />
          <Group justify="space-between">
            {fund.match_source === 'user' ? (
              <Button variant="subtle" color="gray" onClick={() => save(null)} disabled={busy}>
                Reset to ISIN match
              </Button>
            ) : (
              <span />
            )}
            <Group gap="xs">
              <Button variant="default" onClick={onClose}>
                Cancel
              </Button>
              <Button
                onClick={() => pick && save(pick.code)}
                loading={busy}
                disabled={!pick || pick.code === fund.match?.code}
              >
                Use this scheme
              </Button>
            </Group>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
