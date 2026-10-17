import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Center,
  Grid,
  Loader,
  LoadingOverlay,
  MultiSelect,
  Stack,
  Switch,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { IconArrowsExchange, IconBolt, IconInfoCircle } from '@tabler/icons-react';

import * as api from '../api';
import { FundPicker } from '../components/FundPicker';
import { MatchCell } from '../components/MatchBadge';
import { MatchModal } from '../components/MatchModal';
import { PageHeader } from '../components/PageHeader';
import { Results } from '../components/Results';
import * as fmt from '../format';
import { showError } from '../notify';
import type { CompareState, Page } from '../Shell';
import type {
  CompareRequest,
  Comparison,
  Coverage,
  Portfolio,
  SavedComparison,
  StatementFund,
  Status,
} from '../types';

interface Props {
  portfolio: Portfolio;
  onPortfolio: (p: Portfolio) => void;
  status: Status;
  setup: CompareState;
  onSetup: (s: CompareState) => void;
  request: CompareRequest | null;
  sellsInScope: boolean;
  result: Comparison | null;
  running: boolean;
  onRun: () => void;
  onSaved: (s: SavedComparison[]) => void;
  go: (p: Page) => void;
}

function CoverageNote({ request }: { request: CompareRequest }) {
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const key = JSON.stringify(request);

  useEffect(() => {
    let cancelled = false;
    setCoverage(null);
    api
      .getCoverage(request)
      .then((c) => !cancelled && setCoverage(c))
      .catch((e) => !cancelled && showError(e));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!coverage) return <Loader size="xs" />;
  return (
    <Text size="xs" c={coverage.n_before ? 'yellow.8' : 'dimmed'}>
      NAV history {fmt.day(coverage.fund.nav_start)} → {fmt.day(coverage.fund.nav_end)}.{' '}
      {coverage.n_before
        ? `${coverage.n_before} of your transactions (${fmt.day(coverage.first_before)} – ${fmt.day(coverage.last_before)}) predate it and are left out.`
        : 'Covers all your transactions.'}
    </Text>
  );
}

export function ComparePage(props: Props) {
  const { portfolio, onPortfolio, status, setup, onSetup, request, sellsInScope, result, running } =
    props;
  const [matching, setMatching] = useState<StatementFund | null>(null);
  const selectedFunds = portfolio.funds.filter((f) => setup.selected.includes(f.name));
  const unmatched = selectedFunds.filter((f) => !f.match).length;
  const pooled = portfolio.transactions.filter((t) => setup.selected.includes(t.scheme_name));
  const combined = {
    n_txns: pooled.length,
    n_buys: pooled.filter((t) => t.direction === 'buy').length,
    n_sells: pooled.filter((t) => t.direction === 'sell').length,
  };

  if (!portfolio.funds.length) {
    return (
      <>
        <PageHeader title="Compare" />
        <Card>
          <Stack align="center" py="xl" gap="sm">
            <Text>Upload a statement first: comparisons replay your own transactions.</Text>
            <Button onClick={() => props.go('statements')}>Go to statements</Button>
          </Stack>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Compare"
        description="Replay your purchases and sells in another fund, on the same dates and amounts."
      />
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Card className="sticky-setup">
            <Stack gap="md">
              <MultiSelect
                label="Your funds"
                description="Pick several to club them into one portfolio"
                placeholder={setup.selected.length ? undefined : 'Choose funds'}
                data={portfolio.funds.map((f) => ({ value: f.name, label: f.name }))}
                value={setup.selected}
                onChange={(selected) => onSetup({ ...setup, selected })}
                searchable
                clearable
                hidePickedOptions
              />

              {selectedFunds.length > 0 && (
                <Stack gap="xs">
                  {selectedFunds.map((f) => (
                    <Card key={f.name} padding="xs" bg="var(--mantine-color-default-hover)">
                      <Text size="xs" fw={600} lineClamp={1}>
                        {f.name}
                      </Text>
                      <MatchCell fund={f} onEdit={() => setMatching(f)} />
                    </Card>
                  ))}
                  <Text size="xs" c="dimmed">
                    {fmt.txnBlurb(combined)} · {fmt.day(pooled[0] && pooled.map((t) => t.date).sort()[0])}{' '}
                    → {fmt.day(pooled.map((t) => t.date).sort().at(-1))}
                  </Text>
                </Stack>
              )}
              {unmatched > 0 && (
                <Alert color="yellow" p="xs" icon={<IconInfoCircle size={16} />}>
                  <Text size="xs">Match every selected fund to a scheme to compare.</Text>
                </Alert>
              )}

              <Stack gap={6}>
                <FundPicker
                  label="Compare against"
                  description={`${fmt.count(status.funds_with_nav ?? 0)} schemes with NAV data`}
                  placeholder="e.g. Parag Parikh Flexi Cap Direct Growth"
                  value={setup.alt}
                  onChange={(alt) => onSetup({ ...setup, alt })}
                />
                {request && <CoverageNote request={request} />}
              </Stack>

              {sellsInScope && (
                <Switch
                  label="Exclude sells"
                  description="Treat every bought unit as still held"
                  checked={setup.excludeSells}
                  onChange={(e) => onSetup({ ...setup, excludeSells: e.currentTarget.checked })}
                />
              )}

              <Button
                size="md"
                fullWidth
                leftSection={<IconBolt size={18} />}
                disabled={!request}
                loading={running}
                onClick={props.onRun}
              >
                Run comparison
              </Button>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 8 }} pos="relative">
          <LoadingOverlay visible={running && !!result} overlayProps={{ blur: 1 }} />
          {result && request ? (
            <Results result={result} request={request} onSaved={props.onSaved} />
          ) : (
            <Card h="100%" mih={320}>
              <Center h="100%" mih={280}>
                <Stack align="center" gap="sm" maw={380}>
                  <ThemeIcon size={56} radius="xl" variant="light">
                    {running ? <Loader size="sm" /> : <IconArrowsExchange size={30} />}
                  </ThemeIcon>
                  <Title order={4}>{running ? 'Crunching the numbers…' : 'No result yet'}</Title>
                  <Text size="sm" c="dimmed" ta="center">
                    Pick one or more of your funds, choose a fund to compare against, then run
                    the comparison.
                  </Text>
                </Stack>
              </Center>
            </Card>
          )}
        </Grid.Col>
      </Grid>
      <MatchModal fund={matching} onClose={() => setMatching(null)} onPortfolio={onPortfolio} />
    </>
  );
}
