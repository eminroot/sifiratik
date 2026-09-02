import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, ClipboardList, Search, X } from 'lucide-react';

import { useApp } from '../App.jsx';
import { query, useApi } from '../lib/api.js';
import { levelLabel, lira, num, sectorLabel, sizeLabel, statusLabel, tonnes } from '../lib/format.js';
import { useT } from '../lib/i18n.jsx';
import QueueTable from '../components/QueueTable.jsx';
import { PageHead, Resource } from '../components/ui.jsx';

const PAGE_SIZE = 50;

const SORTS = ['priority', 'gap', 'shortfall', 'quality', 'name'];
const QUALITY = ['HIGH', 'MEDIUM', 'LOW'];

export default function Queue() {
  const { period, reference } = useApp();
  const t = useT();

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
      <PageHead eyebrow={t('queue.eyebrow')} icon={ClipboardList} title={t('queue.title')} />

      <div className="filters">
        <div className="filter-search">
          <Search size={14} strokeWidth={1.9} />
          <input
            type="search"
            value={search}
            placeholder={t('queue.search')}
            onChange={(event) => setSearch(event.target.value)}
            aria-label={t('queue.searchLabel')}
          />
        </div>

        <Select value={filters.level} onChange={set('level')} label={t('queue.allPriorities')}>
          {(reference?.priority_levels ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {levelLabel(option.value)} ({num(option.count)})
            </option>
          ))}
        </Select>

        <Select value={filters.sector} onChange={set('sector')} label={t('queue.allSectors')}>
          {(reference?.sectors ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {sectorLabel(option.value)}
            </option>
          ))}
        </Select>

        <Select value={filters.region} onChange={set('region')} label={t('queue.allProvinces')}>
          {(reference?.regions ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label} ({num(option.count)})
            </option>
          ))}
        </Select>

        <Select value={filters.size} onChange={set('size')} label={t('queue.anySize')}>
          {(reference?.company_sizes ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {sizeLabel(option.value)}
            </option>
          ))}
        </Select>

        <Select value={filters.status} onChange={set('status')} label={t('queue.anyStatus')}>
          {(reference?.review_statuses ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {statusLabel(option.value)}
            </option>
          ))}
        </Select>

        <Select value={filters.quality} onChange={set('quality')} label={t('queue.anyEvidence')}>
          {QUALITY.map((value) => (
            <option key={value} value={value}>
              {t(`queue.evidence.${value}`)}
            </option>
          ))}
        </Select>

        <Select
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          label={null}
          fallbackLabel={t('queue.sortOrder')}
          always
        >
          {SORTS.map((value) => (
            <option key={value} value={value}>
              {t('queue.sortBy', { what: t(`queue.sort.${value}`) })}
            </option>
          ))}
        </Select>

        {active && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={clear}>
            <X size={13} strokeWidth={1.9} />
            {t('common.clear')}
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
                  ? t('queue.noMatch')
                  : t('queue.pageRange', {
                      from: num(data.offset + 1),
                      to: num(Math.min(data.offset + data.limit, data.total)),
                      total: num(data.total),
                    })}
                {data.items.length > 0 && (
                  <>
                    {' · '}
                    {t('queue.pageTotals', {
                      tonnes: tonnes(
                        data.items.reduce((sum, item) => sum + item.shortfall_tonnage, 0),
                      ),
                      value: lira(
                        data.items.reduce((sum, item) => sum + item.estimated_gekap_gap_try, 0),
                      ),
                    })}
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
                  {t('common.previous')}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={offset + PAGE_SIZE >= data.total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}
                >
                  {t('common.next')}
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

function Select({ value, onChange, label, children, always = false, fallbackLabel }) {
  return (
    <select
      className={`filter-select${value || always ? ' on' : ''}`}
      value={value}
      onChange={onChange}
      aria-label={label ?? fallbackLabel}
    >
      {label && <option value="">{label}</option>}
      {children}
    </select>
  );
}
