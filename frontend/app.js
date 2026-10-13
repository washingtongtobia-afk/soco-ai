/**
 * SoCo AI Social Media Strategist — Frontend Application Logic
 * Modern, clean white SaaS platform with playful, bold accents.
 *
 * Enforces:
 * 1. Single-use invitation beta access & instant functional demo testing mode.
 * 2. One-time onboarding — returning businesses never repeat industry or profile setup.
 * 3. Continuous monthly conversations — auto-greeting on new month without re-onboarding.
 * 4. Human-in-the-loop draft safeguard — no auto-posting.
 * 5. Multi-tenant isolation through Bearer token auth.
 */

// ============================================================================
// 1. Application State & Storage
// ============================================================================
const state = {
  token: localStorage.getItem('soco_token') || null,
  user: null,
  profile: null,
  currentConversation: null,
  history: [],
  captions: [],
  news: [],
  notifications: [],
  unreadNotifsCount: 0,
  selectedIndustry: null,
  activeView: 'chat', // 'chat' | 'captions' | 'news'
};

// ============================================================================
// 2. API Client Helpers
// ============================================================================
async function api(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const res = await fetch(`/api${endpoint}`, config);
    if (res.status === 401) {
      console.warn('Unauthorized request to', endpoint);
      if (state.token) {
        logoutUser(false);
        showToast('Session expired. Please sign in again.', 'warning');
      }
      throw new Error('Authentication required');
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const errorMsg = data.detail || data.message || `Request failed (${res.status})`;
      throw new Error(errorMsg);
    }
    return data;
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

// ============================================================================
// 3. UI Helpers: Toasts, Modals, Escaping
// ============================================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast-item toast-${type}`;
  
  const iconMap = {
    success: '✅',
    warning: '⚠️',
    error: '❌',
    info: '✨',
  };
  
  toast.innerHTML = `
    <span class="toast-icon">${iconMap[type] || '✨'}</span>
    <span class="toast-msg">${escapeHtml(message)}</span>
    <button class="toast-close" aria-label="Close">×</button>
  `;

  toast.querySelector('.toast-close').addEventListener('click', () => {
    toast.remove();
  });

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let formatted = escapeHtml(text);
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
  formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
  formatted = formatted.replace(/\n\n/g, '<br><br>');
  formatted = formatted.replace(/\n• (.*?)/g, '<br>• $1');
  formatted = formatted.replace(/\n- (.*?)/g, '<br>• $1');
  return formatted;
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('hidden');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('hidden');
}

// ============================================================================
// 4. Authentication, Profile & Demo Flow
// ============================================================================
async function initApp() {
  bindEvents();
  
  if (state.token) {
    try {
      await fetchBusinessProfile();
      await enterWorkspace();
      return;
    } catch (err) {
      console.warn('Failed to resume authenticated session:', err);
      logoutUser(false);
    }
  }

  showLandingView();
}

function showLandingView() {
  document.getElementById('landing-view')?.classList.remove('hidden');
  document.getElementById('workspace-view')?.classList.add('hidden');
  document.getElementById('nav-unauth-actions')?.classList.remove('hidden');
  document.getElementById('nav-auth-actions')?.classList.add('hidden');
  document.getElementById('notif-bell')?.classList.add('hidden');
}

async function fetchBusinessProfile() {
  const profile = await api('/business/profile');
  state.profile = profile;
  return profile;
}

async function enterWorkspace() {
  if (!state.profile) {
    await fetchBusinessProfile();
  }

  document.getElementById('landing-view')?.classList.add('hidden');
  document.getElementById('workspace-view')?.classList.remove('hidden');
  document.getElementById('nav-unauth-actions')?.classList.add('hidden');
  document.getElementById('nav-auth-actions')?.classList.remove('hidden');
  document.getElementById('notif-bell')?.classList.remove('hidden');

  const p = state.profile;
  const industryDisplay = formatIndustryName(p.industry);

  // Top nav
  const navBiz = document.getElementById('nav-biz-name');
  if (navBiz) navBiz.textContent = p.business_name;
  const navInd = document.getElementById('nav-biz-industry');
  if (navInd) navInd.textContent = industryDisplay;

  // Sidebar
  const sideBiz = document.getElementById('sidebar-biz-name');
  if (sideBiz) sideBiz.textContent = p.business_name;
  const sideInd = document.getElementById('sidebar-biz-industry');
  if (sideInd) sideInd.textContent = industryDisplay;
  const sideLoc = document.getElementById('sidebar-biz-location');
  if (sideLoc) sideLoc.textContent = p.business_location;
  const sideVoice = document.getElementById('sidebar-biz-voice');
  if (sideVoice) sideVoice.textContent = p.brand_voice_summary || `${p.tone} tone for ${industryDisplay}.`;

  renderHeaderPlatforms(p.preferred_platforms || []);

  await Promise.all([
    loadCurrentConversation(),
    loadConversationHistory(),
    loadNotifications(),
    loadCaptions(),
    loadNews(),
  ]);
}

function renderHeaderPlatforms(platforms) {
  const container = document.getElementById('header-platform-chips');
  if (!container) return;
  container.innerHTML = platforms
    .map(pl => {
      const cls = pl.toLowerCase() === 'linkedin' ? 'tag-linkedin' : pl.toLowerCase() === 'instagram' ? 'tag-instagram' : '';
      return `<span class="platform-tag ${cls}">${escapeHtml(pl)}</span>`;
    })
    .join('');
}

