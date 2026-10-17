import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AppShell,
  Badge,
  Burger,
  Container,
  Group,
  Loader,
  NavLink,
  Stack,
  Text,
  ThemeIcon,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconArrowsExchange,
  IconBookmark,
  IconFileSpreadsheet,
  IconLayoutDashboard,
} from '@tabler/icons-react';

import * as api from './api';
import { showError } from './notify';
import { StatusIndicator } from './components/StatusIndicator';
import { UserMenu } from './components/UserMenu';
import { ComparePage } from './pages/Compare';
import { Overview } from './pages/Overview';
import { SavedPage } from './pages/Saved';
import { Statements } from './pages/Statements';
import type { CompareRequest, Comparison, Fund, Portfolio, SavedComparison, Status, User } from './types';

export type Page = 'overview' | 'statements' | 'compare' | 'saved';
const PAGES: Page[] = ['overview', 'statements', 'compare', 'saved'];

const pageFromHash = (): Page => {
  const p = window.location.hash.replace(/^#\/?/, '') as Page;
  return PAGES.includes(p) ? p : 'overview';
};

/** The comparison being set up on the Compare page. It lives here so it survives
 *  switching pages. */
export interface CompareState {
  selected: string[];
  alt: Fund | null;
  excludeSells: boolean;
}

interface Props {
  user: User;
  onSignedOut: () => void;
}

export function Shell({ user, onSignedOut }: Props) {
  const [navOpen, { toggle: toggleNav, close: closeNav }] = useDisclosure();
  const [page, setPageState] = useState<Page>(pageFromHash);
  const [status, setStatus] = useState<Status | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [saved, setSaved] = useState<SavedComparison[]>([]);
  const [setup, setSetup] = useState<CompareState>({ selected: [], alt: null, excludeSells: false });
  const [result, setResult] = useState<Comparison | null>(null);
  const [running, setRunning] = useState(false);
  const [autoRun, setAutoRun] = useState(false);

  const go = useCallback(
    (p: Page) => {
      window.location.hash = `/${p}`;
      closeNav();
    },
    [closeNav],
  );

  useEffect(() => {
    const onHash = () => setPageState(pageFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  // NAV data status; poll while the database is still being built.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      api
        .getStatus()
        .then((s) => {
          setStatus(s);
          if (!s.ready) timer = setTimeout(load, 10_000);
        })
        .catch(() => (timer = setTimeout(load, 10_000)));
    load();
    return () => clearTimeout(timer);
  }, []);

  const ready = status?.ready ?? false;

  useEffect(() => {
    if (!ready) return;
    api.getPortfolio().then(setPortfolio).catch(showError);
    api.getSaved().then(setSaved).catch(showError);
  }, [ready]);

  // Drop selected funds that no longer exist after a statement is removed.
  const updatePortfolio = useCallback((p: Portfolio) => {
    setPortfolio(p);
    const names = new Set(p.funds.map((f) => f.name));
    setSetup((s) => ({ ...s, selected: s.selected.filter((n) => names.has(n)) }));
  }, []);

  const selectedFunds = useMemo(
    () => portfolio?.funds.filter((f) => setup.selected.includes(f.name)) ?? [],
    [portfolio, setup.selected],
  );
  const allMatched = selectedFunds.length > 0 && selectedFunds.every((f) => f.match);
  const sellsInScope = selectedFunds.some((f) => f.n_sells > 0);

  const request: CompareRequest | null = useMemo(
    () =>
      allMatched && setup.alt
        ? {
            funds: setup.selected,
            alt_code: setup.alt.code,
            exclude_sells: sellsInScope && setup.excludeSells,
          }
        : null,
    [allMatched, setup, sellsInScope],
  );

  // A shown result goes stale when its inputs change, including a fund's matched scheme.
  const resultKey = JSON.stringify([request, selectedFunds.map((f) => f.match?.code)]);
  useEffect(() => setResult(null), [resultKey]);

  const run = useCallback(async () => {
    if (!request) return;
    setRunning(true);
    try {
      setResult(await api.compare(request));
    } catch (e) {
      showError(e);
    } finally {
      setRunning(false);
    }
  }, [request]);

  useEffect(() => {
    if (autoRun && request) {
      setAutoRun(false);
      run();
    }
  }, [autoRun, request, run]);

  const compareFunds = (names: string[]) => {
    setSetup((s) => ({ ...s, selected: names }));
    go('compare');
  };

  const openSaved = async (s: SavedComparison) => {
    try {
      const alt = await api.getFund(s.params.alt_code);
      setSetup({ selected: s.params.funds, alt, excludeSells: s.params.exclude_sells });
      setAutoRun(true);
      go('compare');
    } catch (e) {
      showError(e);
    }
  };

  const nav = [
    { page: 'overview' as Page, label: 'Overview', icon: IconLayoutDashboard },
    {
      page: 'statements' as Page,
      label: 'Statements',
      icon: IconFileSpreadsheet,
      count: portfolio?.files.length,
    },
    { page: 'compare' as Page, label: 'Compare', icon: IconArrowsExchange },
    { page: 'saved' as Page, label: 'Saved comparisons', icon: IconBookmark, count: saved.length },
  ];

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !navOpen } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={navOpen} onClick={toggleNav} hiddenFrom="sm" size="sm" />
            <ThemeIcon size={32} radius="md">
              <IconArrowsExchange size={20} />
            </ThemeIcon>
            <Text fw={650} size="lg" visibleFrom="xs">
              MF Switch Simulator
            </Text>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <StatusIndicator status={status} />
            <UserMenu user={user} onSignedOut={onSignedOut} />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <Stack gap={4}>
          {nav.map((item) => (
            <NavLink
              key={item.page}
              className="nav-link"
              href={`#/${item.page}`}
              label={item.label}
              leftSection={<item.icon size={18} stroke={1.7} />}
              rightSection={
                item.count ? (
                  <Badge size="sm" variant="light" circle={item.count < 10}>
                    {item.count}
                  </Badge>
                ) : undefined
              }
              active={page === item.page}
              onClick={(e) => {
                e.preventDefault();
                go(item.page);
              }}
            />
          ))}
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main className="app-main">
        <Container size="xl" px={{ base: 0, sm: 'md' }} py="md">
          {!status ? null : !ready ? (
            <Alert color="accent" icon={<Loader size={16} />} title="Preparing the NAV database">
              The fund list and NAV history are being downloaded and indexed. The first start
              takes a few minutes; this page updates by itself.
            </Alert>
          ) : !portfolio ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : page === 'overview' ? (
            <Overview
              portfolio={portfolio}
              saved={saved}
              onPortfolio={updatePortfolio}
              onCompare={compareFunds}
              onOpenSaved={openSaved}
              go={go}
            />
          ) : page === 'statements' ? (
            <Statements portfolio={portfolio} onPortfolio={updatePortfolio} />
          ) : page === 'compare' ? (
            <ComparePage
              portfolio={portfolio}
              onPortfolio={updatePortfolio}
              status={status}
              setup={setup}
              onSetup={setSetup}
              request={request}
              sellsInScope={sellsInScope}
              result={result}
              running={running}
              onRun={run}
              onSaved={setSaved}
              go={go}
            />
          ) : (
            <SavedPage saved={saved} onSaved={setSaved} onOpen={openSaved} go={go} />
          )}
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
