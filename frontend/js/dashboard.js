let currentRetailer = '';
let currentCategory = '';
let currentBrand = '';
let currentProducts = [];

document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('cart-panel')) return;

  loadCart();
  loadCategories();
  loadBrands();

  document.getElementById('search-btn').addEventListener('click', performSearch);
  document.getElementById('search-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });

  document.getElementById('nectar-toggle').addEventListener('change', () => {
    if (currentProducts.length) renderNormalizedProducts(currentProducts);
  });

  document.getElementById('category-dropdown').addEventListener('change', (e) => {
    currentCategory = e.target.value;
    if (currentCategory) {
      loadProductsByCategory(currentCategory, currentRetailer === 'common' ? '' : currentRetailer);
    } else {
      const q = document.getElementById('search-input').value.trim();
      if (q) performSearch();
    }
  });

  document.getElementById('brand-filter').addEventListener('change', (e) => {
    currentBrand = e.target.value;
    const q = document.getElementById('search-input').value.trim();
    if (q || currentCategory) {
      performSearch();
    }
  });

  document.querySelectorAll('.retailer-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.retailer-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      currentRetailer = tab.dataset.retailer;
      const q = document.getElementById('search-input').value.trim();
      if (currentCategory) {
        loadProductsByCategory(currentCategory, currentRetailer === 'common' ? '' : currentRetailer);
      } else if (q) {
        performSearch();
      } else {
        document.getElementById('product-container').innerHTML =
          '<div class="loading"><div class="spinner"></div><p>Search for products or browse by category...</p></div>';
      }
    });
  });

  // Cart toggle
  document.getElementById('sidebar-show-cart').addEventListener('click', toggleCart);
  document.getElementById('cart-close').addEventListener('click', toggleCart);

  // Price Analyzer
  document.getElementById('sidebar-price-analyzer').addEventListener('click', () => {
    document.getElementById('price-analyzer-modal').classList.add('visible');
  });
});

// ── Cart Toggle ──────────────────────────────────────────────────
function toggleCart() {
  document.getElementById('cart-panel').classList.toggle('open');
  document.getElementById('cart-overlay').classList.toggle('visible');
}

// ── Price Analyzer ───────────────────────────────────────────────
function closePriceAnalyzer(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('price-analyzer-modal').classList.remove('visible');
}

// ── Load Categories ──────────────────────────────────────────────
async function loadCategories() {
  try {
    const data = await api('/api/products/categories');
    const select = document.getElementById('category-dropdown');
    const seen = new Set();
    data.categories.forEach(c => {
      if (seen.has(c.name)) return;
      seen.add(c.name);
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = `${c.name} (${c.retailer})`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load categories:', err);
  }
}

// ── Load Brands ──────────────────────────────────────────────────
async function loadBrands() {
  try {
    const data = await api('/api/brands/list');
    const select = document.getElementById('brand-filter');
    data.brands.slice(0, 200).forEach(b => {
      const opt = document.createElement('option');
      opt.value = b;
      opt.textContent = b;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error('Failed to load brands:', err);
  }
}

// ── Nectar helpers ───────────────────────────────────────────────
function addWithPrice(encodedUrl) {
  const url = decodeURIComponent(encodedUrl);
  const product = currentProducts.find(p => (p.url || '') === url);
  if (!product) return;
  const cb = document.getElementById('nectar-toggle');
  const useNectar = cb && cb.checked;
  const finalPrice = useNectar && product.nectar_price
    ? (typeof product.nectar_price === 'number' ? product.nectar_price : parseFloat(product.nectar_price) || product.price)
    : product.price;
  addToCart({
    url: product.url,
    retailer: product.retailer,
    name: product.product_name,
    price: finalPrice,
    brand: product.brand || '',
    image_url: product.image_url || '',
    size: product.size || '',
  });
}

function getNectarPrice(prod) {
  return prod && prod.nectar_price
    ? (typeof prod.nectar_price === 'number' ? prod.nectar_price : parseFloat(prod.nectar_price))
    : null;
}

// ── Search ───────────────────────────────────────────────────────
async function performSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;

  const container = document.getElementById('product-container');
  container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching...</p></div>';

  currentCategory = '';
  const retailer = currentRetailer === 'common' ? '' : currentRetailer;

  try {
    const params = new URLSearchParams({ q });
    if (retailer) params.set('retailer', retailer);
    if (currentBrand) params.set('brand', currentBrand);
    const data = await api(`/api/products/search?${params}`);
    renderNormalizedProducts(data.products || []);
  } catch (err) {
    container.innerHTML = '<p style="color:#c00;">Search failed. Is the server running?</p>';
  }
}

async function loadProductsByCategory(category, retailer) {
  const container = document.getElementById('product-container');
  container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading products...</p></div>';

  try {
    const params = new URLSearchParams();
    if (retailer) params.set('retailer', retailer);
    if (currentBrand) params.set('brand', currentBrand);
    const data = await api(`/api/products/category/${encodeURIComponent(category)}?${params}`);
    renderNormalizedProducts(data.products || []);
  } catch (err) {
    container.innerHTML = '<p style="color:#c00;">Failed to load category products.</p>';
  }
}

// ── Render (always normalized) ────────────────────────────────────
function renderNormalizedProducts(products) {
  const container = document.getElementById('product-container');
  currentProducts = products;

  if (!products.length) {
    container.innerHTML = '<div style="text-align:center;padding:40px;color:#999;"><p>No products found</p></div>';
    return;
  }

  const cb = document.getElementById('nectar-toggle');
  const showNectar = cb && cb.checked;

  container.innerHTML = `<div class="product-grid">${products.map(p => {
    const name = p.product_name || '';
    const brand = p.brand || '';
    const price = typeof p.price === 'number' ? p.price : parseFloat(p.price) || 0;
    const nectarPrice = getNectarPrice(p);
    const showAsNectar = showNectar && nectarPrice != null;
    const retailer = p.retailer || '';
    const size = p.size || '';
    const image = p.image_url || '';
    const url = p.url || '';
    const nectarLabel = p.nectar_price_label || '';

    const priceHtml = showAsNectar
      ? `<div class="product-price-row">
          <span class="product-price original">&pound;${price.toFixed(2)}</span>
          <span class="product-price nectar">&pound;${nectarPrice.toFixed(2)}</span>
          ${nectarLabel ? `<span class="nectar-badge">${nectarLabel}</span>` : ''}
        </div>`
      : `<div class="product-price">&pound;${price.toFixed(2)}</div>`;

    return `<div class="product-card" style="border-left:3px solid ${retailer === 'aldi' ? '#0066a1' : '#e87722'}">
      <div class="product-retailer ${retailer}">${retailer === 'aldi' ? "Aldi" : "Sainsbury's"}</div>
      ${image ? `<img class="product-image" src="${image}" alt="${name}" onerror="this.style.display='none'">` : ''}
      <div class="product-name">${name}</div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin:4px 0;">
        ${brand ? `<span class="product-brand-tag">${brand}</span>` : ''}
        ${size ? `<span class="product-size-tag">${size}</span>` : ''}
      </div>
      ${priceHtml}
      <button class="add-btn ${retailer}" onclick="addWithPrice('${encodeURIComponent(url)}')">Add to Cart</button>
    </div>`;
  }).join('')}</div>`;
}
