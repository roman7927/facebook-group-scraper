import unittest

from media_metadata import media_metadata, normalized_row_metadata


class MediaMetadataTests(unittest.TestCase):
    def assert_type(self, expected, **evidence):
        metadata = media_metadata(**evidence)
        self.assertEqual(metadata["content_type"], expected)
        return metadata

    def test_text_only_post(self):
        self.assert_type("text", has_text=True)

    def test_image_only_post(self):
        metadata = self.assert_type("image_only", has_text=False, has_image=True, attachment_count=1)
        self.assertTrue(metadata["has_image"])
        self.assertGreaterEqual(metadata["attachment_count"], 1)

    def test_text_plus_image(self):
        self.assert_type("text_with_image", has_text=True, has_image=True, attachment_count=1)

    def test_video_only_post(self):
        self.assert_type("video_only", has_text=False, has_video=True, attachment_count=1)

    def test_text_plus_video(self):
        self.assert_type("text_with_video", has_text=True, has_video=True, attachment_count=1)

    def test_link_preview(self):
        self.assert_type("link", has_text=False, has_link_preview=True, attachment_count=1)
        self.assert_type("text_with_link", has_text=True, has_link_preview=True, attachment_count=1)
        self.assert_type("link", has_text=False, has_link_preview=True, has_image=True, attachment_count=2)

    def test_profile_picture_does_not_create_post_image(self):
        self.assert_type("empty", has_text=False, has_image=False, attachment_count=0)

    def test_adjacent_post_image_is_not_card_evidence(self):
        self.assert_type("text", has_text=True, has_image=False, attachment_count=0)

    def test_unrecognized_attachment(self):
        self.assert_type("attachment_only", has_text=False, attachment_count=1)

    def test_empty_and_unknown(self):
        self.assert_type("empty", has_text=False)
        self.assert_type("unknown", has_text=False, uncertain=True)

    def test_legacy_placeholder_becomes_empty_authored_text(self):
        metadata = normalized_row_metadata({"post_text": "[Post without text]"})
        self.assertFalse(metadata["has_text"])
        self.assertEqual(metadata["content_type"], "empty")


if __name__ == "__main__":
    unittest.main()