function formatIndustryName(raw) {
  const map = {
    construction_civil_engineering: 'Construction & Civil Eng',
    nonprofit: 'Nonprofit & Impact',
    restaurant: 'Restaurant & Dining',
    law_office: 'Law Office & Legal',
  };
  return map[raw] || raw;
}

function logoutUser(notify = true) {
  if (state.token) {
    api('/auth/logout', { method: 'POST' }).catch(() => {});
  }
  localStorage.removeItem('soco_token');
  state.token = null;
  state.user = null;
  state.profile = null;
  state.currentConversation = null;
  state.history = [];
  state.captions = [];
  state.news = [];
  state.notifications = [];

  showLandingView();
  if (notify) {
    showToast('Signed out successfully.', 'info');
  }
}

async function launchDemoWorkspace(industry = 'construction_civil_engineering') {
  try {
    showToast('Provisioning instant demo workspace...', 'info');
    const res = await api('/auth/demo-login', {
      method: 'POST',
      body: JSON.stringify({ industry }),
    });

    state.token = res.token;
    localStorage.setItem('soco_token', res.token);
    state.user = res.user;
    state.profile = res.profile;

    closeModal('demo-modal');
    closeModal('auth-modal');

    showToast(res.message || '⚡ Welcome to the SoCo Demo Workspace!', 'success');
    await enterWorkspace();
  } catch (err) {
    showToast(`Demo launch failed: ${err.message}`, 'error');
  }
}

// ============================================================================
// 5. Conversation & Chat Stream
// ============================================================================
async function loadCurrentConversation() {
  try {
    const conv = await api('/conversations/current');
    state.currentConversation = conv;

    const titleEl = document.getElementById('chat-month-title');
    if (titleEl) {
      titleEl.textContent = `${conv.month_name} ${conv.year} Strategy Session`;
    }

    renderChatMessages(conv.messages || []);
    scrollToBottom();
  } catch (err) {
    showToast(`Could not load conversation: ${err.message}`, 'error');
  }
}

async function loadConversationHistory() {
  try {
    const hist = await api('/conversations/history');
    state.history = hist;
    renderMonthsNav(hist);
  } catch (err) {
    console.warn('Failed to load conversation history:', err);
  }
}

function renderMonthsNav(history) {
  const nav = document.getElementById('months-nav-list');
  if (!nav) return;

  if (!history || history.length === 0) {
    nav.innerHTML = '<div class="empty-hint">No past sessions</div>';
    return;
  }

  const currentConvId = state.currentConversation?.id;

  nav.innerHTML = history.map(item => {
    const isActive = item.id === currentConvId ? 'active' : '';
    return `
      <button class="month-nav-btn ${isActive}" data-year="${item.year}" data-month="${item.month}">
        <span class="month-name">📅 ${escapeHtml(item.month_name)} ${item.year}</span>
        <span class="month-badge">${item.message_count} msgs</span>
      </button>
    `;
  }).join('');

  nav.querySelectorAll('.month-nav-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const year = btn.dataset.year;
      const month = btn.dataset.month;
      await switchMonthConversation(year, month);
    });
  });
}

async function switchMonthConversation(year, month) {
  try {
    const conv = await api(`/conversations/${year}/${month}`);
    state.currentConversation = conv;
    
    const titleEl = document.getElementById('chat-month-title');
    if (titleEl) {
      titleEl.textContent = `${conv.month_name} ${conv.year} Strategy Session`;
    }

    renderMonthsNav(state.history);
    renderChatMessages(conv.messages || []);
    scrollToBottom();
    switchToView('chat');
    showToast(`Loaded ${conv.month_name} ${conv.year} conversation.`, 'info');
  } catch (err) {
    showToast(`Error switching month: ${err.message}`, 'error');
  }
}

function renderChatMessages(messages) {
  const stream = document.getElementById('chat-messages-stream');
  if (!stream) return;

  stream.innerHTML = '';

  if (!messages || messages.length === 0) {
    stream.innerHTML = `
      <div class="empty-stream-notice">
        <div class="spark-icon">✨</div>
        <h3>Begin your monthly strategy conversation</h3>
        <p>Tell SoCo what milestones, promotions, or job site highlights you have coming up this month.</p>
      </div>
    `;
    return;
  }

  messages.forEach(msg => {
    const msgEl = createMessageElement(msg);
    stream.appendChild(msgEl);
  });
}

function createMessageElement(msg) {
  const wrapper = document.createElement('div');
  const isModel = msg.role === 'model';
  wrapper.className = `chat-msg-row ${isModel ? 'msg-model' : 'msg-user'}`;

  const avatar = isModel
    ? `<div class="preview-avatar soco-avatar">SoCo</div>`
    : `<div class="preview-avatar user-avatar">You</div>`;

  let cardHtml = '';
  if (msg.card_type === 'observances' && msg.card_data) {
    cardHtml = renderObservancesCard(msg.card_data);
  } else if (msg.card_type === 'captions' && msg.card_data) {
    cardHtml = renderCaptionsCard(msg.card_data);
  } else if (msg.card_type === 'news' && msg.card_data) {
    cardHtml = renderNewsCard(msg.card_data);
  }

  wrapper.innerHTML = `
    ${avatar}
    <div class="msg-bubble-wrap">
      <div class="msg-bubble">
        <div class="msg-content">${formatMarkdown(msg.content)}</div>
        ${cardHtml}
      </div>
      <span class="msg-timestamp">${formatTime(msg.created_at)}</span>
    </div>
  `;

  attachCardEvents(wrapper);
  return wrapper;
}

