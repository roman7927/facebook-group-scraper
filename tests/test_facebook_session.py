import unittest
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from facebook_session import (
    FacebookSessionError,
    browser_session_status,
    require_facebook_session,
)
import main3


class FacebookSessionDOMTests(unittest.TestCase):
    """Real rendered DOM fixtures; every browser request is blocked."""

    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context()
        self.context.route("**/*", lambda route: route.abort())
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()

    def fixture(self, html, url="https://www.facebook.com/groups/test"):
        self.page.set_content(html)
        # Supply a URL independently of set_content's about:blank origin.
        page = MagicMock()
        page.url = url
        page.locator = self.page.locator
        return page

    def test_hidden_first_input_does_not_mask_visible_login_form(self):
        page = self.fixture('<input name="email" hidden><input name="pass">')
        self.assertEqual(browser_session_status(page), "logged_out")

    def test_hidden_login_inputs_and_footer_text_are_not_logout(self):
        page = self.fixture('Log In<input name="email" hidden><input name="pass" style="display:none">'
                            '<div role="button" aria-label="Your profile">Account</div>')
        self.assertEqual(browser_session_status(page), "healthy")

    def test_facebook_url_alone_is_not_healthy(self):
        self.assertEqual(browser_session_status(self.fixture("Loading…")), "unknown")

    def test_post_menu_is_positive_session_evidence(self):
        page = self.fixture('<div aria-label="Actions for this post by Example">Menu</div>')
        self.assertEqual(browser_session_status(page), "healthy")

    def test_login_overlay_over_feed_wins_over_post_menu(self):
        page = self.fixture('<div aria-label="Actions for this post by Example">Menu</div>'
                            '<input name="email">')
        with self.assertRaises(FacebookSessionError) as caught:
            require_facebook_session(page)
        self.assertEqual(caught.exception.status, "logged_out")
        self.assertIn("Log in manually", str(caught.exception))

    def test_login_url_does_not_require_rendered_inputs(self):
        page = self.fixture("", "https://www.facebook.com/login/?next=group")
        self.assertEqual(browser_session_status(page), "logged_out")

    def test_checkpoint_requires_manual_verification(self):
        page = self.fixture("", "https://www.facebook.com/checkpoint/123")
        with self.assertRaises(FacebookSessionError) as caught:
            require_facebook_session(page)
        self.assertEqual(caught.exception.status, "degraded")

    def test_non_facebook_host_is_degraded(self):
        page = self.fixture("", "https://www.facebook.com.example.org/")
        self.assertEqual(browser_session_status(page), "degraded")


class FacebookSessionWorkflowTests(unittest.TestCase):
    source = {"group_id": "test", "group_name": "Test", "facebook_source_type": "group",
              "group_url": "https://www.facebook.com/groups/test"}

    def test_login_appearing_after_navigation_is_classified_before_join_error(self):
        page = MagicMock()
        page.locator.return_value.first.wait_for.side_effect = PlaywrightTimeoutError("timeout")
        with patch.object(main3, "require_facebook_session", side_effect=[
            "unknown", FacebookSessionError("logged_out")
        ]):
            with self.assertRaises(FacebookSessionError):
                main3.scrape_group(page, self.source, set(), True, 5)
        page.get_by_text.assert_not_called()

    def test_failed_cycle_preserves_workbook_and_reports_logged_out(self):
        health = MagicMock()
        with (patch.object(main3, "STATE_FILE") as state,
              patch.object(main3, "GreenCheckClient"),
              patch.object(main3, "OutboundQueue"),
              patch.object(main3, "HealthReporter", return_value=health),
              patch.object(main3, "load_sources", return_value=([self.source], False)),
              patch.object(main3, "load_existing_data", return_value=([], [])),
              patch.object(main3, "sync_playwright"),
              patch.object(main3, "browser_session_status", return_value="unknown"),
              patch.object(main3, "scrape_group", side_effect=FacebookSessionError("logged_out")),
              patch.object(main3, "write_workbook") as write,
              patch.object(main3, "build_payloads") as payloads,
              patch("sys.argv", ["main3.py"])):
            state.exists.return_value = True
            with self.assertRaises(SystemExit) as caught:
                main3.main()
        self.assertEqual(caught.exception.code, 1)
        health.set_browser_status.assert_any_call("logged_out")
        health.fail_source.assert_called_once()
        health.stop.assert_called_once()
        write.assert_not_called()
        payloads.assert_not_called()


if __name__ == "__main__":
    unittest.main()
