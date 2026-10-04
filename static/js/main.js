/**
 * e-Book Global JavaScript Utilities
 */
(() => {
    const header = document.querySelector('[data-purpose="site-header"]');
    if (!header) return;
    const updateHeader = () => header.classList.toggle('is-scrolled', window.scrollY > 24);
    window.addEventListener('scroll', updateHeader, { passive: true });
    window.addEventListener('pageshow', updateHeader);
    updateHeader();
})();

// ==========================================
// IN-PAGE MESSAGE AUTO-DISMISS ENGINE
// ==========================================

/**
 * Smoothly dismisses an alert element and removes it from the DOM without page reload.
 */
function dismissAlert(alertEl) {
    if (!alertEl || alertEl.dataset.dismissing === 'true') return;
    alertEl.dataset.dismissing = 'true';

    if (alertEl._autoDismissTimer) {
        clearTimeout(alertEl._autoDismissTimer);
    }

    // Step 1: Fade out and slide up slightly
    alertEl.style.transition = 'opacity 0.35s ease, transform 0.35s ease, max-height 0.4s ease 0.1s, margin 0.4s ease 0.1s, padding 0.4s ease 0.1s';
    alertEl.style.opacity = '0';
    alertEl.style.transform = 'translateY(-8px)';

    // Step 2: Smoothly collapse vertical height
    setTimeout(() => {
        alertEl.style.maxHeight = '0px';
        alertEl.style.paddingTop = '0px';
        alertEl.style.paddingBottom = '0px';
        alertEl.style.marginTop = '0px';
        alertEl.style.marginBottom = '0px';
        alertEl.style.overflow = 'hidden';
    }, 150);

    // Step 3: Remove from DOM
    setTimeout(() => {
        alertEl.remove();
    }, 550);
}

/**
 * Initializes auto-dismissal for any alert container with pause-on-hover.
 */
function setupAutoAlert(alertEl, delay = 4000) {
    if (!alertEl || alertEl.dataset.initialized === 'true') return;
    alertEl.dataset.initialized = 'true';

    let startTime = Date.now();
    let remaining = delay;
    let isPaused = false;

    const startTimer = () => {
        startTime = Date.now();
        alertEl._autoDismissTimer = setTimeout(() => {
            dismissAlert(alertEl);
        }, remaining);
    };

    const pauseTimer = () => {
        if (isPaused) return;
        isPaused = true;
        clearTimeout(alertEl._autoDismissTimer);
        const elapsed = Date.now() - startTime;
        remaining = Math.max(0, remaining - elapsed);
    };

    const resumeTimer = () => {
        if (!isPaused || remaining <= 0) return;
        isPaused = false;
        startTimer();
    };

    alertEl.addEventListener('mouseenter', pauseTimer);
    alertEl.addEventListener('mouseleave', resumeTimer);

    startTimer();
}

// ==========================================
// DOM READY INITIALIZATION
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    // Automatically find all in-page alerts across all templates
    const alerts = document.querySelectorAll('[data-purpose="auto-alert"]');
    alerts.forEach(alert => {
        setupAutoAlert(alert, 4000);
    });
});

// ==========================================
// HELPER FUNCTIONS
// ==========================================

// Password visibility toggle
function togglePasswordVisibility(inputId, buttonEl) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const icon = buttonEl.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        if (icon) icon.className = 'fa-regular fa-eye-slash text-xs';
    } else {
        input.type = 'password';
        if (icon) icon.className = 'fa-regular fa-eye text-xs';
    }
}

// Copy to clipboard helper
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    navigator.clipboard.writeText(text).then(() => {
        // Simple non-blocking alert notification if available
        const tempNotice = document.createElement('div');
        tempNotice.className = 'fixed bottom-6 right-6 z-50 bg-gray-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-lg transition-all duration-300 transform translate-y-0 opacity-100';
        tempNotice.textContent = successMessage;
        document.body.appendChild(tempNotice);
        setTimeout(() => {
            tempNotice.style.opacity = '0';
            tempNotice.style.transform = 'translateY(8px)';
            setTimeout(() => tempNotice.remove(), 300);
        }, 2500);
    }).catch(() => {
        alert(text);
    });
}

// ==========================================
// REAL-TIME UNREAD MESSAGES BADGE ENGINE
// ==========================================
(function initRealtimeMessageBadges() {
    let previousCount = null;

    function getBadgeElements() {
        return [
            document.getElementById('unreadMessagesBadge'),
            document.getElementById('unreadMessagesMobileBadge'),
            document.getElementById('unreadMessagesDropdownBadge')
        ].filter(Boolean);
    }

    function applyCount(count) {
        const num = parseInt(count, 10) || 0;
        const badges = getBadgeElements();
        badges.forEach(el => {
            if (num > 0) {
                el.textContent = num > 99 ? '99+' : String(num);
                el.classList.remove('hidden');
                // Trigger a momentary scale/glow pulse if count increased
                if (previousCount !== null && num > previousCount) {
                    el.classList.add('scale-125');
                    setTimeout(() => el.classList.remove('scale-125'), 400);
                }
            } else {
                el.textContent = '0';
                el.classList.add('hidden');
            }
        });
        previousCount = num;
    }

    async function checkUnreadCount() {
        if (document.hidden) return; // Pause polling when tab is inactive to save battery/bandwidth
        try {
            const res = await fetch('/inbox/api/unread/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (res.ok) {
                const data = await res.json();
                if (data && typeof data.unread_count === 'number') {
                    applyCount(data.unread_count);
                    window.dispatchEvent(new CustomEvent('unreadMessagesChecked', { detail: data }));
                }
            }
        } catch (e) {
            // Silently ignore network interruptions
        }
    }

    // Expose helpers globally so other views (chat, inbox) can trigger instant refresh
    window.refreshUnreadMessagesBadge = checkUnreadCount;
    window.setUnreadMessagesBadgeCount = applyCount;

    // Check periodically every 3 seconds for instant real-time updates without reload
    document.addEventListener('DOMContentLoaded', () => {
        checkUnreadCount();
        setInterval(checkUnreadCount, 3000);
    });

    // Check immediately when user switches back to this tab
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) checkUnreadCount();
    });
})();
