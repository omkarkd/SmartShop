document.addEventListener('DOMContentLoaded', () => {
  const isLoginPage = document.getElementById('login-form');
  const isDashboard = document.getElementById('cart-panel');

  if (isLoginPage) {
    initAuthPage();
  }
  if (isDashboard) {
    const token = sessionStorage.getItem('token') || localStorage.getItem('token');
    if (!token) {
      window.location.href = '/';
      return;
    }
    const stored = sessionStorage.getItem('user') || localStorage.getItem('user');
    const user = JSON.parse(stored || '{}');
    document.getElementById('user-name').textContent = user.name || 'User';
  }
});

function _storeAuth(token, user, remember) {
  if (remember) {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('user');
  } else {
    sessionStorage.setItem('token', token);
    sessionStorage.setItem('user', JSON.stringify(user));
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }
}

function initAuthPage() {
  let isLogin = false;

  const signupForm = document.getElementById('signup-form');
  const loginForm = document.getElementById('login-form');
  const toggleText = document.getElementById('auth-toggle-text');
  const toggleLink = document.getElementById('auth-toggle-link');
  const authError = document.getElementById('auth-error');

  function showError(msg) {
    authError.textContent = msg;
    authError.style.display = 'block';
  }

  function clearError() {
    authError.style.display = 'none';
  }

  toggleLink.addEventListener('click', (e) => {
    e.preventDefault();
    clearError();
    isLogin = !isLogin;
    signupForm.style.display = isLogin ? 'none' : 'block';
    loginForm.style.display = isLogin ? 'block' : 'none';
    toggleText.textContent = isLogin ? "Don't have an account?" : 'Already have an account?';
    toggleLink.textContent = isLogin ? 'Create Account' : 'Sign In';
  });

  signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();
    const name = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    if (password.length < 6) {
      showError('Password must be at least 6 characters');
      return;
    }
    try {
      const result = await api('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      });
      if (result.error) {
        showError(result.error);
        return;
      }
      _storeAuth(result.token, result.user, true);
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('Connection error. Is the server running?');
    }
  });

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const remember = document.getElementById('remember-me').checked;
    try {
      const result = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password, remember_me: remember }),
      });
      if (result.error) {
        showError(result.error);
        return;
      }
      _storeAuth(result.token, result.user, remember);
      window.location.href = '/dashboard.html';
    } catch (err) {
      showError('Connection error. Is the server running?');
    }
  });
}

// Dashboard logout
document.addEventListener('DOMContentLoaded', () => {
  const logoutBtn = document.getElementById('logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
      _clearAuth();
      window.location.href = '/';
    });
  }
});
