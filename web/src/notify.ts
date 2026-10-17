import { notifications } from '@mantine/notifications';

export function showError(e: unknown) {
  notifications.show({
    color: 'red',
    title: 'Something went wrong',
    message: e instanceof Error ? e.message : String(e),
  });
}
