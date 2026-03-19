/**
 * app_console 列表操作风格：统一复用组件
 *
 * 设计约定（列表页）：
 * - 无「详情」按钮：点击 ID 列进入详情页（RESTful，URL 带 id）
 * - 「删除」：仅用图标（垃圾桶），title="删除"
 * - 「编辑」：仅用图标（铅笔），title="编辑"
 * - ID 列：使用 listIdCell(id, detailUrl) 可点击进入详情
 * - 名称列：使用 listPlainCell(text) 仅展示，不链接
 * - 操作列：使用 listActions({ id, onEdit?, onDelete?, extra? }) 输出图标
 */
function escapeHtml(s) {
  if (s == null || s === '') return '';
  if (typeof window !== 'undefined' && window.ConsoleApi && window.ConsoleApi.escapeHtml)
    return window.ConsoleApi.escapeHtml(s);
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function listTitleCell(text, url, cssClass) {
  const display = text || '-';
  const escaped = String(display).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const escapedUrl = String(url || '').replace(/"/g, '&quot;');
  return `<td class="${cssClass || 'font-medium'}"><a href="${escapedUrl}" class="text-blue-600 hover:underline cursor-pointer">${escaped}</a></td>`;
}

/** ID 列：可点击进入详情页（RESTful URL 带 id） */
function listIdCell(id, detailUrl) {
  const display = id != null && id !== '' ? String(id) : '-';
  const escaped = String(display).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const escapedUrl = String(detailUrl || '').replace(/"/g, '&quot;');
  return `<td class="font-mono text-gray-500"><a href="${escapedUrl}" class="text-blue-600 hover:underline cursor-pointer">${escaped}</a></td>`;
}

/** 名称列：仅展示文本，不链接 */
function listPlainCell(text) {
  const display = text != null && String(text).trim() !== '' ? String(text).trim() : '-';
  const escaped = String(display).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return `<td class="font-medium">${escaped}</td>`;
}

/**
 * 渲染操作列：编辑 + 删除 图标（无「详情」按钮）
 * @param {Object} opts
 * @param {number|string} opts.id - 记录 ID
 * @param {string} [opts.onEdit] - 编辑函数名（全局调用）
 * @param {string} [opts.onDelete] - 删除函数名（全局调用）
 * @param {Array} [opts.extra] - 额外按钮 { label, onclick } 或 { label, href }
 */
function listActions(opts) {
  const { id, onEdit, onDelete, extra = [] } = opts;
  const idStr = typeof id === 'string' ? `'${String(id).replace(/'/g, "\\'")}'` : String(id);
  let html = '<td><div class="flex gap-1 items-center">';

  (extra || []).forEach((btn) => {
    if (btn.href) {
      html += `<a href="${String(btn.href).replace(/"/g, '&quot;')}" class="btn btn-outline btn-sm">${escapeHtml(btn.label)}</a>`;
    } else {
      html += `<button onclick="${escapeHtml(btn.onclick || '')}" class="btn btn-outline btn-sm">${escapeHtml(btn.label)}</button>`;
    }
  });

  if (onEdit) {
    html += `<button type="button" onclick="${String(onEdit)}(${idStr})" class="btn btn-outline btn-sm p-1.5" title="编辑"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg></button>`;
  }
  if (onDelete) {
    html += `<button type="button" onclick="${String(onDelete)}(${idStr})" class="btn btn-danger btn-sm p-1.5" title="删除"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>`;
  }

  html += '</div></td>';
  return html;
}

// 挂到 window，避免缓存或加载顺序导致未定义
if (typeof window !== 'undefined') {
  window.listIdCell = listIdCell;
  window.listPlainCell = listPlainCell;
  window.listTitleCell = listTitleCell;
  window.listActions = listActions;
}
