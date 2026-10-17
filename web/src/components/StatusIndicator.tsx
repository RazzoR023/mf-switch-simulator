import { Badge, HoverCard, Loader, Stack, Text } from '@mantine/core';

import * as fmt from '../format';
import type { Status } from '../types';

/** A small badge in the header for the NAV data's freshness, with details on hover. */
export function StatusIndicator({ status }: { status: Status | null }) {
  if (!status) return null;
  if (!status.ready) {
    return (
      <Badge variant="light" leftSection={<Loader size={10} />}>
        Building NAV data
      </Badge>
    );
  }
  const stale = !status.fresh;
  return (
    <HoverCard width={300} shadow="md" position="bottom-end" withArrow>
      <HoverCard.Target>
        <Badge
          variant="dot"
          color={stale ? 'yellow' : 'green'}
          size="lg"
          tt="none"
          fw={500}
          style={{ cursor: 'default' }}
          visibleFrom="xs"
        >
          NAV {fmt.day(status.latest_nav_date)}
        </Badge>
      </HoverCard.Target>
      <HoverCard.Dropdown>
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            {stale ? `NAV data is ${status.days_stale} days behind` : 'NAV data is up to date'}
          </Text>
          <Text size="xs" c="dimmed">
            {fmt.count(status.funds_with_nav ?? 0)} schemes · latest NAV{' '}
            {fmt.day(status.latest_nav_date)} · refreshed {fmt.dateTime(status.refreshed_at)}
          </Text>
          {stale && (
            <Text size="xs" c="dimmed">
              The upstream data source hasn't updated, so recent purchases may have no NAV.
            </Text>
          )}
        </Stack>
      </HoverCard.Dropdown>
    </HoverCard>
  );
}
