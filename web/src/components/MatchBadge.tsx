import { Badge, Button, Group, Stack, Text, Tooltip } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';

import * as fmt from '../format';
import type { StatementFund } from '../types';

/** A fund's matched scheme, with a button to change or fix it. */
export function MatchCell({ fund, onEdit }: { fund: StatementFund; onEdit: () => void }) {
  if (!fund.match) {
    return (
      <Button
        size="compact-sm"
        variant="light"
        color="yellow"
        leftSection={<IconAlertTriangle size={14} />}
        onClick={onEdit}
      >
        Match scheme
      </Button>
    );
  }
  return (
    <Group gap="xs" wrap="nowrap" align="flex-start" justify="space-between">
      <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
        <Tooltip label={fmt.fundTitle(fund.match)} openDelay={400} multiline maw={360}>
          <Text size="sm" lineClamp={1}>
            {fmt.fundTitle(fund.match)}
          </Text>
        </Tooltip>
        <Group gap={6}>
          <Text size="xs" c="dimmed" className="mono">
            {fund.match.code}
          </Text>
          <Badge size="xs" variant="light" color={fund.match_source === 'user' ? 'violet' : 'gray'}>
            {fund.match_source === 'user' ? 'picked' : 'ISIN'}
          </Badge>
        </Group>
      </Stack>
      <Button size="compact-xs" variant="subtle" onClick={onEdit} style={{ flexShrink: 0 }}>
        Change
      </Button>
    </Group>
  );
}