function renderObservancesCard(data) {
  const observances = data.observances || [];
  if (observances.length === 0) return '';

  const itemsHtml = observances.map(obs => `
    <div class="observance-badge-item">
      <span class="obs-icon">🎉</span>
      <div class="obs-text">
        <strong>${escapeHtml(obs.name)}</strong>
        <span class="obs-date">${obs.day ? `${data.month_name} ${obs.day}` : 'Month-long'}</span>
        <p class="obs-desc">${escapeHtml(obs.description || '')}</p>
      </div>
    </div>
  `).join('');

  return `
    <div class="rich-card observances-card">
      <div class="card-header-bar">
        <span class="card-title">🗓️ Key Observances & Themes for ${escapeHtml(data.month_name || '')} ${escapeHtml(data.year || '')}</span>
      </div>
      <div class="observances-grid">
        ${itemsHtml}
      </div>
      <div class="card-footer-tip">
        💡 <em>Ask SoCo to craft a post celebrating any of these observances!</em>
      </div>
    </div>
  `;
}

function renderCaptionsCard(data) {
  // 1. Single Caption or List of Standalone Captions
  if (data.captions && Array.isArray(data.captions) && data.captions.length > 0) {
    const count = data.captions.length;
    const capsHtml = data.captions.map(cap => renderSingleCaptionSnippet(cap)).join('');
    return `
      <div class="rich-card captions-plan-card single-caption-container">
        <div class="card-header-bar">
          <div class="plan-header-title">
            <span class="plan-badge">${count === 1 ? '✨ Caption Draft' : 'Draft Concepts'}</span>
            <strong>${count === 1 ? 'Generated Social Media Post' : `${count} Draft Captions`}</strong>
          </div>
          <span class="total-caps-count">${count === 1 ? '1 Post Draft' : `${count} Posts`}</span>
        </div>
        <div class="plan-captions-single-list">
          ${capsHtml}
        </div>
        <div class="card-footer-tip">
          🔒 <strong>Human-in-the-Loop</strong>: All drafts require human review before publishing. Say <em>"Make it shorter"</em> or <em>"Make it more exciting"</em> to revise!
        </div>
      </div>
    `;
  }

  // 2. Full Monthly Strategy Plan (Grouped by Weeks)
  const plan = data.plan;
  if (!plan) return '';

  const captionsByWeek = plan.captions_by_week || {};
  let weeksHtml = '';

  for (const [weekNum, captions] of Object.entries(captionsByWeek)) {
    const capsHtml = captions.map(cap => renderSingleCaptionSnippet(cap)).join('');
    weeksHtml += `
      <div class="plan-week-group">
        <div class="week-title">📅 Week ${escapeHtml(weekNum)}</div>
        <div class="week-captions-list">${capsHtml}</div>
      </div>
    `;
  }

  return `
    <div class="rich-card captions-plan-card">
      <div class="card-header-bar">
        <div class="plan-header-title">
          <span class="plan-badge">Draft Concepts</span>
          <strong>${escapeHtml(plan.month_name)} ${plan.year} Strategy Drafts</strong>
        </div>
        <span class="total-caps-count">${plan.total_captions} Posts Planned</span>
      </div>
      <div class="plan-weeks-container">
        ${weeksHtml}
      </div>
      <div class="card-footer-tip">
        🔒 <strong>Human-in-the-Loop</strong>: All posts remain drafts. Copy directly or edit using the buttons above.
      </div>
    </div>
  `;
}

function renderSingleCaptionSnippet(cap) {
  const platform = cap.platform || 'General';
  const hashtags = (cap.hashtags || []).map(h => (h.startsWith('#') ? h : `#${h}`)).join(' ');
  const versionsCount = cap.version_history ? cap.version_history.length : 0;
  const currentV = cap.version_number || cap.current_version || (versionsCount + 1);
  const rawText = cap.caption_text || cap.text || '';
  const charCount = rawText.length;
  const isAi = !!cap.is_ai_generated;

  return `
    <div class="caption-snippet-card" data-caption-id="${escapeHtml(cap.id)}">
      <div class="cap-card-top">
        <div class="cap-meta-left">
          <span class="platform-pill platform-${platform.toLowerCase()}">${escapeHtml(platform)}</span>
          <span class="cap-concept-title">${escapeHtml(cap.concept_title || 'Post Draft')}</span>
        </div>
        <div class="cap-meta-right">
          ${isAi 
            ? `<span class="ai-badge live-ai" title="Live generation via Gemini 2.5 Flash">⚡ Gemini AI</span>`
            : `<span class="ai-badge simulated-ai" title="Locally simulated prototype draft">🧪 Simulated Prototype</span>`}
          ${currentV > 1 ? `<span class="version-tag" title="Revision version">v${currentV}</span>` : ''}
          <span class="cap-char-count">${charCount} chars</span>
        </div>
      </div>

      <div class="cap-text-body" id="cap-text-${escapeHtml(cap.id)}">
        ${formatMarkdown(rawText)}
      </div>

      ${hashtags ? `<div class="cap-hashtags" id="cap-tags-${escapeHtml(cap.id)}">${escapeHtml(hashtags)}</div>` : ''}

      <div class="cap-actions-bar">
        <button class="btn btn-outline-xs btn-copy-caption" data-id="${escapeHtml(cap.id)}" title="Copy text & hashtags">
          📋 Copy
        </button>
        <button class="btn btn-outline-xs btn-edit-caption" data-id="${escapeHtml(cap.id)}" title="Revise copy">
          ✏️ Edit
        </button>
        ${versionsCount > 0 ? `
          <button class="btn btn-outline-xs btn-history-caption" data-id="${escapeHtml(cap.id)}" title="View previous versions">
            🕒 History (${versionsCount})
          </button>
        ` : ''}
      </div>

      <div class="version-history-drawer hidden" id="cap-hist-${escapeHtml(cap.id)}"></div>
    </div>
  `;
}

