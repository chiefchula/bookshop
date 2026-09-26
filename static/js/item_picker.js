/**
 * Reusable item autocomplete.
 * Usage in HTML:
 *   <div class="item-picker" data-source="/api/items/search?stocked=1">
 *     <input type="text" class="form-control item-picker-input" placeholder="Search...">
 *     <input type="hidden" class="item-picker-id" name="item_id">
 *     <input type="hidden" class="item-picker-price" name="unit_price">
 *     <div class="list-group item-picker-results position-absolute"></div>
 *   </div>
 *
 * The element gets populated with a data-label attribute after selection
 * so other code can display what's picked.
 */
(function () {
  function attach(picker) {
    const input   = picker.querySelector('.item-picker-input');
    const hidden  = picker.querySelector('.item-picker-id');
    const results = picker.querySelector('.item-picker-results');
    const source  = picker.dataset.source || '/api/items/search';

    let debounceTimer = null;
    let lastQuery = '';

    function hideResults() {
      results.innerHTML = '';
      results.style.display = 'none';
    }

    function render(items) {
      if (!items.length) {
        results.innerHTML = '<div class="list-group-item small text-muted">No matches</div>';
        results.style.display = 'block';
        return;
      }
      results.innerHTML = items.map(it => `
        <button type="button" class="list-group-item list-group-item-action"
                data-id="${it.id}"
                data-title="${it.title.replace(/"/g, '&quot;')}"
                data-price="${it.price}"
                data-qty="${it.quantity}"
                data-unit="${it.unit}">
          <div class="d-flex justify-content-between">
            <span><strong>${it.title}</strong>${it.brand ? ' <span class="text-muted">— ' + it.brand + '</span>' : ''}</span>
            <span class="text-muted small">
              ${it.stocked ? 'qty ' + it.quantity : 'not stocked'} · KES ${it.price.toFixed(2)}
            </span>
          </div>
        </button>
      `).join('');
      results.style.display = 'block';
    }

    function search(q) {
      const url = source + (source.includes('?') ? '&' : '?') + 'q=' + encodeURIComponent(q);
      fetch(url, { headers: { 'Accept': 'application/json' } })
        .then(r => r.json())
        .then(render)
        .catch(() => hideResults());
    }

    input.addEventListener('input', () => {
      const q = input.value.trim();
      if (q === lastQuery) return;
      lastQuery = q;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => search(q), 180);
    });

    input.addEventListener('focus', () => {
      if (input.value.trim().length >= 1) search(input.value.trim());
    });

    results.addEventListener('click', (e) => {
      const btn = e.target.closest('button[data-id]');
      if (!btn) return;
      hidden.value = btn.dataset.id;
      input.value  = btn.dataset.title;
      picker.dataset.selectedId = btn.dataset.id;
      picker.dataset.selectedPrice = btn.dataset.price;
      picker.dataset.selectedQty = btn.dataset.qty;
      hideResults();

      // Notify any listener
      picker.dispatchEvent(new CustomEvent('item-selected', {
        detail: {
          id: btn.dataset.id,
          title: btn.dataset.title,
          price: parseFloat(btn.dataset.price),
          quantity: parseInt(btn.dataset.qty, 10),
        }
      }));
    });

    document.addEventListener('click', (e) => {
      if (!picker.contains(e.target)) hideResults();
    });
  }

  document.querySelectorAll('.item-picker').forEach(attach);
})();