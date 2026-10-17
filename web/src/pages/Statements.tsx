import { useMemo, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconAlertTriangle, IconDownload, IconFileSpreadsheet, IconTrash } from '@tabler/icons-react';

import * as api from '../api';
import { PageHeader } from '../components/PageHeader';
import { UploadDropzone } from '../components/UploadDropzone';
import * as fmt from '../format';
import { showError } from '../notify';
import type { Portfolio, UploadFile } from '../types';

interface Props {
  portfolio: Portfolio;
  onPortfolio: (p: Portfolio) => void;
}

export function Statements({ portfolio, onPortfolio }: Props) {
  const [removing, setRemoving] = useState<UploadFile | null>(null);
  const [busy, setBusy] = useState(false);
  const [fundFilter, setFundFilter] = useState<string | null>(null);
  const { files, transactions, duplicates, funds } = portfolio;

  const shown = useMemo(
    () =>
      transactions
        .filter((t) => !fundFilter || t.scheme_name === fundFilter)
        .sort((a, b) => b.date.localeCompare(a.date)),
    [transactions, fundFilter],
  );

  const remove = async () => {
    if (!removing) return;
    setBusy(true);
    try {
      onPortfolio(await api.deleteUpload(removing.id));
      setRemoving(null);
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Statements"
        description="Tradebooks saved to your account. Every comparison uses all of them together."
      />
      <Stack gap="lg">
        <UploadDropzone onPortfolio={onPortfolio} compact />

        {files.length > 0 && (
          <Card padding={0}>
            <Table.ScrollContainer minWidth={620}>
              <Table verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th pl="lg">File</Table.Th>
                    <Table.Th>Uploaded</Table.Th>
                    <Table.Th ta="right">Transactions</Table.Th>
                    <Table.Th pr="lg" />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {files.map((f) => (
                    <Table.Tr key={f.id}>
                      <Table.Td pl="lg">
                        <Group gap="sm" wrap="nowrap">
                          <IconFileSpreadsheet size={20} stroke={1.5} style={{ flexShrink: 0 }} />
                          <div style={{ minWidth: 0 }}>
                            <Text size="sm" fw={500} truncate>
                              {f.name}
                            </Text>
                            <Text size="xs" c="dimmed">
                              {fmt.fileSize(f.size)}
                            </Text>
                          </div>
                          {f.warnings.length > 0 && (
                            <Tooltip label={f.warnings.join(' ')} multiline maw={320}>
                              <IconAlertTriangle size={16} color="var(--mantine-color-yellow-6)" />
                            </Tooltip>
                          )}
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{fmt.dateTime(f.uploaded_at)}</Text>
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {fmt.count(f.count)}
                      </Table.Td>
                      <Table.Td pr="lg">
                        <Group gap={4} justify="flex-end" wrap="nowrap">
                          <Tooltip label="Download original">
                            <ActionIcon
                              variant="subtle"
                              color="gray"
                              component="a"
                              href={api.uploadUrl(f.id)}
                              aria-label={`Download ${f.name}`}
                            >
                              <IconDownload size={16} />
                            </ActionIcon>
                          </Tooltip>
                          <Tooltip label="Remove">
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              onClick={() => setRemoving(f)}
                              aria-label={`Remove ${f.name}`}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Card>
        )}

        {duplicates.dropped > 0 && (
          <Alert color="accent" variant="light" p="sm">
            <b>{duplicates.dropped}</b> rows appear in more than one file and are counted once
            (matched by {duplicates.method}).
          </Alert>
        )}

        {transactions.length > 0 && (
          <Card padding={0}>
            <Group justify="space-between" p="lg" pb="sm" gap="sm">
              <Group gap="xs">
                <Title order={4}>Transactions</Title>
                <Badge variant="light">{fmt.count(shown.length)}</Badge>
              </Group>
              <Select
                placeholder="All funds"
                data={funds.map((f) => f.name)}
                value={fundFilter}
                onChange={setFundFilter}
                clearable
                searchable
                w={{ base: '100%', sm: 360 }}
              />
            </Group>
            <Table.ScrollContainer minWidth={720} maxHeight={560}>
              <Table striped stickyHeader highlightOnHover fz="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th pl="lg">Date</Table.Th>
                    <Table.Th>Fund</Table.Th>
                    <Table.Th>Type</Table.Th>
                    <Table.Th ta="right">Amount</Table.Th>
                    <Table.Th ta="right">Units</Table.Th>
                    <Table.Th ta="right" pr="lg">
                      NAV
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {shown.map((t, i) => (
                    <Table.Tr key={i}>
                      <Table.Td pl="lg" className="num">
                        {fmt.day(t.date)}
                      </Table.Td>
                      <Table.Td>{t.scheme_name}</Table.Td>
                      <Table.Td>
                        <Badge
                          size="sm"
                          variant="light"
                          color={t.direction === 'sell' ? 'orange' : 'accent'}
                        >
                          {t.direction}
                        </Badge>
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {fmt.money(t.amount)}
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {fmt.units(t.units)}
                      </Table.Td>
                      <Table.Td ta="right" pr="lg" className="num">
                        {fmt.nav(t.nav)}
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </Card>
        )}
      </Stack>

      <Modal opened={!!removing} onClose={() => setRemoving(null)} title="Remove statement?" centered>
        <Stack>
          <Text size="sm">
            <b>{removing?.name}</b> and its {removing?.count} transactions will be deleted from
            your account. Saved comparisons stay, but re-running them uses what's left.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRemoving(null)}>
              Cancel
            </Button>
            <Button color="red" loading={busy} onClick={remove}>
              Remove
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
