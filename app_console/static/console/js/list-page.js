/**
 * app_console 列表页复用：配置驱动的表格 + 加载/空/错态
 * 依赖：ConsoleApi (api.js), list-actions.js (listIdCell, listPlainCell, listActions)
 */
(function () {
  'use strict';

  const LOADING_HTML = '<div class="p-8 text-center text-gray-500"><div class="spinner"></div><p class="mt-2">加载中...</p></div>';
  const escapeHtml = function (s) {
    return (window.ConsoleApi && window.ConsoleApi.escapeHtml) ? window.ConsoleApi.escapeHtml(s) : (s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'));
  };

  function errorHtml(msg) {
    return '<div class="p-8 text-center text-red-500">加载失败: ' + escapeHtml(msg) + '</div>';
  }
  function emptyHtml(message, hint) {
    return '<div class="empty-state"><p>' + escapeHtml(message || '暂无数据') + '</p>' + (hint ? '<p class="text-sm mt-2">' + escapeHtml(hint) + '</p>' : '') + '</div>';
  }

  function getByPath(obj, path) {
    const parts = path.split('.');
    for (let i = 0; i < parts.length; i++) {
      if (obj == null) return undefined;
      obj = obj[parts[i]];
    }
    return obj;
  }

  function renderCell(col, row, listIdCell, listPlainCell, listActions) {
    const key = col.key;
    const val = col.valueGetter ? col.valueGetter(row) : row[key];
    const type = col.type || 'text';
    if (col.customRender) return col.customRender(row);
    if (type === 'id') {
      const detailUrl = col.detailUrlTemplate ? col.detailUrlTemplate(row) : '';
      return (listIdCell || window.listIdCell)(row[key], detailUrl);
    }
    if (type === 'text') return (listPlainCell || window.listPlainCell)(val != null ? String(val).trim() : '');
    if (type === 'badge') {
      const badgeMap = col.badgeMap || {};
      const cls = badgeMap[val] || 'badge-warning';
      return '<td><span class="badge ' + cls + '">' + escapeHtml(val != null ? String(val) : '-') + '</span></td>';
    }
    if (type === 'datetime') {
      const s = val ? String(val).slice(0, 19) : '-';
      return '<td>' + escapeHtml(s) + '</td>';
    }
    if (type === 'truncate') {
      const len = col.truncateLen != null ? col.truncateLen : 80;
      const raw = val != null ? (typeof val === 'object' ? JSON.stringify(val) : String(val)) : '';
      const display = raw.length > len ? raw.slice(0, len) + '...' : raw;
      const title = raw.length > len ? ' title="' + escapeHtml(raw) + '"' : '';
      return '<td class="text-xs"' + title + '>' + escapeHtml(display || '-') + '</td>';
    }
    return '<td>' + escapeHtml(val != null ? String(val) : '-') + '</td>';
  }

  function buildTable(columns, actions) {
    const headers = columns.map(function (c) {
      return '<th>' + escapeHtml(c.label) + '</th>';
    });
    if (actions && (actions.onEdit || actions.onDelete || actions.extra && actions.extra.length)) headers.push('<th>操作</th>');
    return '<table class="data-table"><thead><tr>' + headers.join('') + '</tr></thead><tbody>';
  }

  let currentConfig = null;

  function run(config) {
    currentConfig = config;
    const containerId = config.containerId;
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = LOADING_HTML;
    const listResponseKey = config.listResponseKey || 'data';
    const totalKey = config.totalKey;
    const queryString = config.queryString != null ? config.queryString : '?limit=100';
    const url = config.apiUrl + queryString;
    window.ConsoleApi.apiGet(url)
      .then(function (data) {
        let items = getByPath(data, listResponseKey);
        if (!Array.isArray(items)) items = [];
        const total = totalKey ? getByPath(data, totalKey) : items.length;
        if (items.length === 0) {
          el.innerHTML = emptyHtml(config.emptyMessage || '暂无数据', config.emptyHint);
          return;
        }
        const listIdCell = window.listIdCell;
        const listPlainCell = window.listPlainCell;
        const listActions = window.listActions;
        let table = buildTable(config.columns, config.actions);
        items.forEach(function (row) {
          table += '<tr>';
          config.columns.forEach(function (col) {
            table += renderCell(col, row, listIdCell, listPlainCell, listActions);
          });
          if (config.actions && (config.actions.onEdit || config.actions.onDelete || (config.actions.extra && config.actions.extra.length))) {
            table += listActions({
              id: row.id,
              onEdit: config.actions.onEdit,
              onDelete: config.actions.onDelete,
              extra: config.actions.extra ? config.actions.extra.map(function (e) {
                if (e.hrefTemplate) return { label: e.label, href: e.hrefTemplate(row) };
                return e;
              }) : [],
            });
          }
          table += '</tr>';
        });
        table += '</tbody></table>';
        if (totalKey && total > items.length) table += '<p class="px-4 py-2 text-sm text-gray-500">共 ' + total + ' 条</p>';
        el.innerHTML = table;
      })
      .catch(function (e) {
        el.innerHTML = errorHtml(e && e.message ? e.message : '加载失败');
      });
  }

  function refresh() {
    if (currentConfig) run(currentConfig);
  }

  window.ConsoleListPage = {
    run: run,
    refresh: refresh,
    LOADING_HTML: LOADING_HTML,
  };
})();