function renderNewsCard(data) {
  const article = data.article;
  if (!article) return '';

  return `
    <div class="rich-card news-item-card" data-article-id="${escapeHtml(article.id)}">
      <div class="card-header-bar">
        <span class="news-source-tag">${escapeHtml(article.source || 'Industry News')}</span>
        <span class="news-status">${escapeHtml(article.status)}</span>
      </div>
      <h4 class="news-headline">${escapeHtml(article.title)}</h4>
      <p class="news-summary">${escapeHtml(article.summary)}</p>
      <div class="news-actions">
        <button class="btn btn-primary-sm btn-approve-news" data-id="${escapeHtml(article.id)}">
          ✅ Approve Article
        </button>
        <button class="btn btn-secondary-sm btn-reject-news" data-id="${escapeHtml(article.id)}">
          🚫 Reject (Blacklist)
        </button>
      </div>
    </div>
  `;
}

function attachCardEvents(parent) {
  parent.querySelectorAll('.btn-copy-caption').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const textEl = document.getElementById(`cap-text-${id}`);
      const tagEl = document.getElementById(`cap-tags-${id}`);
      const copyContent = `${textEl ? textEl.innerText : ''}\n\n${tagEl ? tagEl.innerText : ''}`.trim();
      navigator.clipboard.writeText(copyContent).then(() => {
        showToast('Caption copied to clipboard!', 'success');
      }).catch(() => {
        showToast('Failed to copy. Please copy manually.', 'warning');
      });
    });
  });

  parent.querySelectorAll('.btn-edit-caption').forEach(btn => {
    btn.addEventListener('click', () => {
      openCaptionEditor(btn.dataset.id);
    });
  });

  parent.querySelectorAll('.btn-history-caption').forEach(btn => {
    btn.addEventListener('click', () => {
      toggleVersionHistory(btn.dataset.id);
    });
  });

  parent.querySelectorAll('.btn-approve-news').forEach(btn => {
    btn.addEventListener('click', () => handleApproveNews(btn.dataset.id));
  });

  parent.querySelectorAll('.btn-reject-news').forEach(btn => {
    btn.addEventListener('click', () => handleRejectNews(btn.dataset.id));
  });
}

function toggleVersionHistory(captionId) {
  const drawer = document.getElementById(`cap-hist-${captionId}`);
  if (!drawer) return;

  if (!drawer.classList.contains('hidden')) {
    drawer.classList.add('hidden');
    return;
  }

  const cap = state.captions.find(c => c.id === captionId);
  if (!cap || !cap.version_history || cap.version_history.length === 0) {
    drawer.innerHTML = '<div class="empty-hist">No prior versions recorded.</div>';
    drawer.classList.remove('hidden');
    return;
  }

  drawer.innerHTML = `
    <div class="history-list-header">Previous Saved Versions:</div>
    ${cap.version_history.map(v => `
      <div class="version-entry">
        <div class="version-meta">
          <strong>Version ${v.version_number || v.version}</strong>
          <span>${formatTime(v.saved_at || v.created_at)}</span>
          ${(v.change_note || v.note) ? `<em>Note: ${escapeHtml(v.change_note || v.note)}</em>` : ''}
        </div>
        <div class="version-body">${escapeHtml(v.caption_text || v.text || '')}</div>
        <button class="btn btn-outline-xs btn-restore-v" data-id="${captionId}" data-v="${v.version_number || v.version}">
          ↺ Restore Version ${v.version_number || v.version}
        </button>
      </div>
    `).join('')}
  `;

  drawer.querySelectorAll('.btn-restore-v').forEach(rBtn => {
    rBtn.addEventListener('click', async () => {
      await restoreCaptionVersion(rBtn.dataset.id, parseInt(rBtn.dataset.v, 10));
    });
  });

  drawer.classList.remove('hidden');
}

async function restoreCaptionVersion(captionId, versionNum) {
  try {
    const updated = await api(`/captions/${captionId}/restore/${versionNum}`, { method: 'POST' });
    showToast(`Restored version ${versionNum}!`, 'success');

    const idx = state.captions.findIndex(c => c.id === captionId);
    if (idx !== -1) {
      state.captions[idx] = updated;
    }
    await loadCurrentConversation();
  } catch (err) {
    showToast(`Restore failed: ${err.message}`, 'error');
  }
}

