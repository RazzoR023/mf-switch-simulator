import { Alert, Button, Group, Stack, Table, Text } from '@mantine/core';
import { IconAlertTriangle, IconDownload, IconTrendingDown, IconTrendingUp } from '@tabler/icons-react';

import * as fmt from '../format';
import type { Comparison, DetailRow } from '../types';
import { StepLabel } from './StepLabel';

function Verdict({ result }: { result: Comparison }) {
  const { value_diff, xirr_diff } = result.verdict;
  const gain = value_diff >= 0;
  const alt = result.alternate.label;
  const n = result.funds.length;
  return (
    <Alert
      color={gain ? 'green' : 'red'}
      icon={gain ? <IconTrendingUp size={20} /> : <IconTrendingDown size={20} />}
      title="Verdict"
    >
      <Text>
        {n === 1 ? (
          <>
            Switching to <em>{alt}</em>
          </>
        ) : (
          <>
            Clubbing your {n} funds ({result.n_txns} transactions) into <em>{alt}</em>
          </>
        )}
        {result.exclude_sells && <Text span c="dimmed"> (sells excluded)</Text>} would have{' '}
        {gain ? 'added' : 'cost'} you <b>{fmt.money(Math.abs(value_diff))}</b> (
        {fmt.signedPct(xirr_diff)} XIRR difference).
      </Text>
    </Alert>
  );
}

function SummaryTable({ result }: { result: Comparison }) {
  const n = result.funds.length;
  const actualHdr = n === 1 ? `Actual · ${fmt.truncate(result.funds[0])}` : `Actual · ${n} funds clubbed`;
  const altHdr = `Alternate · ${fmt.truncate(result.alternate.label)}`;
  const altWins = result.verdict.value_diff >= 0;
  return (
    <Table.ScrollContainer minWidth={560}>
      <Table verticalSpacing="xs" fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w="30%">Metric</Table.Th>
            <Table.Th className={altWins ? undefined : 'winner-col'}>{actualHdr}</Table.Th>
            <Table.Th className={altWins ? 'winner-col' : undefined}>{altHdr}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {result.metrics.map((m) => (
            <Table.Tr key={m.key}>
              <Table.Td c="dimmed">{m.label}</Table.Td>
              <Table.Td className={`num ${m.actual_cls}`}>{fmt.metricValue(m.kind, m.actual)}</Table.Td>
              <Table.Td className={`num ${m.alternate_cls}`}>
                {fmt.metricValue(m.kind, m.alternate)}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

function notes(r: DetailRow): string {
  const parts = [];
  if (r.actual_status === 'no_nav') parts.push('no NAV (actual)');
  if (r.alt_status === 'no_nav') parts.push('no NAV (alt)');
  return parts.length ? `⚠ ${parts.join(', ')}` : '✓';
}

function DetailTable({ rows }: { rows: DetailRow[] }) {
  return (
    <Table.ScrollContainer minWidth={900} maxHeight={520}>
      <Table striped stickyHeader highlightOnHover fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Date</Table.Th>
            <Table.Th>Fund</Table.Th>
            <Table.Th>Type</Table.Th>
            <Table.Th ta="right">Amount</Table.Th>
            <Table.Th ta="right">Actual NAV</Table.Th>
            <Table.Th ta="right">Actual units</Table.Th>
            <Table.Th ta="right">Alt NAV</Table.Th>
            <Table.Th ta="right">Alt units</Table.Th>
            <Table.Th>Notes</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r, i) => (
            <Table.Tr key={i}>
              <Table.Td className="num">{fmt.day(r.date)}</Table.Td>
              <Table.Td>{r.fund}</Table.Td>
              <Table.Td tt="capitalize">{r.direction}</Table.Td>
              <Table.Td ta="right" className="num">
                {fmt.money(r.direction === 'sell' ? -r.amount : r.amount)}
              </Table.Td>
              <Table.Td ta="right" className="num">{fmt.nav(r.actual_nav)}</Table.Td>
              <Table.Td ta="right" className="num">{fmt.units(r.actual_units)}</Table.Td>
              <Table.Td ta="right" className="num">{fmt.nav(r.alt_nav)}</Table.Td>
              <Table.Td ta="right" className="num">{fmt.units(r.alt_units)}</Table.Td>
              <Table.Td c={notes(r) === '✓' ? 'dimmed' : 'yellow.8'}>{notes(r)}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

interface Props {
  result: Comparison;
  downloading: boolean;
  onDownload: () => void;
}

export function Results({ result, downloading, onDownload }: Props) {
  const neg = result.alternate.negative_events;
  const { actual: missActual, alternate: missAlt } = result.missing;
  return (
    <Stack gap="lg">
      <Verdict result={result} />

      {neg.length > 0 && (
        <Alert color="yellow" icon={<IconAlertTriangle size={18} />} p="sm">
          On <b>{fmt.day(neg[0].date)}</b> your sell of <b>{fmt.money(neg[0].amount)}</b> was more
          than the alternate fund was worth by then
          {neg.length > 1 ? ` (and ${neg.length - 1} more time(s))` : ''}. Its units went
          negative so the maths stays consistent, but that holding couldn't exist in reality.
        </Alert>
      )}

      <section>
        <StepLabel>Comparison summary</StepLabel>
        <SummaryTable result={result} />
      </section>

      <section>
        <StepLabel>Transaction detail</StepLabel>
        <Stack gap="sm">
          {(missActual > 0 || missAlt > 0) && (
            <Alert color="yellow" p="sm">
              Missing NAV data → actual: <b>{missActual}</b> rows, alternate: <b>{missAlt}</b> rows.
              These rows are left out of the XIRR and return figures.
            </Alert>
          )}
          <DetailTable rows={result.detail} />
        </Stack>
      </section>

      <Group>
        <Button
          variant="default"
          leftSection={<IconDownload size={16} />}
          loading={downloading}
          onClick={onDownload}
        >
          Download Excel report
        </Button>
        <Text size="xs" c="dimmed">
          Values as of {fmt.day(result.as_of)}, using each fund's latest NAV in the data.
        </Text>
      </Group>
    </Stack>
  );
}
