import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, ClipboardList, Search, X } from 'lucide-react';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import { lira, num, tonnes } from '../lib/format.js';
import QueueTable from '../components/QueueTable.jsx';
import { PageHead, Resource } from '../components/ui.jsx';

const PAGE_SIZE = 50;

const SORTS = [
  { value: 'priority', label: 'Priority score' },
  { value: 'gap', label: 'Contribution at stake' },
  { value: 'shortfall', label: 'Unexplained tonnage' },
  { value: 'quality', label: 'Data quality' },
  { value: 'name', label: 'Company name' },
];

const QUALITY = [
  { value: 'HIGH', label: 'Well evidenced' },
  { value: 'MEDIUM', label: 'Partly evidenced' },
  { value: 'LOW', label: 'Thin evidence' },
];

export default function Queue() {
  const { period, reference } = useApp();

  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [filters, setFilters] = useState({
    level: '',
    sector: '',
    region: '',
    size: '',
    status: '',
    quality: '',
  });
  const [sort, setSort] = useState('priority');
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 260);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setOffset(0);
  }, [debounced, filters, sort, period]);

  const path = useMemo(
    () =>
      `/inspection-queue${query({
        period,
        search: debounced,
        ...filters,
        sort,
        direction: sort === 'name' ? 'asc' : 'desc',
        limit: PAGE_SIZE,
        offset,
      })}`,
    [period, debounced, filters, sort, offset],
  );

  const state = useApi(path, []);
  const active = Object.values(filters).some(Boolean) || Boolean(debounced);

  const set = (key) => (event) =>
    setFilters((current) => ({ ...current, [key]: event.target.value }));

  const clear = () => {
    setSearch('');
    setFilters({ level: '', sector: '', region: '', size: '', status: '', quality: '' });
  };

  return (
    <div className="page wide">
      <PageHead eyebrow="Operations" icon={ClipboardList} title="Inspection queue" />

      <div className="filters">
        <div className="filter-search">
          <Search size={14} strokeWidth={1.9} />
          <input
            type="search"
            value={search}
            placeholder="Company name or tax number"
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search companies"
          />
        </div>

        <Select value={filters.level} onChange={set('level')} label="All priorities">
          {(reference?.priority_levels ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label} ({option.count})
            </option>
          ))}
        </Select>

        <Select value={filters.sector} onChange={set('sector')} label="All sectors">
          {(reference?.sectors ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select value={filters.region} onChange={set('region')} label="All provinces">
          {(reference?.regions ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label} ({option.count})
            </option>
          ))}
        </Select>

        <Select value={filters.size} onChange={set('size')} label="Any size">
          {(reference?.company_sizes ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select value={filters.status} onChange={set('status')} label="Any status">
          {(reference?.review_statuses ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select value={filters.quality} onChange={set('quality')} label="Any evidence level">
          {QUALITY.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>

        <Select value={sort} onChange={(event) => setSort(event.target.value)} label={null} always>
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              Sort by {option.label.toLowerCase()}
            </option>
          ))}
        </Select>

        {active && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={clear}>
            <X size={13} strokeWidth={1.9} />
            Clear
          </button>
        )}
      </div>

      <Resource state={state} rows={2}>
        {(data) => (
          <>
            <QueueTable items={data.items} />

            <div className="pager">
              <span>
                {data.total === 0
                  ? 'No companies match'
                  : `${num(data.offset + 1)} to ${num(Math.min(data.offset + data.limit, data.total))} of ${num(data.total)}`}
                {data.items.length > 0 && (
                  <>
                    {' · '}
                    {tonnes(data.items.reduce((sum, item) => sum + item.shortfall_tonnage, 0))} and{' '}
                    {lira(
                      data.items.reduce((sum, item) => sum + item.estimated_gekap_gap_try, 0),
                    )}{' '}
                    unexplained on this page
                  </>
                )}
              </span>

              <span className="row">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                >
                  <ChevronLeft size={13} strokeWidth={1.9} />
                  Previous
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={offset + PAGE_SIZE >= data.total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  Next
                  <ChevronRight size={13} strokeWidth={1.9} />
                </button>
              </span>
            </div>
          </>
        )}
      </Resource>
    </div>
  );
}

function Select({ value, onChange, label, children, always = false }) {
  return (
    <select
      className={`filter-select${value || always ? ' on' : ''}`}
      value={value}
      onChange={onChange}
      aria-label={label ?? 'Sort order'}
    >
      {label && <option value="">{label}</option>}
      {children}
    </select>
  );
}
