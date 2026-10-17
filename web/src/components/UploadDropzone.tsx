import { useState } from 'react';
import { Group, Text } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { notifications } from '@mantine/notifications';
import { IconFileSpreadsheet, IconUpload, IconX } from '@tabler/icons-react';

import * as api from '../api';
import { showError } from '../notify';
import type { Portfolio } from '../types';

const ACCEPT = {
  'text/csv': ['.csv'],
  // Windows reports .csv files as this.
  'application/vnd.ms-excel': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

/** Uploads statements straight to the user's account and reports each file. */
export function UploadDropzone({
  onPortfolio,
  compact,
}: {
  onPortfolio: (p: Portfolio) => void;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false);

  const drop = async (files: File[]) => {
    setBusy(true);
    try {
      const { results, portfolio } = await api.upload(files);
      onPortfolio(portfolio);
      for (const r of results) {
        notifications.show({
          color: r.ok ? (r.warnings.length ? 'yellow' : 'green') : 'red',
          title: r.name,
          message: r.ok
            ? `Saved ${r.count} transactions.${r.warnings.length ? ` ${r.warnings.join(' ')}` : ''}`
            : r.error,
          autoClose: r.ok ? 4000 : 10_000,
        });
      }
    } catch (e) {
      showError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dropzone onDrop={drop} accept={ACCEPT} multiple loading={busy} radius="md">
      <Group
        justify="center"
        gap="lg"
        mih={compact ? 90 : 160}
        style={{ pointerEvents: 'none' }}
        wrap="nowrap"
      >
        <Dropzone.Accept>
          <IconUpload size={40} stroke={1.5} color="var(--mantine-color-accent-6)" />
        </Dropzone.Accept>
        <Dropzone.Reject>
          <IconX size={40} stroke={1.5} color="var(--mantine-color-red-6)" />
        </Dropzone.Reject>
        <Dropzone.Idle>
          <IconFileSpreadsheet size={40} stroke={1.5} color="var(--mantine-color-dimmed)" />
        </Dropzone.Idle>
        <div>
          <Text size="lg" fw={500}>
            Drop Zerodha Coin tradebooks here, or click to choose
          </Text>
          <Text size="sm" c="dimmed" mt={4}>
            CSV or Excel. Files are saved to your account; rows that appear in more than one
            file are counted once.
          </Text>
        </div>
      </Group>
    </Dropzone>
  );
}
