import {
  ActionIcon,
  Alert,
  Group,
  Loader,
  Stack,
  Text,
  Title,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core';
import { IconAlertTriangle, IconDatabase, IconMoon, IconSun } from '@tabler/icons-react';

import * as fmt from '../format';
import type { Status } from '../types';

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme('light');
  const next = scheme === 'dark' ? 'light' : 'dark';
  return (
    <Tooltip label={`Switch to ${next} mode`}>
      <ActionIcon
        variant="default"
        size="lg"
        aria-label={`Switch to ${next} mode`}
        onClick={() => setColorScheme(next)}
      >
        {scheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}

export function Header() {
  return (
    <Group className="page-header" justify="space-between" align="flex-end" wrap="nowrap">
      <Stack gap={4}>
        <Title order={1} fz={{ base: '1.8rem', sm: '2.4rem' }} lh={1.15} style={{ letterSpacing: '-0.02em' }}>
          MF Switch Simulator
        </Title>
        <Text className="mono" size="xs" c="dimmed" tt="uppercase" style={{ letterSpacing: '0.1em' }}>
          What if I had invested in a different fund?
        </Text>
      </Stack>
      <ColorSchemeToggle />
    </Group>
  );
}

export function StatusBanner({ status }: { status: Status | null }) {
  if (!status) return null;
  if (!status.ready) {
    return (
      <Alert color="accent" icon={<Loader size={16} />} title="Preparing the NAV database">
        The fund list and NAV history are being downloaded and indexed. The first start takes a
        few minutes; this page updates by itself.
      </Alert>
    );
  }
  const stale = !status.fresh;
  return (
    <Alert
      color={stale ? 'yellow' : 'accent'}
      icon={stale ? <IconAlertTriangle size={18} /> : <IconDatabase size={18} />}
      p="sm"
    >
      <Text size="sm">
        NAV database: <b>{fmt.count(status.funds_with_nav ?? 0)} funds</b> · refreshed{' '}
        {fmt.dateTime(status.refreshed_at)} · latest NAV in data{' '}
        <b>{fmt.day(status.latest_nav_date)}</b>
        {stale ? (
          <>
            {' '}
            · <b>{status.days_stale} days behind today</b>. The upstream data source hasn't updated,
            so recent purchases may have no NAV.
          </>
        ) : (
          ' · up to date'
        )}
      </Text>
    </Alert>
  );
}
