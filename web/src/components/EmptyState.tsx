import { Alert, List, Paper, Text, Title } from '@mantine/core';
import { IconInfoCircle } from '@tabler/icons-react';

export function EmptyState() {
  return (
    <>
      <Alert color="yellow" icon={<IconInfoCircle size={18} />} p="sm">
        <b>Export from Zerodha Coin:</b> log in → Coin → Portfolio → Transaction History →
        Download.
      </Alert>
      <Paper withBorder p="lg" radius="md" maw={560}>
        <Title order={4} mb="xs">
          How it works
        </Title>
        <List type="ordered" size="sm" spacing={6}>
          <List.Item>Reads the dates and amounts of every buy and sell in your statement.</List.Item>
          <List.Item>Replays the same timeline in another fund, using its historical NAV.</List.Item>
          <List.Item>Shows XIRR and returns side by side.</List.Item>
          <List.Item>Flags dates where either fund has no NAV.</List.Item>
        </List>
        <Text size="xs" c="dimmed" mt="sm">
          Your statement is processed on this server and not stored anywhere.
        </Text>
      </Paper>
    </>
  );
}
