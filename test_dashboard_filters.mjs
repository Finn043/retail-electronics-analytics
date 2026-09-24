import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('./dashboard/index.html', import.meta.url), 'utf8');
const data = html.match(/<script type="application\/json" id="product-data">([^<]*)<\/script>/)?.[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(data && script, 'generated dashboard must include product data and filters');
assert.equal(JSON.parse(data).length, 10378);

function node(tag = 'div', value = '') {
  return {
    tag, value, textContent: '', children: [], hidden: false, listeners: {},
    addEventListener(event, callback) { this.listeners[event] = callback; },
    append(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; },
  };
}

const elements = {
  '#product-data': { textContent: data },
  '#product-search': node('input'),
  '#minimum-reviews': node('select', '0'),
  '#rating-band': node('select', 'all'),
  '#quality-flag': node('select'),
  '#product-results': node('tbody'),
  '#product-count': node('p'),
  '#load-more': node('button'),
};
const document = {
  querySelector(selector) { return elements[selector]; },
  createElement: node,
  createDocumentFragment() { return node('fragment'); },
};
vm.runInNewContext(script, { document });

const count = () => elements['#product-count'].textContent;
assert.match(count(), /Showing 20 of 10,378 matching products/);
elements['#minimum-reviews'].value = '500';
elements['#minimum-reviews'].listeners.change();
assert.match(count(), /Showing 20 of 28 matching products/);
elements['#quality-flag'].value = 'high_volume_low_rating';
elements['#quality-flag'].listeners.change();
assert.match(count(), /Showing 0 of 0 matching products/);
elements['#minimum-reviews'].value = '0';
elements['#minimum-reviews'].listeners.change();
assert.match(count(), /Showing 7 of 7 matching products/);
elements['#quality-flag'].value = '';
elements['#quality-flag'].listeners.change();
elements['#product-search'].value = 'B0002L5R78';
elements['#product-search'].listeners.input();
assert.match(count(), /Showing 1 of 1 matching products/);
elements['#product-search'].value = '';
elements['#product-search'].listeners.input();
elements['#rating-band'].value = 'high';
elements['#rating-band'].listeners.change();
const highRated = JSON.parse(data).filter((product) => product.avg_rating >= 4.5).length;
assert.equal(count(), `Showing 20 of ${highRated.toLocaleString('en-US')} matching products`);
elements['#rating-band'].value = 'all';
elements['#rating-band'].listeners.change();
elements['#load-more'].listeners.click();
assert.match(count(), /Showing 40 of 10,378 matching products/);