function openCaptionEditor(captionId) {
  let cap = state.captions.find(c => c.id === captionId);
  if (!cap) {
    const textEl = document.getElementById(`cap-text-${captionId}`);
    const tagEl = document.getElementById(`cap-tags-${captionId}`);
    cap = {
      id: captionId,
      text: textEl ? textEl.innerText : '',
      hashtags: tagEl ? tagEl.innerText.split(' ').filter(Boolean) : [],
    };
  }

  document.getElementById('edit-caption-id').value = cap.id;
  document.getElementById('edit-caption-text').value = cap.caption_text || cap.text || '';
  document.getElementById('edit-caption-hashtags').value = (cap.hashtags || []).join(' ');
  document.getElementById('edit-caption-note').value = '';

  openModal('caption-edit-modal');
}

// ============================================================================
// 6. Chat Input & Message Sending
// ============================================================================
async function handleSendMessage(messageText) {
  if (!messageText || !messageText.trim()) return;

  const stream = document.getElementById('chat-messages-stream');
  const cleanText = messageText.trim();

  const userMsg = {
    role: 'user',
    content: cleanText,
    created_at: new Date().toISOString(),
  };
  stream.appendChild(createMessageElement(userMsg));
  scrollToBottom();

  const inputEl = document.getElementById('chat-input-text');
  if (inputEl) {
    inputEl.value = '';
    inputEl.style.height = 'auto';
  }

  const indicator = document.createElement('div');
  indicator.className = 'chat-msg-row msg-model typing-row';
  indicator.id = 'typing-indicator-row';
  indicator.innerHTML = `
    <div class="preview-avatar soco-avatar">SoCo</div>
    <div class="msg-bubble-wrap">
      <div class="msg-bubble typing-bubble">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-label">SoCo is strategizing...</span>
      </div>
    </div>
  `;
  stream.appendChild(indicator);
  scrollToBottom();

  try {
    const payload = {
      message: cleanText,
      year: state.currentConversation?.year,
      month: state.currentConversation?.month,
    };

    const resp = await api('/chat/message', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    document.getElementById('typing-indicator-row')?.remove();

    if (resp.message) {
      stream.appendChild(createMessageElement(resp.message));
      scrollToBottom();
    }
    await loadCaptions();
  } catch (err) {
    document.getElementById('typing-indicator-row')?.remove();
    showToast(`Could not send message: ${err.message}`, 'error');
  }
}

function scrollToBottom() {
  const stream = document.getElementById('chat-messages-stream');
  if (stream) {
    stream.scrollTop = stream.scrollHeight;
  }
}

// ============================================================================
// 7. News Approval & Platform Selection Workflow
// ============================================================================
async function loadNews() {
  try {
    const news = await api('/news');
    state.news = news;
    const badge = document.getElementById('sidebar-news-count');
    if (badge) {
      badge.textContent = news.filter(n => n.status === 'pending_review').length;
    }
  } catch (err) {
    console.warn('Failed to load news:', err);
  }
}

async function handleApproveNews(articleId) {
  try {
    const res = await api(`/news/${articleId}/approve`, { method: 'POST' });
    showToast('Article approved! Select social platforms.', 'info');
    showPlatformSelectionPrompt(articleId, res.prompt);
  } catch (err) {
    showToast(`Approval failed: ${err.message}`, 'error');
  }
}

function showPlatformSelectionPrompt(articleId, promptText) {
  const defaultPlatforms = state.profile?.preferred_platforms || ['LinkedIn', 'Instagram'];
  const userSelected = prompt(
    `${promptText || 'Which platforms would you like to draft captions for?'}\n(Comma-separated, e.g. LinkedIn, Instagram, Facebook):`,
    defaultPlatforms.join(', ')
  );

  if (!userSelected) return;

  const platformsList = userSelected.split(',').map(s => s.trim()).filter(Boolean);
  if (platformsList.length === 0) return;

  finalizeNewsPlatforms(articleId, platformsList);
}

async function finalizeNewsPlatforms(articleId, platforms) {
  try {
    const res = await api(`/news/${articleId}/select-platforms`, {
      method: 'POST',
      body: JSON.stringify({ platforms }),
    });

    showToast(res.message || 'Draft captions generated for approved article!', 'success');
    await loadCaptions();
    await loadCurrentConversation();
  } catch (err) {
    showToast(`Platform selection failed: ${err.message}`, 'error');
  }
}

async function handleRejectNews(articleId) {
  try {
    const res = await api(`/news/${articleId}/reject`, { method: 'POST' });
    showToast(res.message || 'Article rejected and blacklisted.', 'info');
    await loadNews();
  } catch (err) {
    showToast(`Rejection failed: ${err.message}`, 'error');
  }
}

// ============================================================================
// 8. Captions Management Subview
// ============================================================================
async function loadCaptions() {
  try {
    const caps = await api('/captions');
    state.captions = caps;
    const badge = document.getElementById('sidebar-caption-count');
    if (badge) badge.textContent = caps.length;
  } catch (err) {
    console.warn('Failed to load captions:', err);
  }
}

// ============================================================================
// 9. Notification Center Drawer
// ============================================================================
async function loadNotifications() {
  try {
    const data = await api('/notifications');
    state.notifications = data.notifications || [];
    state.unreadNotifsCount = data.unread_count || 0;

    const badge = document.getElementById('notif-badge');
    if (badge) {
      if (state.unreadNotifsCount > 0) {
        badge.textContent = state.unreadNotifsCount;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    renderNotificationDrawer(state.notifications);
  } catch (err) {
    console.warn('Failed to load notifications:', err);
  }
}

function renderNotificationDrawer(notifs) {
  const container = document.getElementById('notif-list');
  if (!container) return;

  if (!notifs || notifs.length === 0) {
    container.innerHTML = '<div class="empty-state">No notifications right now.</div>';
    return;
  }

  container.innerHTML = notifs.map(n => `
    <div class="notif-item ${n.read ? 'notif-read' : 'notif-unread'}" data-id="${escapeHtml(n.id)}">
      <div class="notif-top">
        <span class="notif-type">${escapeHtml(n.type)}</span>
        <span class="notif-time">${formatTime(n.created_at)}</span>
      </div>
      <div class="notif-title">${escapeHtml(n.title)}</div>
      <div class="notif-body">${escapeHtml(n.message)}</div>
      ${!n.read ? `
        <button class="btn-text-action btn-mark-notif-read" data-id="${escapeHtml(n.id)}">
          Mark as read
        </button>
      ` : ''}
    </div>
  `).join('');

  container.querySelectorAll('.btn-mark-notif-read').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await markNotificationRead(btn.dataset.id);
    });
  });
}

