import os

from sqlalchemy import create_engine

from services import update_service as up


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")


def _installer(tmp_path, name, size=5 * 1024 * 1024 + 123):
    path = tmp_path / name
    path.write_bytes(os.urandom(size))
    return str(path)


def test_version_compare_is_numeric():
    assert up.parse_version("1.6.10") > up.parse_version("1.6.9")
    assert up.parse_version("1.7") > up.parse_version("1.6.99")
    assert up.parse_version("bad") == (0,)


def test_no_table_means_no_update(tmp_path):
    assert up.newer_release(_engine(tmp_path), "1.6.5") is None


def test_publish_detect_and_download(tmp_path):
    eng = _engine(tmp_path)
    src = _installer(tmp_path, "ITServiceLog-Setup-1.6.6.exe")
    up.publish(eng, src, "1.6.6", "یادداشت")
    rel = up.newer_release(eng, "1.6.5")
    assert rel["version"] == "1.6.6" and rel["notes"] == "یادداشت"
    assert up.newer_release(eng, "1.6.6") is None          # هم‌نسخه: اعلانی نیست
    assert up.newer_release(eng, "1.6.10") is None         # جدیدتر: اعلانی نیست

    seen = []
    out = up.download(eng, rel, str(tmp_path / "dl.exe"), lambda d, t: seen.append(d))
    assert open(out, "rb").read() == open(src, "rb").read()
    assert len(seen) == 3 and seen[-1] == rel["size"]      # تکه‌تکه دانلود شد


def test_keeps_last_two_and_replaces_same_version(tmp_path):
    eng = _engine(tmp_path)
    for v in ("1.6.6", "1.6.7", "1.6.8", "1.6.8"):
        up.publish(eng, _installer(tmp_path, f"s{v}.exe", 10), v)
    with eng.connect() as c:
        versions = sorted(r[0] for r in c.execute(up.AppRelease.__table__.select()
                                                  .with_only_columns(up.AppRelease.version)))
    assert versions == ["1.6.7", "1.6.8"]
    assert up.latest_release(eng)["version"] == "1.6.8"


def test_corrupt_download_is_rejected(tmp_path):
    eng = _engine(tmp_path)
    up.publish(eng, _installer(tmp_path, "s.exe", 100), "1.6.6")
    rel = dict(up.latest_release(eng), sha256="0" * 64)
    dest = str(tmp_path / "dl.exe")
    try:
        up.download(eng, rel, dest)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected failure")
    assert not os.path.exists(dest) and not os.path.exists(dest + ".part")
