let currentCart = null;

async function loadCart() {
  try {
    currentCart = await api('/api/cart/active');
    renderCart(currentCart);
  } catch (err) {
    console.error('Failed to load cart:', err);
  }
}

async function addToCart(product) {
  try {
    const result = await api('/api/cart/add', {
      method: 'POST',
      body: JSON.stringify({
        product_url: product.url || product.product_url,
        retailer: product.retailer,
        product_name: product.name || product.product_name,
        price: product.price,
        brand: product.brand || '',
        size: product.size || '',
        category: product.category || '',
        image_url: product.image_url || product.image || '',
        price_per_unit: product.price_per_unit || '',
        is_own_brand: product.is_own_brand || false,
        match_key: product.url || product.product_url,
      }),
    });
    await loadCart();
    return result;
  } catch (err) {
    console.error('Failed to add to cart:', err);
  }
}

async function updateQuantity(itemId, quantity) {
  if (quantity < 1) {
    await removeItem(itemId);
    return;
  }
  try {
    await api(`/api/cart/item/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify({ quantity }),
    });
    await loadCart();
  } catch (err) {
    console.error('Failed to update quantity:', err);
  }
}

async function removeItem(itemId) {
  try {
    await api(`/api/cart/item/${itemId}`, {
      method: 'DELETE',
    });
    await loadCart();
  } catch (err) {
    console.error('Failed to remove item:', err);
  }
}

function updateCartBadge(n) {
  const badges = document.querySelectorAll('#cart-count, #sidebar-cart-count');
  badges.forEach(el => { el.textContent = n; });
}

function renderCart(data) {
  const body = document.getElementById('cart-body');
  const n = data.items ? data.items.length : 0;
  updateCartBadge(n);

  if (!data.items || data.items.length === 0) {
    body.innerHTML = `<div class="cart-empty">
      <p>Your cart is empty</p>
      <p style="margin-top:4px;font-size:0.85rem;color:#bbb;">Search products above and add them to compare prices</p>
    </div>`;
    return;
  }

  let itemsHtml = '';
  for (const item of data.items) {
    const size = item.size || '';
    itemsHtml += `
      <div class="cart-item">
        <div class="item-header">
          <span class="item-name">${item.product_name}</span>
          <span class="item-retailer ${item.retailer}">${item.retailer}</span>
        </div>
        ${size ? `<div class="item-size">${size}</div>` : ''}
        <div class="item-price-row">
          <span class="item-price">&pound;${item.price.toFixed(2)}</span>
          <div class="item-qty">
            <button onclick="updateQuantity('${item.id}', ${(item.quantity || 1) - 1})">&minus;</button>
            <span>${item.quantity || 1}</span>
            <button onclick="updateQuantity('${item.id}', ${(item.quantity || 1) + 1})">+</button>
          </div>
        </div>
        <button class="item-remove" onclick="removeItem('${item.id}')">Remove</button>
      </div>`;
  }

  const totals = data.totals || {};

  body.innerHTML = itemsHtml + `
    <div class="cart-totals">
      <div class="total-row aldi">
        <span>Aldi Total</span>
        <span>&pound;${(totals.aldi_total || 0).toFixed(2)}</span>
      </div>
      <div class="total-row sainsburys">
        <span>Sainsbury's Total</span>
        <span>&pound;${(totals.sainsburys_total || 0).toFixed(2)}</span>
      </div>
      ${totals.matched_aldi_total ? `
        <div class="total-row" style="margin-top:8px;font-weight:600;font-size:0.85rem;color:#666;border-top:1px solid #eee;padding-top:8px;">
          <span>Matched basket at Aldi:</span>
          <span>&pound;${totals.matched_aldi_total.toFixed(2)}</span>
        </div>
        <div class="total-row" style="font-size:0.85rem;color:#666;">
          <span>Matched basket at Sainsbury's:</span>
          <span>&pound;${totals.matched_sainsburys_total.toFixed(2)}</span>
        </div>
      ` : ''}
    </div>`;
}