async function markNotificationRead(notifId) {
  try {
    await api(`/notifications/${notifId}/read`, { method: 'PUT' });
    await loadNotifications();
  } catch (err) {
    console.warn('Failed to mark read:', err);
  }
}

// ============================================================================
// 10. View Switcher (Chat vs Captions vs News)
// ============================================================================
function switchToView(viewName) {
  state.activeView = viewName;
  document.querySelectorAll('.sidebar-link').forEach(btn => btn.classList.remove('active'));

  if (viewName === 'chat') {
    document.getElementById('btn-view-chat')?.classList.add('active');
    loadCurrentConversation();
  } else if (viewName === 'captions') {
    document.getElementById('btn-view-captions')?.classList.add('active');
    renderDedicatedCaptionsView();
  } else if (viewName === 'news') {
    document.getElementById('btn-view-news')?.classList.add('active');
    renderDedicatedNewsView();
  }
}

function renderDedicatedCaptionsView() {
  const stream = document.getElementById('chat-messages-stream');
  if (!stream) return;

  if (state.captions.length === 0) {
    stream.innerHTML = `
      <div class="empty-stream-notice">
        <div class="spark-icon">📝</div>
        <h3>No Draft Captions Yet</h3>
        <p>Chat with SoCo to draft your monthly post ideas.</p>
        <button class="btn btn-primary" onclick="switchToView('chat')">Return to Chat</button>
      </div>
    `;
    return;
  }

  const capsHtml = state.captions.map(c => renderSingleCaptionSnippet(c)).join('');
  stream.innerHTML = `
    <div class="dedicated-view-container">
      <div class="dedicated-view-header">
        <h3>📝 All Saved Draft Captions (${state.captions.length})</h3>
        <p>Review and edit draft copy across your social platforms. None are auto-posted.</p>
      </div>
      <div class="captions-grid-dedicated">
        ${capsHtml}
      </div>
    </div>
  `;
  attachCardEvents(stream);
}

function renderDedicatedNewsView() {
  const stream = document.getElementById('chat-messages-stream');
  if (!stream) return;

  if (state.news.length === 0) {
    stream.innerHTML = `
      <div class="empty-stream-notice">
        <div class="spark-icon">📰</div>
        <h3>No News Articles Found</h3>
        <p>Click "Discover News" or ask SoCo in chat to find relevant industry announcements.</p>
        <button class="btn btn-primary" onclick="switchToView('chat')">Return to Chat</button>
      </div>
    `;
    return;
  }

  const newsHtml = state.news.map(n => renderNewsCard({ article: n })).join('');
  stream.innerHTML = `
    <div class="dedicated-view-container">
      <div class="dedicated-view-header">
        <h3>📰 Timely Industry News Review (${state.news.length})</h3>
        <p>Approve articles to draft relevant social posts, or reject to blacklist.</p>
      </div>
      <div class="news-list-dedicated">
        ${newsHtml}
      </div>
    </div>
  `;
  attachCardEvents(stream);
}

