/**
 * app_console 统一 API 层：CSRF、请求封装、通用工具
 * 约定：后端返回 { errorCode: 0, message?, data? }，errorCode !== 0 为失败
 */
(function () {
  'use strict';

  function getCsrfToken() {
    const el = document.querySelector('input[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function getCsrfHeaders() {
    const h = {'Content-Type': 'application/json'};
    const t = getCsrfToken();
    if (t) h['X-CSRFToken'] = t;
    return h;
  }

  function escapeHtml(s) {
    if (s == null || s === '') return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function parseResponse(j) {
    if (j.errorCode !== 0) throw new Error(j.message || '请求失败');
    return j.data;
  }

  function apiGet(url) {
    return fetch(url, { method: 'GET', credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(parseResponse);
  }

  function apiPost(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: getCsrfHeaders(),
      body: typeof body === 'string' ? body : JSON.stringify(body || {}),
      credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(parseResponse);
  }

  function apiPut(url, body) {
    return fetch(url, {
      method: 'PUT',
      headers: getCsrfHeaders(),
      body: typeof body === 'string' ? body : JSON.stringify(body || {}),
      credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(parseResponse);
  }

  function apiDelete(url) {
    return fetch(url, {
      method: 'DELETE',
      headers: getCsrfHeaders(),
      credentials: 'same-origin',
    })
      .then(function (r) { return r.json(); })
      .then(parseResponse);
  }

  window.ConsoleApi = {
    getCsrfToken: getCsrfToken,
    getCsrfHeaders: getCsrfHeaders,
    escapeHtml: escapeHtml,
    apiGet: apiGet,
    apiPost: apiPost,
    apiPut: apiPut,
    apiDelete: apiDelete,
  };
})();
