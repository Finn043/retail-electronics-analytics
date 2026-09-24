import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./dashboard/index.html', import.meta.url), 'utf8');
const raw = html.match(/<script type="application\/json" id="dashboard-data">([^<]*)<\/script>/)?.[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(raw && script, 'generated dashboard must include its filter data and script');
const data = JSON.parse(raw);
assert.equal(data.products.length, 10378);
assert.equal(data.cube.length, 182788);

function node(tag = 'div', value = '') {
  return {
    tag, value, textContent: '', innerHTML: '', children: [], hidden: false, listeners: {},
    addEventListener(event, callback) { this.listeners[event] = callback; },
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
  };
}

const elements = Object.fromEntries([
  '#product-search', '#minimum-reviews', '#rating-filter', '#quality-flag', '#start-month', '#end-month',
  '#product-results', '#watch-results', '#product-count', '#active-filter-summary', '#load-more',
  '#reset-filters', '#kpi-reviews', '#kpi-products', '#kpi-rating', '#kpi-helpful', '#meta-window',
  '#meta-latest', '#meta-peak', '#monthly-chart', '#rating-chart', '#selection-profile'
].map((selector) => [selector, node()]));
elements['#dashboard-data'] = { textContent: raw };
elements['#minimum-reviews'].value = '0';
elements['#rating-filter'].value = '0';

const document = {
  querySelector(selector) { return elements[selector]; },
  createElement: node,
  createDocumentFragment() { return node('fragment'); },
};
vm.runInNewContext(script, { document, Intl });

assert.equal(elements['#kpi-reviews'].textContent, '250,000');
assert.equal(elements['#kpi-products'].textContent, '10,378');
assert.equal(elements['#kpi-rating'].textContent, '4.21');
assert.equal(elements['#kpi-helpful'].textContent, '50.85%');

elements['#rating-filter'].value = '1';
elements['#rating-filter'].listeners.change();
assert.equal(elements['#kpi-reviews'].textContent, '17,202');
assert.equal(elements['#kpi-rating'].textContent, '1.00');
assert.match(elements['#rating-chart'].innerHTML, /17,202/);

elements['#reset-filters'].listeners.click();
elements['#minimum-reviews'].value = '500';
elements['#minimum-reviews'].listeners.change();
assert.equal(elements['#kpi-products'].textContent, '28');
assert.notEqual(elements['#kpi-reviews'].textContent, '250,000');

elements['#reset-filters'].listeners.click();
elements['#quality-flag'].value = 'high_volume_low_rating';
elements['#quality-flag'].listeners.change();
assert.equal(elements['#kpi-products'].textContent, '7');

elements['#reset-filters'].listeners.click();
elements['#product-search'].value = 'B0002L5R78';
elements['#product-search'].listeners.input();
assert.equal(elements['#kpi-products'].textContent, '1');
assert.match(elements['#active-filter-summary'].textContent, /every KPI, chart and table reflects these filters/);

elements['#product-search'].value = 'NO-SUCH-ASIN';
elements['#product-search'].listeners.input();
assert.equal(elements['#kpi-reviews'].textContent, '0');
assert.equal(elements['#kpi-rating'].textContent, '—');
assert.match(elements['#active-filter-summary'].textContent, /No matching reviews/);

elements['#reset-filters'].listeners.click();
elements['#start-month'].value = '2014-01';
elements['#start-month'].listeners.change();
assert.match(elements['#meta-window'].textContent, /^2014-01/);
assert.notEqual(elements['#kpi-reviews'].textContent, '250,000');
