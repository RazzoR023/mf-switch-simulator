import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, Checkbox, Container, Divider, Group, Stack } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBolt } from '@tabler/icons-react';

import * as api from './api';
import { AlternateStep } from './components/AlternateStep';
import { EmptyState } from './components/EmptyState';
import { FundsStep } from './components/FundsStep';
import { Header, StatusBanner } from './components/Header';
import { MatchStep } from './components/MatchStep';
import { Results } from './components/Results';
import { UploadStep } from './components/UploadStep';
import type { CompareRequest, Comparison, Coverage, Fund, Status, TradebookResult } from './types';

const fileKey = (f: File) => `${f.name}|${f.size}|${f.lastModified}`;

function showError(e: unknown) {
  notifications.show({
    color: 'red',
    title: 'Something went wrong',
    message: e instanceof Error ? e.message : String(e),
  });
}

export function App() {
  const [status, setStatus] = useState<Status | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [parsed, setParsed] = useState<TradebookResult | null>(null);
  const [parsing, setParsing] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<Record<string, Fund>>({});
  const [alt, setAlt] = useState<Fund | null>(null);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [excludeSells, setExcludeSells] = useState(false);
  const [result, setResult] = useState<Comparison | null>(null);
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Data status; poll while the database is still being built.
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

  // Re-parse whenever the file list changes: the server dedupes across all files.
  useEffect(() => {
    if (!files.length) {
      setParsed(null);
      return;
    }
    let cancelled = false;
    setParsing(true);
    api
      .parseTradebooks(files)
      .then((r) => {
        if (cancelled) return;
        setParsed(r);
        // Keep selections that still exist in the new set of files.
        const names = new Set(r.funds.map((f) => f.name));
        setSelected((s) => s.filter((n) => names.has(n)));
      })
      .catch((e) => !cancelled && showError(e))
      .finally(() => !cancelled && setParsing(false));
    return () => {
      cancelled = true;
    };
  }, [files]);

  const selectedFunds = useMemo(
    () => parsed?.funds.filter((f) => selected.includes(f.name)) ?? [],
    [parsed, selected],
  );
  const actualCodes = useMemo(() => {
    const codes: Record<string, number> = {};
    for (const f of selectedFunds) {
      const m = overrides[f.name] ?? f.match;
      if (m) codes[f.name] = m.code;
    }
    return codes;
  }, [selectedFunds, overrides]);
  const allMatched = selectedFunds.length > 0 && Object.keys(actualCodes).length === selectedFunds.length;
  const sellsInScope = selectedFunds.some((f) => f.n_sells > 0);

  const request: CompareRequest | null = useMemo(
    () =>
      parsed && allMatched && alt
        ? {
            transactions: parsed.transactions,
            funds: selected,
            actual_codes: actualCodes,
            alt_code: alt.code,
            exclude_sells: sellsInScope && excludeSells,
          }
        : null,
    [parsed, allMatched, alt, selected, actualCodes, sellsInScope, excludeSells],
  );

  // Any change to the inputs makes a shown result stale.
  useEffect(() => setResult(null), [request]);

  // NAV coverage of the alternate fund for the selected transactions.
  useEffect(() => {
    if (!parsed || !alt || !selected.length) {
      setCoverage(null);
      return;
    }
    let cancelled = false;
    setCoverageLoading(true);
    api
      .getCoverage(parsed.transactions, selected, alt.code)
      .then((c) => !cancelled && setCoverage(c))
      .catch((e) => !cancelled && showError(e))
      .finally(() => !cancelled && setCoverageLoading(false));
    return () => {
      cancelled = true;
    };
  }, [parsed, alt, selected]);

  const addFiles = useCallback((dropped: File[]) => {
    setFiles((cur) => {
      const seen = new Set(cur.map(fileKey));
      return [...cur, ...dropped.filter((f) => !seen.has(fileKey(f)))];
    });
  }, []);

  const run = async () => {
    if (!request) return;
    setRunning(true);
    try {
      setResult(await api.compare(request));
    } catch (e) {
      showError(e);
    } finally {
      setRunning(false);
    }
  };

  const download = async () => {
    if (!request) return;
    setDownloading(true);
    try {
      await api.downloadReport(request);
    } catch (e) {
      showError(e);
    } finally {
      setDownloading(false);
    }
  };

  const ready = status?.ready ?? false;

  return (
    <Container size="lg" py="xl">
      <Stack gap="xl">
        <Header />
        <StatusBanner status={status} />

        {ready && (
          <>
            <UploadStep
              files={files}
              parsed={parsed}
              loading={parsing}
              onAdd={addFiles}
              onRemove={(f) => setFiles((cur) => cur.filter((x) => x !== f))}
            />

            {!files.length && <EmptyState />}

            {parsed && parsed.funds.length > 0 && (
              <FundsStep
                funds={parsed.funds}
                transactions={parsed.transactions}
                selected={selected}
                onChange={setSelected}
              />
            )}

            {selectedFunds.length > 0 && (
              <MatchStep
                funds={selectedFunds}
                overrides={overrides}
                onOverride={(name, fund) =>
                  setOverrides((cur) => {
                    const next = { ...cur };
                    if (fund) next[name] = fund;
                    else delete next[name];
                    return next;
                  })
                }
              />
            )}

            {allMatched && (
              <AlternateStep
                fundsWithNav={status?.funds_with_nav}
                value={alt}
                onChange={setAlt}
                coverage={coverage}
                coverageLoading={coverageLoading}
              />
            )}

            {request && (
              <>
                <Divider />
                <Group justify="space-between">
                  {sellsInScope ? (
                    <Checkbox
                      label="Exclude sells (treat every bought unit as still held)"
                      checked={excludeSells}
                      onChange={(e) => setExcludeSells(e.currentTarget.checked)}
                    />
                  ) : (
                    <span />
                  )}
                  <Button
                    size="md"
                    leftSection={<IconBolt size={18} />}
                    loading={running}
                    onClick={run}
                  >
                    Run comparison
                  </Button>
                </Group>
              </>
            )}

            {result && <Results result={result} downloading={downloading} onDownload={download} />}
          </>
        )}
      </Stack>
    </Container>
  );
}
