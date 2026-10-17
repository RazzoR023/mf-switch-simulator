import { useEffect, useState } from 'react';
import { Center, Loader } from '@mantine/core';

import * as api from './api';
import { Login } from './pages/Login';
import { Shell } from './Shell';
import type { Me } from './types';

/** Shows the login page until there's a session, then the app. */
export function App() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.setSignedOutHandler(() => setMe((cur) => (cur ? { ...cur, user: null } : cur)));
    api
      .me()
      .then(setMe)
      .catch(() => setMe({ user: null, signup: false }));
  }, []);

  if (!me) {
    return (
      <Center h="100dvh">
        <Loader />
      </Center>
    );
  }
  if (!me.user) return <Login signup={me.signup} onSignedIn={setMe} />;
  return (
    <Shell
      user={me.user}
      onSignedOut={() => setMe({ ...me, user: null })}
    />
  );
}
