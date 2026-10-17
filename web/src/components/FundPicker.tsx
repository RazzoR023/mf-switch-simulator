import { useEffect, useMemo, useState } from 'react';
import { Loader, Select, Stack, Text } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';

import { searchFunds } from '../api';
import * as fmt from '../format';
import type { Fund } from '../types';

interface Props {
  label: string;
  description?: string;
  placeholder?: string;
  value: Fund | null;
  onChange: (fund: Fund | null) => void;
  initialQuery?: string;
}

const optionLabel = (f: Fund) => `${fmt.fundTitle(f)} [${f.code}]`;

/** Searchable scheme picker. Searching happens on the server (only schemes with NAV
 *  history are offered); this component only shows the results. */
export function FundPicker({ label, description, placeholder, value, onChange, initialQuery }: Props) {
  const [search, setSearch] = useState(value ? optionLabel(value) : (initialQuery ?? ''));
  const [debounced] = useDebouncedValue(search, 200);
  const [results, setResults] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = debounced.trim();
    // Selecting an option puts its label in the search box: don't search for that.
    if (q.length < 2 || (value && q === optionLabel(value))) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    searchFunds(q, ctrl.signal)
      .then(setResults)
      .catch(() => {})
      .finally(() => !ctrl.signal.aborted && setLoading(false));
    return () => ctrl.abort();
  }, [debounced, value]);

  const byCode = useMemo(() => {
    const m = new Map(results.map((f) => [String(f.code), f]));
    if (value) m.set(String(value.code), value);
    return m;
  }, [results, value]);

  return (
    <Select
      label={label}
      description={description}
      placeholder={placeholder ?? 'Type a fund name or scheme code'}
      searchable
      clearable
      data={[...byCode.values()].map((f) => ({ value: String(f.code), label: optionLabel(f) }))}
      value={value ? String(value.code) : null}
      onChange={(code) => onChange(code ? (byCode.get(code) ?? null) : null)}
      searchValue={search}
      onSearchChange={setSearch}
      filter={({ options }) => options}
      nothingFoundMessage={
        debounced.trim().length < 2 ? 'Type at least 2 characters' : loading ? 'Searching…' : 'No scheme found'
      }
      rightSection={loading ? <Loader size="xs" /> : undefined}
      maxDropdownHeight={380}
      comboboxProps={{ shadow: 'md' }}
      renderOption={({ option }) => {
        const f = byCode.get(option.value);
        if (!f) return option.label;
        return (
          <Stack gap={0}>
            <Text size="sm">{fmt.fundTitle(f)}</Text>
            <Text size="xs" c="dimmed">
              {f.code} · {f.amc ?? 'Unknown AMC'} · NAV {fmt.day(f.nav_start)} → {fmt.day(f.nav_end)}
            </Text>
          </Stack>
        );
      }}
    />
  );
}
