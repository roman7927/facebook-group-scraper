"""Recognize rendered Facebook authentication failures without reading cookies."""

from urllib.parse import urlsplit


POST_ACTION_SELECTOR = "[aria-label^='Actions for this post by ']"
LOGIN_INPUT_SELECTOR = "input[name='email']:visible, input[name='pass']:visible"
ACCOUNT_SELECTOR = '[aria-label="Your profile"]:visible, [aria-label="Account"]:visible'


class FacebookSessionError(RuntimeError):
    def __init__(self, status):
        self.status = status
        message = (
            "Facebook session expired: a visible login form or login page was found. "
            "Log in manually and refresh facebook_state.json."
            if status == "logged_out" else
            "Facebook requires account verification or the browser left Facebook. "
            "Open the session manually before retrying."
        )
        super().__init__(message)


def browser_session_status(page):
    url = urlsplit(page.url)
    if url.hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com"}:
        return "degraded"
    path = url.path.lower()
    if path.startswith(("/checkpoint", "/challenge", "/two_step_verification")):
        return "degraded"
    if path.startswith(("/login", "/recover")) or page.locator(LOGIN_INPUT_SELECTOR).count():
        return "logged_out"
    # Hidden hydration inputs and footer text are not evidence of logout.
    # Conversely, a Facebook URL alone is not evidence of authentication.
    if (page.locator(ACCOUNT_SELECTOR).count()
            or page.locator(f"{POST_ACTION_SELECTOR}:visible").count()):
        return "healthy"
    return "unknown"


def require_facebook_session(page):
    status = browser_session_status(page)
    if status in {"logged_out", "degraded"}:
        raise FacebookSessionError(status)
    return status