// ============================================================================
// 11. Event Binding & Wire-Up
// ============================================================================
function bindEvents() {
  document.getElementById('brand-logo')?.addEventListener('click', () => {
    if (state.token) {
      switchToView('chat');
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });

  // Demo buttons
  document.getElementById('btn-nav-demo')?.addEventListener('click', () => openModal('demo-modal'));
  document.getElementById('hero-try-demo-btn')?.addEventListener('click', () => openModal('demo-modal'));
  document.getElementById('btn-modal-quick-demo')?.addEventListener('click', () => openModal('demo-modal'));
  document.getElementById('btn-close-demo')?.addEventListener('click', () => closeModal('demo-modal'));

  // Demo modal pick buttons
  document.querySelectorAll('.demo-pick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const ind = btn.dataset.industry;
      launchDemoWorkspace(ind);
    });
  });

  // Hero Actions
  document.getElementById('hero-get-started-btn')?.addEventListener('click', () => {
    document.getElementById('industries-selection')?.scrollIntoView({ behavior: 'smooth' });
  });

  // Trio feature cards
  document.getElementById('trio-content-ideas')?.addEventListener('click', () => openModal('demo-modal'));
  document.getElementById('trio-ai-chat')?.addEventListener('click', () => openModal('demo-modal'));
  document.getElementById('trio-industry-news')?.addEventListener('click', () => openModal('demo-modal'));

  // 4 Industry Cards
  document.querySelectorAll('.industry-card').forEach(card => {
    card.addEventListener('click', async (e) => {
      // If clicked specific demo button inside card, don't trigger signup modal
      if (e.target.classList.contains('btn-ind-demo')) return;

      const industry = card.dataset.industry;
      state.selectedIndustry = industry;
      
      const regIndSelect = document.getElementById('reg-industry');
      if (regIndSelect) {
        regIndSelect.value = industry;
      }

      await prefillSampleInvitation();
      setAuthModalTab('signup');
      openModal('auth-modal');
    });
  });

  // Per-industry demo buttons on cards
  document.querySelectorAll('.btn-ind-demo').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const ind = btn.dataset.industry;
      launchDemoWorkspace(ind);
    });
  });

  // Top Nav Buttons
  document.getElementById('btn-nav-signup')?.addEventListener('click', async () => {
    await prefillSampleInvitation();
    setAuthModalTab('signup');
    openModal('auth-modal');
  });

  document.getElementById('btn-nav-login')?.addEventListener('click', () => {
    setAuthModalTab('login');
    openModal('auth-modal');
  });

  document.getElementById('btn-nav-logout')?.addEventListener('click', () => {
    logoutUser(true);
  });

  document.getElementById('btn-close-auth')?.addEventListener('click', () => {
    closeModal('auth-modal');
  });

  // Auth Modal Tabs
  document.getElementById('tab-auth-signup')?.addEventListener('click', () => setAuthModalTab('signup'));
  document.getElementById('tab-auth-login')?.addEventListener('click', () => setAuthModalTab('login'));

  // Registration Form Submit
  document.getElementById('form-signup')?.addEventListener('submit', handleSignupSubmit);

  // Login Form Submit
  document.getElementById('form-login')?.addEventListener('submit', handleLoginSubmit);

  // Chat Form Submit
  document.getElementById('chat-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const textEl = document.getElementById('chat-input-text');
    if (textEl) {
      handleSendMessage(textEl.value);
    }
  });

  // Chat Textarea Auto-expand & Enter-to-send
  const chatInput = document.getElementById('chat-input-text');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage(chatInput.value);
      }
    });

    chatInput.addEventListener('input', () => {
      chatInput.style.height = 'auto';
      chatInput.style.height = `${Math.min(chatInput.scrollHeight, 160)}px`;
    });
  }

  // Suggestion Chips
  document.querySelectorAll('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const promptText = btn.dataset.prompt;
      if (promptText) {
        handleSendMessage(promptText);
      }
    });
  });

  // Header Quick Buttons
  document.getElementById('btn-find-news')?.addEventListener('click', () => {
    handleSendMessage('Please discover recent industry news and timely announcements for our location.');
  });

  document.getElementById('btn-show-holidays')?.addEventListener('click', () => {
    handleSendMessage('What upcoming observances or awareness themes should we highlight this month?');
  });

  // Notification Bell & Drawer
  document.getElementById('notif-bell')?.addEventListener('click', () => {
    const drawer = document.getElementById('notif-drawer');
    drawer?.classList.toggle('hidden');
  });

  document.getElementById('btn-close-notif')?.addEventListener('click', () => {
    document.getElementById('notif-drawer')?.classList.add('hidden');
  });

  // Sidebar Links Switcher
  document.getElementById('btn-view-chat')?.addEventListener('click', () => switchToView('chat'));
  document.getElementById('btn-view-captions')?.addEventListener('click', () => switchToView('captions'));
  document.getElementById('btn-view-news')?.addEventListener('click', () => switchToView('news'));

  // + New Month button
  document.getElementById('btn-new-month')?.addEventListener('click', async () => {
    await loadCurrentConversation();
    showToast('Loaded active monthly workspace.', 'info');
  });

  // Settings Modal
  document.getElementById('btn-nav-settings')?.addEventListener('click', openSettingsModal);
  document.getElementById('btn-sidebar-settings')?.addEventListener('click', openSettingsModal);
  document.getElementById('btn-close-settings')?.addEventListener('click', () => closeModal('settings-modal'));
  document.getElementById('form-settings')?.addEventListener('submit', handleSettingsSubmit);
  document.getElementById('btn-danger-delete')?.addEventListener('click', handleAccountDeletion);

  // Caption Edit Modal
  document.getElementById('btn-close-caption-edit')?.addEventListener('click', () => closeModal('caption-edit-modal'));
  document.getElementById('form-caption-edit')?.addEventListener('submit', handleCaptionEditSubmit);
}

function setAuthModalTab(tab) {
  const tabSignup = document.getElementById('tab-auth-signup');
  const tabLogin = document.getElementById('tab-auth-login');
  const formSignup = document.getElementById('form-signup');
  const formLogin = document.getElementById('form-login');

  if (tab === 'signup') {
    tabSignup?.classList.add('active');
    tabLogin?.classList.remove('active');
    formSignup?.classList.remove('hidden');
    formLogin?.classList.add('hidden');
  } else {
    tabLogin?.classList.add('active');
    tabSignup?.classList.remove('active');
    formLogin?.classList.remove('hidden');
    formSignup?.classList.add('hidden');
  }
}

