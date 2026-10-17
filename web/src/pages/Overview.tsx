import { useState } from 'react';
import {
  Anchor,
  Button,
  Card,
  Group,
  Progress,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowsExchange,
  IconCash,
  IconChartPie,
  IconReceipt,
  IconReceiptRefund,
} from '@tabler/icons-react';

import { MatchCell } from '../components/MatchBadge';
import { MatchModal } from '../components/MatchModal';
import { PageHeader } from '../components/PageHeader';
import { StatCard } from '../components/StatCard';
import { UploadDropzone } from '../components/UploadDropzone';
import * as fmt from '../format';
import type { Page } from '../Shell';
import type { Portfolio, SavedComparison, StatementFund } from '../types';

const BAR_COLORS = ['accent', 'teal', 'grape', 'orange', 'cyan', 'pink', 'lime', 'indigo', 'yellow'];

interface Props {
  portfolio: Portfolio;
  saved: SavedComparison[];
  onPortfolio: (p: Portfolio) => void;
  onCompare: (funds: string[]) => void;
  onOpenSaved: (s: SavedComparison) => void;
  go: (p: Page) => void;
}

export function Overview({ portfolio, saved, onPortfolio, onCompare, onOpenSaved, go }: Props) {
  const [matching, setMatching] = useState<StatementFund | null>(null);
  const { funds, files, transactions } = portfolio;

  if (!files.length) {
    return (
      <>
        <PageHeader
          title="Welcome"
          description="Upload your Zerodha Coin tradebook to get started. It's saved to your account, so you only do this once."
        />
        <Card>
          <Stack>
            <UploadDropzone onPortfolio={onPortfolio} />
            <Text size="sm" c="dimmed">
              In Coin: <b>Portfolio → Transaction History</b>, then <b>Download</b> as CSV. You can
              add more files later; rows that repeat across files are counted once.
            </Text>
          </Stack>
        </Card>
      </>
    );
  }

  const bought = funds.reduce((a, f) => a + f.bought, 0);
  const sold = funds.reduce((a, f) => a + f.sold, 0);
  const unmatched = funds.filter((f) => !f.match).length;
  const byInvested = [...funds].sort((a, b) => b.bought - a.bought);
  const color = (i: number) => BAR_COLORS[i % BAR_COLORS.length];
  const first = transactions.reduce((m, t) => (t.date < m ? t.date : m), transactions[0]?.date ?? '');

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Your statements since ${fmt.day(first)}`}
        actions={
          <Button leftSection={<IconArrowsExchange size={16} />} onClick={() => go('compare')}>
            New comparison
          </Button>
        }
      />
      <Stack gap="lg">
        <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
          <StatCard
            label="Invested"
            value={fmt.compactMoney(bought)}
            hint={fmt.money(bought)}
            icon={<IconCash size={20} />}
          />
          <StatCard
            label="Redeemed"
            value={fmt.compactMoney(sold)}
            hint={sold ? fmt.money(sold) : 'No sells'}
            icon={<IconReceiptRefund size={20} />}
            color="teal"
          />
          <StatCard
            label="Transactions"
            value={fmt.count(transactions.length)}
            hint={`from ${fmt.plural(files.length, 'statement')}`}
            icon={<IconReceipt size={20} />}
            color="grape"
          />
          <StatCard
            label="Funds"
            value={funds.length}
            hint={unmatched ? `${unmatched} need a scheme match` : 'All matched to AMFI schemes'}
            icon={<IconChartPie size={20} />}
            color={unmatched ? 'yellow' : 'orange'}
          />
        </SimpleGrid>

        <Card>
          <Group justify="space-between" mb="sm">
            <Title order={4}>Where your money went</Title>
            <Text size="sm" c="dimmed">
              Share of total purchases
            </Text>
          </Group>
          <Progress.Root size={14} radius="xl">
            {byInvested.map((f, i) => (
              <Tooltip key={f.name} label={`${f.name}: ${fmt.money(f.bought)}`}>
                <Progress.Section value={(f.bought / bought) * 100} color={color(i)} />
              </Tooltip>
            ))}
          </Progress.Root>
        </Card>

        <Card padding={0}>
          <Group justify="space-between" p="lg" pb="sm">
            <Title order={4}>Your funds</Title>
            <Text size="sm" c="dimmed">
              Each fund is replayed in the AMFI scheme it's matched to
            </Text>
          </Group>
          <Table.ScrollContainer minWidth={860}>
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th pl="lg">Fund</Table.Th>
                  <Table.Th>Activity</Table.Th>
                  <Table.Th ta="right">Invested</Table.Th>
                  <Table.Th w={300}>AMFI scheme</Table.Th>
                  <Table.Th pr="lg" />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {byInvested.map((f, i) => (
                  <Table.Tr key={f.name}>
                    <Table.Td pl="lg">
                      <Group gap="sm" wrap="nowrap">
                        <div
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: 3,
                            flexShrink: 0,
                            background: `var(--mantine-color-${color(i)}-6)`,
                          }}
                        />
                        <div style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500}>
                            {f.name}
                          </Text>
                          <Text size="xs" c="dimmed" className="mono">
                            {f.isin ?? 'no ISIN'}
                          </Text>
                        </div>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{fmt.txnBlurb(f)}</Text>
                      <Text size="xs" c="dimmed">
                        {fmt.day(f.first_date)} → {fmt.day(f.last_date)}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right" className="num">
                      <Text size="sm">{fmt.money(f.bought)}</Text>
                      {f.sold > 0 && (
                        <Text size="xs" c="dimmed">
                          {fmt.money(f.sold)} sold
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <MatchCell fund={f} onEdit={() => setMatching(f)} />
                    </Table.Td>
                    <Table.Td pr="lg" ta="right">
                      <Button
                        size="compact-sm"
                        variant="default"
                        disabled={!f.match}
                        onClick={() => onCompare([f.name])}
                      >
                        Compare
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>

        {saved.length > 0 && (
          <Card>
            <Group justify="space-between" mb="sm">
              <Title order={4}>Recent comparisons</Title>
              <Anchor size="sm" onClick={() => go('saved')}>
                See all
              </Anchor>
            </Group>
            <Stack gap="xs">
              {saved.slice(0, 3).map((s) => (
                <Group key={s.id} justify="space-between" wrap="nowrap">
                  <Anchor size="sm" onClick={() => onOpenSaved(s)} lineClamp={1}>
                    {s.name}
                  </Anchor>
                  <Text
                    size="sm"
                    className={`num ${s.snapshot.value_diff >= 0 ? 'better' : 'worse'}`}
                  >
                    {fmt.signedMoney(s.snapshot.value_diff)}
                  </Text>
                </Group>
              ))}
            </Stack>
          </Card>
        )}
      </Stack>
      <MatchModal fund={matching} onClose={() => setMatching(null)} onPortfolio={onPortfolio} />
    </>
  );
}
