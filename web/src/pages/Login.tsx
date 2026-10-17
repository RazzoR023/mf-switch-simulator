import { useState } from 'react';
import {
  Alert,
  Button,
  Paper,
  PasswordInput,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { IconArrowsExchange, IconInfoCircle } from '@tabler/icons-react';

import * as api from '../api';
import type { Me } from '../types';

interface Props {
  signup: boolean;
  onSignedIn: (me: Me) => void;
}

export function Login({ signup, onSignedIn }: Props) {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const creating = mode === 'signup';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (creating && password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onSignedIn(await (creating ? api.signup : api.login)(username.trim(), password));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={400}>
        <form onSubmit={submit}>
          <Stack gap="lg">
            <Stack gap="xs" align="center">
              <ThemeIcon size={48} radius="md" variant="light">
                <IconArrowsExchange size={28} />
              </ThemeIcon>
              <Title order={2} ta="center">
                MF Switch Simulator
              </Title>
              <Text size="sm" c="dimmed" ta="center">
                What if you had invested in a different fund?
              </Text>
            </Stack>

            {signup && (
              <SegmentedControl
                fullWidth
                value={mode}
                onChange={(v) => {
                  setMode(v as 'login' | 'signup');
                  setError(null);
                }}
                data={[
                  { value: 'login', label: 'Sign in' },
                  { value: 'signup', label: 'Create account' },
                ]}
              />
            )}

            {error && (
              <Alert color="red" icon={<IconInfoCircle size={18} />} p="sm">
                {error}
              </Alert>
            )}

            <TextInput
              label="Username"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              required
              autoFocus
            />
            <PasswordInput
              label="Password"
              autoComplete={creating ? 'new-password' : 'current-password'}
              description={creating ? 'At least 8 characters' : undefined}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              required
            />
            {creating && (
              <PasswordInput
                label="Confirm password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.currentTarget.value)}
                required
              />
            )}
            <Button type="submit" fullWidth loading={busy}>
              {creating ? 'Create account' : 'Sign in'}
            </Button>
            {!signup && (
              <Text size="xs" c="dimmed" ta="center">
                Accounts are created by the admin.
              </Text>
            )}
          </Stack>
        </form>
      </Paper>
    </div>
  );
}