async function prefillSampleInvitation() {
  const invInput = document.getElementById('reg-invitation');
  if (invInput && !invInput.value) {
    try {
      const data = await api('/auth/invitation/sample');
      if (data && data.code) {
        invInput.value = data.code;
      }
    } catch (err) {
      console.warn('Could not fetch sample invitation code:', err);
    }
  }
}

async function handleSignupSubmit(e) {
  e.preventDefault();
  const invitationCode = document.getElementById('reg-invitation').value.trim();
  const industry = document.getElementById('reg-industry').value;
  const businessName = document.getElementById('reg-biz-name').value.trim();
  const location = document.getElementById('reg-biz-location').value.trim();
  const description = document.getElementById('reg-biz-desc').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;

  const platforms = Array.from(document.querySelectorAll('#form-signup input[name="platform"]:checked'))
    .map(cb => cb.value);

  const submitBtn = document.getElementById('btn-submit-signup');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Setting up your business...';

  try {
    const payload = {
      email,
      password,
      invitation_code: invitationCode,
      business_name: businessName,
      industry,
      business_description: description,
      business_location: location,
      preferred_platforms: platforms.length > 0 ? platforms : ['LinkedIn', 'Instagram'],
    };

    const res = await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    state.token = res.token;
    localStorage.setItem('soco_token', res.token);
    state.user = res.user;
    state.profile = res.profile;

    closeModal('auth-modal');
    showToast(res.message || 'Welcome to SoCo!', 'success');
    await enterWorkspace();
  } catch (err) {
    showToast(`Registration failed: ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Create Account & Enter Workspace';
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;

  const submitBtn = document.getElementById('btn-submit-login');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Signing in...';

  try {
    const res = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    state.token = res.token;
    localStorage.setItem('soco_token', res.token);
    state.user = res.user;
    state.profile = res.profile;

    closeModal('auth-modal');
    showToast(`Welcome back, ${res.profile ? res.profile.business_name : 'Partner'}!`, 'success');
    await enterWorkspace();
  } catch (err) {
    showToast(`Sign in failed: ${err.message}`, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Sign In to SoCo';
  }
}

function openSettingsModal() {
  if (!state.profile) return;
  const p = state.profile;

  document.getElementById('set-biz-name').value = p.business_name || '';
  document.getElementById('set-biz-location').value = p.business_location || '';
  document.getElementById('set-biz-desc').value = p.business_description || '';
  document.getElementById('set-industry').value = p.industry || 'construction_civil_engineering';

  openModal('settings-modal');
}

async function handleSettingsSubmit(e) {
  e.preventDefault();
  const updates = {
    business_name: document.getElementById('set-biz-name').value.trim(),
    business_location: document.getElementById('set-biz-location').value.trim(),
    business_description: document.getElementById('set-biz-desc').value.trim(),
    industry: document.getElementById('set-industry').value,
  };

  try {
    const updated = await api('/business/profile', {
      method: 'PUT',
      body: JSON.stringify(updates),
    });

    state.profile = updated;
    closeModal('settings-modal');
    showToast('Settings saved successfully.', 'success');
    await enterWorkspace();
  } catch (err) {
    showToast(`Failed to update profile: ${err.message}`, 'error');
  }
}

async function handleAccountDeletion() {
  const confirmed = confirm(
    'Are you sure you want to permanently delete your business account?\n\n' +
    'This will wipe all monthly conversations, draft captions, and custom settings. ' +
    'This action cannot be undone.'
  );

  if (!confirmed) return;

  try {
    await api('/auth/account', { method: 'DELETE' });
    showToast('Account and business data permanently wiped.', 'info');
    closeModal('settings-modal');
    logoutUser(false);
  } catch (err) {
    showToast(`Deletion failed: ${err.message}`, 'error');
  }
}

async function handleCaptionEditSubmit(e) {
  e.preventDefault();
  const captionId = document.getElementById('edit-caption-id').value;
  const newText = document.getElementById('edit-caption-text').value.trim();
  const rawHashtags = document.getElementById('edit-caption-hashtags').value.trim();
  const note = document.getElementById('edit-caption-note').value.trim();

  const hashtags = rawHashtags ? rawHashtags.split(' ').map(h => h.trim()).filter(Boolean) : [];

  try {
    const updated = await api(`/captions/${captionId}/revise`, {
      method: 'POST',
      body: JSON.stringify({
        new_text: newText,
        new_hashtags: hashtags,
        note: note || 'User edited copy in workspace',
      }),
    });

    closeModal('caption-edit-modal');
    showToast('Revision saved with version history preserved.', 'success');

    const idx = state.captions.findIndex(c => c.id === captionId);
    if (idx !== -1) {
      state.captions[idx] = updated;
    }

    if (state.activeView === 'chat') {
      await loadCurrentConversation();
    } else {
      renderDedicatedCaptionsView();
    }
  } catch (err) {
    showToast(`Revision failed: ${err.message}`, 'error');
  }
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

// ============================================================================
// 12. App Bootstrap
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initApp();
});
