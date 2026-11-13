"""Deleting a document removes its uploaded file, and nothing outside the uploads folder."""
from routers import matters


def test_a_file_inside_the_uploads_folder_is_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(matters, "UPLOAD_DIR", tmp_path)
    upload = tmp_path / "matter-1" / "contract.pdf"
    upload.parent.mkdir()
    upload.write_bytes(b"%PDF")
    matters._remove_upload(str(upload))
    assert not upload.exists()


def test_a_file_outside_the_uploads_folder_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(matters, "UPLOAD_DIR", tmp_path / "uploads")
    elsewhere = tmp_path / "keep.txt"
    elsewhere.write_text("not an upload")
    matters._remove_upload(str(elsewhere))
    matters._remove_upload(str(tmp_path / "uploads" / ".." / "keep.txt"))
    assert elsewhere.exists()


def test_a_missing_file_or_path_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(matters, "UPLOAD_DIR", tmp_path)
    matters._remove_upload(str(tmp_path / "gone.pdf"))
    matters._remove_upload(None)
