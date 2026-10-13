"""Unit tests for caption draft revision, version history preservation, and restoration."""

import pytest
from app.models.caption import CaptionDraft, CaptionSourceType, CaptionStatus
from app.storage.firestore_store import LocalDocumentRepository


def test_caption_revision_and_version_preservation():
    repo = LocalDocumentRepository()
    biz_id = "biz_test_versioning"

    cap = CaptionDraft(
        id="cap_v_100",
        business_id=biz_id,
        month="October",
        year=2026,
        week_number=2,
        suggested_date="2026-10-14",
        platform="LinkedIn",
        caption_text="Initial version: Building stronger roads.",
        hashtags=["#Infrastructure", "#CivilEngineering"],
        concept_title="Road Project",
        source_type=CaptionSourceType.USER_EVENT,
        tone="Authoritative",
        voice="Engineering Leader",
    )
    repo.save_caption(biz_id, cap)

    # Initial state: version 1, empty history
    assert cap.current_version == 1
    assert len(cap.version_history) == 0

    # Revision 1: User edits caption
    updated_1 = repo.update_caption_revision(
        biz_id,
        "cap_v_100",
        new_text="Second version: Modernizing regional asphalt infrastructure.",
        new_hashtags=["#Infrastructure", "#PavingExcellence"],
        note="User requested more technical emphasis",
    )

    assert updated_1.current_version == 2
    assert len(updated_1.version_history) == 1
    # Check that Version 1 was preserved in history
    v1_snap = updated_1.version_history[0]
    assert v1_snap.version == 1
    assert v1_snap.caption_text == "Initial version: Building stronger roads."
    assert v1_snap.hashtags == ["#Infrastructure", "#CivilEngineering"]

    # Revision 2: Another edit
    updated_2 = repo.update_caption_revision(
        biz_id,
        "cap_v_100",
        new_text="Third version: Shorter and punchier road update.",
        note="Made shorter for quick scannability",
    )

    assert updated_2.current_version == 3
    assert len(updated_2.version_history) == 2
    assert updated_2.caption_text == "Third version: Shorter and punchier road update."
    assert updated_2.version_history[1].version == 2


def test_caption_version_restoration():
    repo = LocalDocumentRepository()
    biz_id = "biz_restore_test"

    cap = CaptionDraft(
        id="cap_restore_1",
        business_id=biz_id,
        month="October",
        year=2026,
        week_number=1,
        suggested_date="2026-10-07",
        platform="Instagram",
        caption_text="Version 1: Our favorite dish this week.",
        hashtags=["#Foodie"],
        concept_title="Weekly Special",
        source_type=CaptionSourceType.USER_EVENT,
        tone="Warm",
        voice="Friendly",
    )
    repo.save_caption(biz_id, cap)

    # Make revisions to reach Version 3
    repo.update_caption_revision(biz_id, "cap_restore_1", "Version 2: Chef's autumn recommendation.")
    repo.update_caption_revision(biz_id, "cap_restore_1", "Version 3: Too complex gourmet copy.")

    active = repo.get_caption(biz_id, "cap_restore_1")
    assert active.current_version == 3
    assert "Version 3" in active.caption_text

    # Restore Version 1
    restored = repo.restore_caption_version(biz_id, "cap_restore_1", target_version=1)
    assert restored.current_version == 4  # Version bumped to preserve restoration snapshot
    assert restored.caption_text == "Version 1: Our favorite dish this week."
    assert restored.hashtags == ["#Foodie"]

    # Attempt to restore non-existent version -> raises ValueError
    with pytest.raises(ValueError):
        repo.restore_caption_version(biz_id, "cap_restore_1", target_version=99)
