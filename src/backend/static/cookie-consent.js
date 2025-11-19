/**
 * Cookie consent management following GOV.UK Design System patterns
 * Handles analytics cookie consent for PostHog tracking
 */

const CONSENT_COOKIE_VERSION = 1;
const CONSENT_COOKIE_NAME = 'lex_cookies_policy';
const CONSENT_COOKIE_DURATION = 365; // days

/**
 * Get cookie consent preferences
 * @returns {Object|null} Consent object or null if not set
 */
function getConsentCookie() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === CONSENT_COOKIE_NAME) {
            try {
                return JSON.parse(decodeURIComponent(value));
            } catch (e) {
                console.error('Failed to parse consent cookie:', e);
                return null;
            }
        }
    }
    return null;
}

/**
 * Set cookie consent preferences
 * @param {Object} preferences - Consent preferences object
 */
function setConsentCookie(preferences) {
    const consent = {
        version: CONSENT_COOKIE_VERSION,
        analytics: preferences.analytics,
        timestamp: new Date().toISOString()
    };

    const expires = new Date();
    expires.setDate(expires.getDate() + CONSENT_COOKIE_DURATION);

    const cookieValue = encodeURIComponent(JSON.stringify(consent));
    document.cookie = `${CONSENT_COOKIE_NAME}=${cookieValue}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;

    return consent;
}

/**
 * Initialize PostHog with user consent
 * @param {boolean} hasConsent - Whether user has consented to analytics
 */
function initializePostHog(hasConsent) {
    if (!window.posthog) {
        console.warn('PostHog not loaded');
        return;
    }

    if (hasConsent) {
        // Enable cookies and start tracking
        window.posthog.set_config({
            persistence: 'cookie',
            disable_cookie: false
        });

        // Track initial pageview
        window.posthog.capture('$pageview', {
            $current_url: window.location.href,
            page_title: document.title
        });

        console.log('PostHog analytics enabled with cookie consent');
    } else {
        // Disable tracking
        window.posthog.opt_out_capturing();
        console.log('PostHog analytics disabled - no consent');
    }
}

/**
 * Show cookie banner message
 * @param {string} messageId - ID of message to show
 */
function showBannerMessage(messageId) {
    // Hide all messages
    document.querySelectorAll('.govuk-cookie-banner__message').forEach(msg => {
        msg.setAttribute('hidden', 'hidden');
    });

    // Show requested message
    const message = document.getElementById(messageId);
    if (message) {
        message.removeAttribute('hidden');
        message.setAttribute('role', 'alert');
        message.setAttribute('tabindex', '-1');
        message.focus();
    }
}

/**
 * Hide the entire cookie banner
 */
function hideCookieBanner() {
    const banner = document.querySelector('.govuk-cookie-banner');
    if (banner) {
        banner.setAttribute('hidden', 'hidden');
    }
}

/**
 * Accept analytics cookies
 */
function acceptCookies() {
    setConsentCookie({ analytics: true });
    initializePostHog(true);
    showBannerMessage('cookie-banner-accepted');
}

/**
 * Reject analytics cookies
 */
function rejectCookies() {
    setConsentCookie({ analytics: false });
    initializePostHog(false);
    showBannerMessage('cookie-banner-rejected');
}

/**
 * Initialize cookie consent on page load
 */
function initializeCookieConsent() {
    // Don't show banner on cookies page
    if (window.location.pathname === '/cookies') {
        hideCookieBanner();
        return;
    }

    const consent = getConsentCookie();

    if (consent && consent.version === CONSENT_COOKIE_VERSION) {
        // User has already made a choice - hide banner and initialize PostHog
        hideCookieBanner();
        initializePostHog(consent.analytics);
    } else {
        // No consent yet - show the banner
        const banner = document.querySelector('.govuk-cookie-banner');
        if (banner) {
            banner.removeAttribute('hidden');
        }

        // Initialize PostHog in opt-out mode until consent given
        if (window.posthog) {
            window.posthog.opt_out_capturing();
        }
    }

    // Set up event listeners
    const acceptButton = document.getElementById('cookie-accept-button');
    const rejectButton = document.getElementById('cookie-reject-button');
    const hideButtons = document.querySelectorAll('.cookie-hide-button');

    if (acceptButton) {
        acceptButton.addEventListener('click', acceptCookies);
    }

    if (rejectButton) {
        rejectButton.addEventListener('click', rejectCookies);
    }

    hideButtons.forEach(button => {
        button.addEventListener('click', hideCookieBanner);
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCookieConsent);
} else {
    initializeCookieConsent();
}

// Export functions for cookies page
window.CookieConsent = {
    getConsent: getConsentCookie,
    setConsent: setConsentCookie,
    acceptCookies,
    rejectCookies,
    initializePostHog
};
