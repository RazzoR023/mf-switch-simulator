import { ActionIcon, Alert, Badge, Group, Loader, Paper, Stack, Text, Tooltip } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconFileSpreadsheet, IconUpload, IconX } from '@tabler/icons-react';

import type { TradebookResult } from '../types';
import { StepLabel } from './StepLabel';

const ACCEPT = {
  'text/csv': ['.csv'],
  // Windows reports .csv files as this.
  'application/vnd.ms-excel': ['.csv'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

interface Props {
  files: File[];
  parsed: TradebookResult | null;
  loading: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (file: File) => void;
}

export function UploadStep({ files, parsed, loading, onAdd, onRemove }: Props) {
  const resultFor = (f: File) => parsed?.files.find((r) => r.name === f.name);

  return (
    <section>
      <StepLabel>Step 1 · Upload Zerodha Coin statement(s)</StepLabel>
      <Stack gap="sm">
        <Dropzone onDrop={onAdd} accept={ACCEPT} multiple loading={loading} radius="md">
          <Group justify="center" gap="lg" mih={110} style={{ pointerEvents: 'none' }}>
            <Dropzone.Accept>
              <IconUpload size={40} stroke={1.5} />
            </Dropzone.Accept>
            <Dropzone.Reject>
              <IconX size={40} stroke={1.5} />
            </Dropzone.Reject>
            <Dropzone.Idle>
              <IconFileSpreadsheet size={40} stroke={1.5} />
            </Dropzone.Idle>
            <div>
              <Text size="lg">Drop tradebook CSV or Excel files here, or click to choose</Text>
              <Text size="sm" c="dimmed" mt={4}>
                Add several files to combine them; rows that appear in more than one file are
                counted once.
              </Text>
            </div>
          </Group>
        </Dropzone>

        {files.length > 0 && (
          <Paper withBorder p="xs" radius="md">
            <Stack gap={6}>
              {files.map((f) => {
                const r = resultFor(f);
                return (
                  <Group key={`${f.name}-${f.size}-${f.lastModified}`} justify="space-between" wrap="nowrap">
                    <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
                      <IconFileSpreadsheet size={18} style={{ flexShrink: 0 }} />
                      <Text size="sm" truncate>
                        {f.name}
                      </Text>
                      {loading && !r ? (
                        <Loader size="xs" />
                      ) : r?.ok ? (
                        <Badge color="green" variant="light">
                          {r.count} transactions
                        </Badge>
                      ) : r ? (
                        <Tooltip label={r.error} multiline w={320}>
                          <Badge color="red" variant="light">
                            not read
                          </Badge>
                        </Tooltip>
                      ) : null}
                    </Group>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      aria-label={`Remove ${f.name}`}
                      onClick={() => onRemove(f)}
                      disabled={loading}
                    >
                      <IconX size={16} />
                    </ActionIcon>
                  </Group>
                );
              })}
            </Stack>
          </Paper>
        )}

        {parsed?.files
          .filter((r) => !r.ok || r.warnings.length > 0)
          .map((r) => (
            <Alert key={r.name} color={r.ok ? 'yellow' : 'red'} title={r.name} p="sm">
              {r.error ?? r.warnings.join(' ')}
            </Alert>
          ))}

        {parsed && parsed.duplicates.dropped > 0 && (
          <Alert color="yellow" p="sm">
            Removed <b>{parsed.duplicates.dropped}</b> duplicate row(s) across files (matched by{' '}
            {parsed.duplicates.method}).
          </Alert>
        )}
      </Stack>
    </section>
  );
}
