import {element} from './client.js';

function zone(target, className, text) {
  const box = element('div', undefined, {class:className});
  if (text) box.append(element('span',text));
  target.append(box);
  return box;
}

function fill(layer, value, max, label) {
  const mark = zone(layer, 'mark-piece', label);
  mark.style.setProperty('--part', `${Math.max(0,Math.min(100,100*Math.abs(value)/Math.max(1,max)))}%`);
  return mark;
}

export function visualize(report, selected) {
  const target = document.querySelector('#visual');
  const row = report.cases?.find(item=>item.case===selected && item.revenue);
  target.replaceChildren();
  if (!row) {
    target.append(element('p','该分组暂无确认值'));
    const blockers = report.balance?.blockers?.filter(item=>item.case===selected) || [];
    for (const item of blockers) {
      target.append(element('p', `${item.case} · ${item.status} · 记录键 ${item.records.join(', ') || '—'}`));
    }
    return;
  }
  const {revenue:r} = row;
  const items=[['新增',r.totals.new.recognized],['扩张',r.totals.expansion.recognized],
    ['收缩',r.totals.contraction.recognized],['流失',r.totals.churn.recognized]];
  const shelf=zone(target,'bridge-columns');
  const maximum=Math.max(1,...items.map(([,n])=>Math.abs(n)));
  items.forEach(([label,n],i)=>{
    const col=zone(shelf,`bridge-tower bridge-${i}`);
    fill(col,n,maximum,`${i>1&&n?'-':''}${n}`); col.append(element('span',label));
  });
  const tie = r.ok ? '已对平' : '未对平';
  zone(target,'bridge-total',`确认 ${r.recognized_cents} 分 · 期末 ${r.closing_cents} 分 · ${tie}`);
}
