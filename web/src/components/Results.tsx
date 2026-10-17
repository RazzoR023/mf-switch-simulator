import { useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle,
  IconBookmark,
  IconDownload,
  IconTrendingDown,
  IconTrendingUp,
} from '@tabler/icons-react';

import * as api from '../api';
import * as fmt from '../format';
import { showError } from '../notify';
import type { CompareRequest, Comparison, DetailRow, SavedComparison, Scenario } from '../types';

function Verdict({ result }: { result: Comparison }) {
  const { value_diff, xirr_diff } = result.verdict;
  const gain = value_diff >= 0;
  const n = result.funds.length;
  const color = gain ? 'green' : 'red';
  return (
    <Card style={{ borderLeft: `4px solid var(--mantine-color-${color}-6)` }}>
      <Group wrap="nowrap" align="flex-start" gap="md">
        <ThemeIcon size={44} radius="md" variant="light" color={color}>
          {gain ? <IconTrendingUp size={26} /> : <IconTrendingDown size={26} />}
        </ThemeIcon>
        <div>
          <Text fz={30} fw={700} c={`${color}.7`} className="num" lh={1.1}>
            {fmt.signedMoney(value_diff)}
          </Text>
          <Text size="sm" mt={6}>
            {n === 1 ? 'Switching to ' : `Clubbing your ${n} funds (${result.n_txns} transactions) into `}
            <b>{result.alternate.label}</b>
            {result.exclude_sells && ' (sells excluded)'} would have {gain ? 'added' : 'cost'} you{' '}
            {fmt.money(Math.abs(value_diff))}, a {fmt.signedPct(xirr_diff)} difference in XIRR.
          </Text>
        </div>
      </Group>
    </Card>
  );
}

function ScenarioCard({
  title,
  label,
  s,
  winner,
}: {
  title: string;
  label: string;
  s: Scenario;
  winner: boolean;
}) {
  const ret = s.current_value + s.total_proceeds - s.total_bought;
  return (
    <Card className={winner ? 'winner' : undefined}>
      <Group justify="space-between" wrap="nowrap" align="flex-start" mb="sm">
        <div style={{ minWidth: 0 }}>
          <Text className="stat-label">{title}</Text>
          <Text size="sm" fw={500} lineClamp={2}>
            {label}
          </Text>
        </div>
        {winner && (
          <Badge color="green" variant="light">
            Better
          </Badge>
        )}
      </Group>
      <Text fz={28} fw={700} className="num">
        {fmt.money(s.current_value)}
      </Text>
      <Text size="xs" c="dimmed" mb="md">
        current value
      </Text>
      <SimpleGrid cols={3} spacing="xs">
        <div>
          <Text className="stat-label">Net invested</Text>
          <Text size="sm" className="num">
            {fmt.money(s.net_invested)}
          </Text>
        </div>
        <div>
          <Text className="stat-label">Return</Text>
          <Text size="sm" className={`num ${ret >= 0 ? 'better' : 'worse'}`}>
            {fmt.signedPct(s.return_pct)}
          </Text>
        </div>
        <div>
          <Text className="stat-label">XIRR</Text>
          <Text size="sm" className="num" fw={600}>
            {fmt.xirr(s.xirr)}
          </Text>
        </div>
      </SimpleGrid>
    </Card>
  );
}

