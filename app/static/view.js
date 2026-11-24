import {element, pretty} from './client.js';

const labels = {READY:'通过', MISMATCH:'差异待复核', PENDING:'待复核', APPROVED:'已签发', HELD:'已暂缓',
  CHANGE_CONFLICT:'时刻冲突', ORDER_CONFLICT:'顺序冲突', INTERVAL_GAP:'区间断档', INTERVAL_OVERLAP:'区间重叠',
  INVALID_PERIOD:'窗口无效', REVENUE_MISMATCH:'读回不平'};
const headers = ['业务分组', '输入行', '确认收入', '期末 MRR', '读回', '判定'];

export function badge(status) {
  return element('span', labels[status] || status, {class:'badge', 'data-result':status, title: status});
}

function readback(revenue) {
  if (!revenue) return '—';
  return revenue.ok ? '✓' : '✗';
}

function showBlockers(balance) {
  const target = document.querySelector('#blockers');
  target.replaceChildren();
  if (!balance?.blockers?.length) return;
  target.hidden = false;
  const title = element('strong', `签发受阻 · ${balance.blockers.length} 组`);
  target.append(title);
  for (const item of balance.blockers) {
    const line = element('div', undefined, {class:'blocker'});
    const keys = item.records.length ? item.records.join(', ') : (item.evidence_records.join(', ') || '—');
    line.append(document.createTextNode(`${item.case} · ${item.status} · 记录键 ${keys}`));
    target.append(line);
  }
}

export function snapshot(report, selected, stage) {
  const stats = report.intake;
  document.querySelector('[data-metric="input"]').textContent = stats.input;
  document.querySelector('[data-metric="accepted"]').textContent = stats.accepted;
  document.querySelector('[data-metric="isolated"]').textContent = stats.rejected;
  document.querySelector('[data-metric="cases"]').textContent = report.cases?.length ?? '—';
  const table = document.querySelector('#rows');
  table.replaceChildren();
  const head = element('tr');
  const body = table.createTBody();
  if (stage === 'intake') {
    head.append(...['源行', '记录键', '业务分组', '原因码'].map(title => element('th', title, {scope:'col'})));
    for (const item of stats.isolation) {
      const tr = body.insertRow();
      tr.append(...[item.line,item.record,item.case,item.reason].map(value=>element('td',value)));
    }
    if (!stats.isolation.length) body.insertRow().insertCell().textContent = '当前文件没有隔离行';
  } else {
    head.append(...headers.map(title => element('th', title, {scope:'col'})));
    for (const row of report.cases || []) {
      const tr = body.insertRow();
      const button = element('button',row.case,{type:'button','data-case':row.case,'aria-pressed':String(row.case===selected)});
      tr.insertCell().append(button);
      const rev = row.revenue;
      [row.records.length,
       rev ? rev.recognized_cents : '—',
       rev ? rev.closing_cents : '—',
       readback(rev)].forEach(value=>tr.insertCell().textContent=value);
      tr.insertCell().append(badge(row.status));
    }
  }
  table.createTHead().append(head);
  const picked = report.cases?.find(row=>row.case===selected);
  document.querySelector('#detail-title').textContent = picked ? `分组 ${picked.case}` : '采信摘要';
  let shown;
  if (picked && picked.revenue) {
    shown = {
      服务窗口: picked.revenue.window,
      期初分: picked.revenue.opening_cents,
      期末分: picked.revenue.closing_cents,
      确认分: `${picked.revenue.recognized_numerator} / ${picked.revenue.recognized_denominator} = ${picked.revenue.recognized_cents}`,
      递延分: picked.revenue.deferred_numerator,
      读回: picked.revenue.checks,
      分段: picked.revenue.segments.map(s => `${s.start}–${s.end} @ ${s.level_cents}`),
      变动: picked.revenue.movements.map(m => `${m.record} @${m.minute}#${m.sequence} ${m.kind} Δ${m.delta_cents} 确认${m.recognized}`),
    };
  } else if (picked) {
    shown = picked.blocking ?? {原因: picked.status, 记录键: picked.records};
  } else {
    shown = stats.reasons;
  }
  document.querySelector('#detail').textContent = pretty(shown);
  const revenueOk = report.revenue ? (report.revenue.verified ? '读回已验证' : '读回待核') : '';
  document.querySelector('#counts').textContent = report.balance
    ? `行数 ${report.balance.accounted}/${report.balance.input} · ${report.balance.ready} 组通过 · ${revenueOk}`
    : `采信 ${stats.accepted} 行 · 隔离 ${stats.rejected} 行`;
  showBlockers(report.balance);
}

export function history(items, active) {
  const target = document.querySelector('#history');
  target.replaceChildren();
  for (const run of items) {
    const button = element('button', run.id.slice(0,10), {'data-run':run.id,'aria-pressed':String(run.id===active),type:'button'});
    const item = element('li');
    item.append(button, badge(run.status));
    target.append(item);
  }
  if (!items.length) target.append(element('li','尚无执行批次'));
}
