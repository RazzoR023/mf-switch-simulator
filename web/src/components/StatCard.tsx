import type { ReactNode } from 'react';
import { Card, Group, Text, ThemeIcon } from '@mantine/core';

interface Props {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon: ReactNode;
  color?: string;
}

export function StatCard({ label, value, hint, icon, color = 'accent' }: Props) {
  return (
    <Card padding="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div style={{ minWidth: 0 }}>
          <Text className="stat-label">{label}</Text>
          <Text fz={26} fw={650} className="num" mt={4} lh={1.2}>
            {value}
          </Text>
          {hint && (
            <Text size="xs" c="dimmed" mt={4}>
              {hint}
            </Text>
          )}
        </div>
        <ThemeIcon variant="light" color={color} size={38} radius="md">
          {icon}
        </ThemeIcon>
      </Group>
    </Card>
  );
}