function SummaryTable({ result }: { result: Comparison }) {
  return (
    <Table.ScrollContainer minWidth={520}>
      <Table verticalSpacing="xs" fz="sm" highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w="34%">Metric</Table.Th>
            <Table.Th ta="right">Actual</Table.Th>
            <Table.Th ta="right">Alternate</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {result.metrics.map((m) => (
            <Table.Tr key={m.key}>
              <Table.Td c="dimmed">{m.label}</Table.Td>
              <Table.Td ta="right" className={`num ${m.actual_cls}`}>
                {fmt.metricValue(m.kind, m.actual)}
              </Table.Td>
              <Table.Td ta="right" className={`num ${m.alternate_cls}`}>
                {fmt.metricValue(m.kind, m.alternate)}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

const missing = (r: DetailRow) =>
  [r.actual_status === 'no_nav' && 'actual', r.alt_status === 'no_nav' && 'alternate'].filter(
    Boolean,
  ) as string[];

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
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((r, i) => {
            const miss = missing(r);
            return (
              <Table.Tr key={i}>
                <Table.Td className="num">{fmt.day(r.date)}</Table.Td>
                <Table.Td>
                  <Text size="sm" lineClamp={1}>
                    {r.fund}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light" color={r.direction === 'sell' ? 'orange' : 'accent'}>
                    {r.direction}
                  </Badge>
                </Table.Td>
                <Table.Td ta="right" className="num">
                  {fmt.money(r.direction === 'sell' ? -r.amount : r.amount)}
                </Table.Td>
                <Table.Td ta="right" className="num">{fmt.nav(r.actual_nav)}</Table.Td>
                <Table.Td ta="right" className="num">{fmt.units(r.actual_units)}</Table.Td>
                <Table.Td ta="right" className="num">{fmt.nav(r.alt_nav)}</Table.Td>
                <Table.Td ta="right" className="num">{fmt.units(r.alt_units)}</Table.Td>
                <Table.Td>
                  {miss.length > 0 && (
                    <Badge size="sm" color="yellow" variant="light">
                      no NAV ({miss.join(', ')})
                    </Badge>
                  )}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

interface Props {
  result: Comparison;
  request: CompareRequest;
  onSaved: (s: SavedComparison[]) => void;
}

export function Results({ result, request, onSaved }: Props) {
  const [downloading, setDownloading] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const defaultName = `${result.actual.label} → ${result.alternate.label}`;
  const [name, setName] = useState(defaultName);

  const neg = result.alternate.negative_events;
  const { actual: missActual, alternate: missAlt } = result.missing;
  const altWins = result.verdict.value_diff >= 0;

  const download = async () => {
    setDownloading(true);
    try {
      await api.downloadReport(request);
    } catch (e) {
      showError(e);
    } finally {
      setDownloading(false);
    }
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      onSaved(await api.saveComparison(request, name.trim()));
      notifications.show({ color: 'green', message: 'Comparison saved.' });
      setSaveOpen(false);
    } catch (err) {
      showError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack gap="md">
      <Group justify="space-between" gap="xs">
        <div>
          <Title order={3}>Result</Title>
          <Text size="xs" c="dimmed">
            Values as of {fmt.day(result.as_of)}, at each fund's latest NAV
          </Text>
        </div>
        <Group gap="xs">
          <Button
            variant="default"
            leftSection={<IconBookmark size={16} />}
            onClick={() => {
              setName(defaultName);
              setSaveOpen(true);
            }}
          >
            Save
          </Button>
          <Button
            variant="default"
            leftSection={<IconDownload size={16} />}
            loading={downloading}
            onClick={download}
          >
            Excel
          </Button>
        </Group>
      </Group>

      <Verdict result={result} />

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <ScenarioCard
          title="What you did"
          label={result.funds.length === 1 ? result.funds[0] : `${result.funds.length} funds clubbed`}
          s={result.actual}
          winner={!altWins}
        />
        <ScenarioCard title="The alternate" label={result.alternate.label} s={result.alternate} winner={altWins} />
      </SimpleGrid>

      {neg.length > 0 && (
        <Alert color="yellow" icon={<IconAlertTriangle size={18} />} p="sm">
          On <b>{fmt.day(neg[0].date)}</b> your sell of <b>{fmt.money(neg[0].amount)}</b> was more
          than the alternate fund was worth by then
          {neg.length > 1 ? ` (and ${neg.length - 1} more time(s))` : ''}. Its units went negative
          so the maths stays consistent, but that holding couldn't exist in reality.
        </Alert>
      )}
      {(missActual > 0 || missAlt > 0) && (
        <Alert color="yellow" icon={<IconAlertTriangle size={18} />} p="sm">
          Missing NAV data for <b>{missActual}</b> actual and <b>{missAlt}</b> alternate rows. They
          are left out of the XIRR and return figures.
        </Alert>
      )}

      <Card padding="sm">
        <Tabs defaultValue="summary">
          <Tabs.List>
            <Tabs.Tab value="summary">All metrics</Tabs.Tab>
            <Tabs.Tab value="detail">
              Transactions{' '}
              <Badge size="xs" variant="light" ml={4}>
                {result.detail.length}
              </Badge>
            </Tabs.Tab>
          </Tabs.List>
          <Tabs.Panel value="summary" pt="sm">
            <SummaryTable result={result} />
          </Tabs.Panel>
          <Tabs.Panel value="detail" pt="sm">
            <DetailTable rows={result.detail} />
          </Tabs.Panel>
        </Tabs>
      </Card>

      <Modal opened={saveOpen} onClose={() => setSaveOpen(false)} title="Save comparison" centered>
        <form onSubmit={save}>
          <Stack>
            <TextInput
              label="Name"
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              maxLength={120}
              data-autofocus
            />
            <Text size="xs" c="dimmed">
              Saves the funds, the alternate and the options. Opening it later re-runs it with
              current NAVs and your statements at that time.
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setSaveOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                Save
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}
