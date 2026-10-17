import { useState } from 'react';
import { ActionIcon, Button, Card, Group, Stack, Table, Text, Tooltip } from '@mantine/core';
import { IconPlayerPlay, IconTrash } from '@tabler/icons-react';

import * as api from '../api';
import { PageHeader } from '../components/PageHeader';
import * as fmt from '../format';
import { showError } from '../notify';
import type { Page } from '../Shell';
import type { SavedComparison } from '../types';

interface Props {
  saved: SavedComparison[];
  onSaved: (s: SavedComparison[]) => void;
  onOpen: (s: SavedComparison) => void;
  go: (p: Page) => void;
}

export function SavedPage({ saved, onSaved, onOpen, go }: Props) {
  const [deleting, setDeleting] = useState<number | null>(null);

  const remove = async (id: number) => {
    setDeleting(id);
    try {
      onSaved(await api.deleteSaved(id));
    } catch (e) {
      showError(e);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Saved comparisons"
        description="The figures are from when each was saved. Open one to re-run it with today's NAVs."
      />
      {!saved.length ? (
        <Card>
          <Stack align="center" py="xl" gap="sm">
            <Text c="dimmed">Nothing saved yet. Run a comparison and press Save.</Text>
            <Button variant="light" onClick={() => go('compare')}>
              Go to compare
            </Button>
          </Stack>
        </Card>
      ) : (
        <Card padding={0}>
          <Table.ScrollContainer minWidth={820}>
            <Table verticalSpacing="sm" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th pl="lg">Comparison</Table.Th>
                  <Table.Th ta="right">Your value</Table.Th>
                  <Table.Th ta="right">Alternate</Table.Th>
                  <Table.Th ta="right">Difference</Table.Th>
                  <Table.Th ta="right">XIRR</Table.Th>
                  <Table.Th pr="lg" />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {saved.map((s) => {
                  const { snapshot: snap } = s;
                  const gain = snap.value_diff >= 0;
                  return (
                    <Table.Tr key={s.id}>
                      <Table.Td pl="lg" maw={360}>
                        <Text size="sm" fw={500} lineClamp={1}>
                          {s.name}
                        </Text>
                        <Text size="xs" c="dimmed" lineClamp={1}>
                          {snap.actual_label} → {snap.alt_label} · as of {fmt.day(snap.as_of)}
                          {s.params.exclude_sells ? ' · sells excluded' : ''}
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {fmt.money(snap.actual_value)}
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        {fmt.money(snap.alt_value)}
                      </Table.Td>
                      <Table.Td ta="right" className={`num ${gain ? 'better' : 'worse'}`}>
                        {fmt.signedMoney(snap.value_diff)}
                      </Table.Td>
                      <Table.Td ta="right" className="num">
                        <Text size="sm">
                          {fmt.xirr(snap.actual_xirr)} → {fmt.xirr(snap.alt_xirr)}
                        </Text>
                      </Table.Td>
                      <Table.Td pr="lg">
                        <Group gap={4} justify="flex-end" wrap="nowrap">
                          <Button
                            size="compact-sm"
                            variant="light"
                            leftSection={<IconPlayerPlay size={14} />}
                            onClick={() => onOpen(s)}
                          >
                            Open
                          </Button>
                          <Tooltip label="Delete">
                            <ActionIcon
                              variant="subtle"
                              color="red"
                              loading={deleting === s.id}
                              onClick={() => remove(s.id)}
                              aria-label={`Delete ${s.name}`}
                            >
                              <IconTrash size={16} />
                            </ActionIcon>
                          </Tooltip>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </Card>
      )}
    </>
  );
}
