import { useState } from 'react';
import {
  Avatar,
  Button,
  Menu,
  Modal,
  PasswordInput,
  Stack,
  Text,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import { IconKey, IconLogout, IconMoon, IconSun } from '@tabler/icons-react';

import * as api from '../api';
import type { User } from '../types';

function PasswordModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setCurrent('');
    setNext('');
    setConfirm('');
    setError(null);
    onClose();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      setError("The new passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(current, next);
      notifications.show({
        color: 'green',
        message: 'Password changed. Other browsers have been signed out.',
      });
      close();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={opened} onClose={close} title="Change password" centered>
      <form onSubmit={submit}>
        <Stack>
          <PasswordInput
            label="Current password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.currentTarget.value)}
            required
            data-autofocus
          />
          <PasswordInput
            label="New password"
            description="At least 8 characters"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.currentTarget.value)}
            required
          />
          <PasswordInput
            label="Confirm new password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.currentTarget.value)}
            error={error}
            required
          />
          <Button type="submit" loading={busy}>
            Change password
          </Button>
        </Stack>
      </form>
    </Modal>
  );
}

export function UserMenu({ user, onSignedOut }: { user: User; onSignedOut: () => void }) {
  const [pwOpen, pw] = useDisclosure();
  const { setColorScheme } = useMantineColorScheme();
  const scheme = useComputedColorScheme('light');

  const signOut = async () => {
    await api.logout().catch(() => {});
    onSignedOut();
  };

  return (
    <>
      <Menu shadow="md" width={220} position="bottom-end">
        <Menu.Target>
          <UnstyledButton aria-label="Account menu">
            <Avatar color="accent" radius="xl" size={34}>
              {user.username.slice(0, 2).toUpperCase()}
            </Avatar>
          </UnstyledButton>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>
            Signed in as{' '}
            <Text span size="xs" fw={600} c="var(--mantine-color-text)">
              {user.username}
            </Text>
          </Menu.Label>
          <Menu.Item
            leftSection={scheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
            onClick={() => setColorScheme(scheme === 'dark' ? 'light' : 'dark')}
          >
            {scheme === 'dark' ? 'Light mode' : 'Dark mode'}
          </Menu.Item>
          <Menu.Item leftSection={<IconKey size={16} />} onClick={pw.open}>
            Change password
          </Menu.Item>
          <Menu.Divider />
          <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={signOut}>
            Sign out
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <PasswordModal opened={pwOpen} onClose={pw.close} />
    </>
  );
}
