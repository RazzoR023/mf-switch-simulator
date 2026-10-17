import { Accordion, Alert, Badge, MultiSelect, Stack, Table, Text } from '@mantine/core';

import * as fmt from '../format';
import type { StatementFund, Transaction } from '../types';
import { StepLabel } from './StepLabel';

interface Props {
  funds: StatementFund[];
  transactions: Transaction[];
  selected: string[];
  onChange: (names: string[]) => void;
}

export function FundsStep({ funds, transactions, selected, onChange }: Props) {
  const chosen = funds.filter((f) => selected.includes(f.name));
  const pooled = transactions
    .filter((t) => selected.includes(t.scheme_name))
    .sort((a, b) => a.date.localeCompare(b.date));
  const combined = {
    n_txns: pooled.length,
    n_buys: pooled.filter((t) => t.direction === 'buy').length,
    n_sells: pooled.filter((t) => t.direction === 'sell').length,
  };

  return (
    <section>
      <StepLabel>Step 2 · Select fund(s) from your statement</StepLabel>
      <Stack gap="sm">
        <MultiSelect
          label="Your fund(s)"
          description="Pick one, or several to club them into one combined real portfolio"
          placeholder={selected.length ? undefined : 'Choose funds'}
          data={funds.map((f) => ({ value: f.name, label: f.name }))}
          value={selected}
          onChange={onChange}
          searchable
          clearable
          hidePickedOptions
        />

        {chosen.length > 0 && (
          <>
            <Stack gap={6}>
              {chosen.map((f) => (
                <Badge
                  key={f.name}
                  variant="default"
                  radius="sm"
                  size="lg"
                  tt="none"
                  fw={400}
                  className="mono"
                  styles={{ root: { height: 'auto', paddingBlock: 4, whiteSpace: 'normal' } }}
                >
                  {f.name} · {fmt.txnBlurb(f)} · {fmt.day(f.first_date)} → {fmt.day(f.last_date)}
                </Badge>
              ))}
            </Stack>
            <Alert color="accent" p="sm">
              <b>Combined:</b> {chosen.length} fund{chosen.length > 1 ? 's' : ''} ·{' '}
              {fmt.txnBlurb(combined)} · {fmt.day(pooled[0]?.date)} →{' '}
              {fmt.day(pooled[pooled.length - 1]?.date)}
            </Alert>
            <Accordion variant="contained" radius="md">
              <Accordion.Item value="preview">
                <Accordion.Control>
                  <Text size="sm">Preview transactions ({pooled.length})</Text>
                </Accordion.Control>
                <Accordion.Panel>
                  <Table.ScrollContainer minWidth={640} maxHeight={360}>
                    <Table striped stickyHeader fz="sm">
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th>Date</Table.Th>
                          <Table.Th>Fund</Table.Th>
                          <Table.Th>Type</Table.Th>
                          <Table.Th ta="right">Amount</Table.Th>
                          <Table.Th ta="right">Units</Table.Th>
                          <Table.Th ta="right">NAV</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {pooled.map((t, i) => (
                          <Table.Tr key={i}>
                            <Table.Td className="num">{fmt.day(t.date)}</Table.Td>
                            <Table.Td>{t.scheme_name}</Table.Td>
                            <Table.Td tt="capitalize">{t.direction}</Table.Td>
                            <Table.Td ta="right" className="num">
                              {fmt.money(t.amount)}
                            </Table.Td>
                            <Table.Td ta="right" className="num">
                              {fmt.units(t.units)}
                            </Table.Td>
                            <Table.Td ta="right" className="num">
                              {fmt.nav(t.nav)}
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          </>
        )}
      </Stack>
    </section>
  );
}
