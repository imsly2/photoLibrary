"""Optional local video transcription. Whisper family, no cloud API."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import wave
from pathlib import Path
from typing import Any

from library.atomic import atomic_write_json, transact
from library.catalog_io import item_rel, iter_item_ids, load_item
from library.errors import fail
from library.media import ffprobe_json, mtime_iso
from library.records import clone, ordered_item
from library.volumes import location_file, location_matches_stat

KIND = "transcribe"
MODEL_SIZE = "small"
MODEL_FAMILY = "whisper"
ENGINE = "faster-whisper"
RUNTIME_PACKAGES = ("faster-whisper",)
TRANSCRIPT_STATUSES = frozenset({"ready", "skipped", "error"})

# Fold common Traditional forms Whisper emits so Simplified queries match.
_CJK_FOLD = str.maketrans(
    {
        "氣": "气",
        "園": "园",
        "噴": "喷",
        "車": "车",
        "麼": "么",
        "這": "这",
        "還": "还",
        "來": "来",
        "過": "过",
        "為": "为",
        "無": "无",
        "長": "长",
        "門": "门",
        "開": "开",
        "問": "问",
        "東": "东",
        "風": "风",
        "頭": "头",
        "見": "见",
        "說": "说",
        "時": "时",
        "後": "后",
        "嗎": "吗",
        "對": "对",
        "裡": "里",
        "裏": "里",
        "點": "点",
        "國": "国",
        "會": "会",
        "學": "学",
        "語": "语",
        "話": "话",
        "們": "们",
        "個": "个",
        "從": "从",
        "當": "当",
        "經": "经",
        "現": "现",
        "發": "发",
        "實": "实",
        "與": "与",
        "於": "于",
        "並": "并",
        "種": "种",
        "樣": "样",
        "將": "将",
        "樂": "乐",
        "歡": "欢",
        "歲": "岁",
        "兒": "儿",
        "孫": "孙",
        "親": "亲",
        "節": "节",
        "飯": "饭",
        "魚": "鱼",
        "馬": "马",
        "鳥": "鸟",
        "龍": "龙",
        "錢": "钱",
        "電": "电",
        "機": "机",
        "橋": "桥",
        "樓": "楼",
        "廣": "广",
        "場": "场",
    }
)

_EN_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "to",
        "of",
        "in",
        "on",
        "for",
        "at",
        "by",
        "with",
        "from",
        "as",
        "it",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "our",
        "their",
        "not",
        "no",
        "yes",
        "oh",
        "um",
        "uh",
    }
)

_WHISPER_MODEL = None
_WHISPER_DEVICE: str | None = None


def whisper_dir(root: Path) -> Path:
    return root / "models" / "whisper"


def transcribe_manifest_path(root: Path) -> Path:
    return whisper_dir(root) / "transcribe.json"


def model_size() -> str:
    raw = os.environ.get("LIBRARY_WHISPER_MODEL") or MODEL_SIZE
    if type(raw) is not str or raw == "":
        return MODEL_SIZE
    return raw.strip()


def _has_model_bin(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    return any(path.name == "model.bin" and path.is_file() and path.stat().st_size > 1_000_000 for path in folder.rglob("model.bin"))


def model_installed(root: Path) -> bool:
    if transcribe_manifest_path(root).is_file() and _has_model_bin(whisper_dir(root)):
        return True
    return _has_model_bin(whisper_dir(root))


def transcribe_enabled(root: Path) -> bool:
    try:
        from library.settings import load_settings_file

        return bool(load_settings_file(root).get("transcribeVideos", True))
    except Exception:
        return True


def read_transcribe_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {"itemId": None, "force": False}
    if not isinstance(value, dict):
        raise fail("invalid-argument")
    extra = set(value.keys()) - {"itemId", "force"}
    if extra:
        raise fail("invalid-argument")
    item_id = value.get("itemId")
    if item_id is None:
        parsed_id = None
    else:
        if type(item_id) is not str or item_id == "":
            raise fail("invalid-argument")
        parsed_id = item_id
    force = value.get("force", False)
    if type(force) is not bool:
        raise fail("invalid-argument")
    return {"itemId": parsed_id, "force": force}


def transcribe_status(root: Path) -> dict[str, Any]:
    installed = model_installed(root)
    enabled = transcribe_enabled(root)
    pending, done, error = transcribe_counts(root)
    return {
        "ok": True,
        "installed": installed,
        "enabled": enabled,
        "model": MODEL_SIZE if installed else None,
        "engine": ENGINE,
        "pending": pending if enabled and installed else 0,
        "done": done,
        "error": error,
    }


def transcribe_counts(root: Path) -> tuple[int, int, int]:
    pending = 0
    done = 0
    error = 0
    enabled = transcribe_enabled(root)
    installed = model_installed(root)
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        if item.get("kind") != "video":
            continue
        video = _current_video_file(item, root)
        if video is None:
            continue
        if not _has_audio_stream(video):
            rec = item.get("transcript")
            if isinstance(rec, dict) and rec.get("status") in {"skipped", "ready"}:
                done += 1
            elif enabled and installed:
                pending += 1
            continue
        if _already_done(item, video):
            rec = item.get("transcript") or {}
            if isinstance(rec, dict) and rec.get("status") == "error":
                error += 1
            else:
                done += 1
            continue
        if enabled and installed:
            pending += 1
    return pending, done, error


def setup_transcribe(root: Path) -> dict[str, Any]:
    whisper_dir(root).mkdir(parents=True, exist_ok=True)
    _ensure_runtime()
    dest = whisper_dir(root)
    _seed_from_cache(dest)
    if not _has_model_bin(dest):
        _download_model(dest)
    if not _has_model_bin(dest):
        raise fail("io-error")
    size_name = model_size()
    manifest = {
        "schemaVersion": 1,
        "kind": KIND,
        "engine": ENGINE,
        "modelFamily": MODEL_FAMILY,
        "model": size_name,
        "device": _pick_device()[0],
    }
    atomic_write_json(transcribe_manifest_path(root), manifest)
    return {
        "ok": True,
        "kind": KIND,
        "engine": ENGINE,
        "modelFamily": MODEL_FAMILY,
        "model": size_name,
        "path": "models/whisper",
        "device": manifest["device"],
    }


def transcribe_videos(root: Path, item_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    if not model_installed(root):
        raise fail("model-unavailable")
    _ensure_runtime()
    force_one = bool(force)
    if item_id is not None:
        load_item(root, item_id)
        ids = [item_id]
    else:
        ids = iter_item_ids(root)
    transcribed = 0
    skipped = 0
    errors = 0
    items: list[dict[str, Any]] = []
    for current_id in ids:
        item = load_item(root, current_id)
        if item.get("kind") != "video":
            skipped += 1
            continue
        video = _current_video_file(item, root)
        if video is None:
            skipped += 1
            continue
        if not force_one and _already_done(item, video):
            skipped += 1
            continue
        try:
            record = _transcribe_one(root, current_id, video)
        except Exception:
            _publish_transcript(root, current_id, _error_record(video))
            errors += 1
            continue
        transcribed += 1
        items.append(
            {
                "id": current_id,
                "language": record.get("language"),
                "text": record.get("text"),
                "summary": record.get("summary"),
                "keywords": record.get("keywords") or [],
            }
        )
    return {
        "ok": True,
        "transcribed": transcribed,
        "skipped": skipped,
        "errors": errors,
        "items": items,
        "summaryMethod": "extractive",
    }


def transcribe_step(root: Path) -> bool:
    if not transcribe_enabled(root):
        return False
    if not model_installed(root):
        return False
    try:
        _ensure_runtime()
    except Exception:
        return False
    for item_id in iter_item_ids(root):
        item = load_item(root, item_id)
        if item.get("kind") != "video":
            continue
        video = _current_video_file(item, root)
        if video is None:
            continue
        if not _has_audio_stream(video):
            if _already_done(item, video) and (item.get("transcript") or {}).get("status") == "skipped":
                continue
            _publish_transcript(root, item_id, _skipped_record(video))
            return True
        if _already_done(item, video):
            continue
        try:
            _transcribe_one(root, item_id, video)
        except Exception:
            _publish_transcript(root, item_id, _error_record(video))
        return True
    return False


def transcript_search_hit(item: dict[str, Any], needle: str) -> dict[str, Any] | None:
    folded = _fold_query(needle)
    if not folded:
        return None
    rec = item.get("transcript")
    if not isinstance(rec, dict) or rec.get("status") != "ready":
        return None
    for word in rec.get("words") or []:
        token = word.get("word")
        if type(token) is str and folded in _fold_query(token):
            start = word.get("start")
            return {
                "start": float(start) if isinstance(start, (int, float)) else 0.0,
                "text": token.strip(),
                "field": "transcript",
            }
    for seg in rec.get("segments") or []:
        text = seg.get("text")
        if type(text) is str and folded in _fold_query(text):
            start = seg.get("start")
            return {
                "start": float(start) if isinstance(start, (int, float)) else 0.0,
                "text": text.strip(),
                "field": "transcript",
            }
    summary = rec.get("summary") or ""
    if type(summary) is str and folded in _fold_query(summary):
        return {"start": _first_start(rec), "text": summary.strip(), "field": "summary"}
    for keyword in rec.get("keywords") or []:
        if type(keyword) is str and folded in _fold_query(keyword):
            return {"start": _first_start(rec), "text": keyword, "field": "keyword"}
    text = rec.get("text") or ""
    if type(text) is str and folded in _fold_query(text):
        snippet = text.strip()
        if len(snippet) > 80:
            snippet = snippet[:80]
        return {"start": _first_start(rec), "text": snippet, "field": "transcript"}
    return None


def _fold_query(value: str) -> str:
    text = unicodedata.normalize("NFC", value.strip()).casefold()
    return text.translate(_CJK_FOLD)


def _first_start(rec: dict[str, Any]) -> float:
    for word in rec.get("words") or []:
        start = word.get("start")
        if isinstance(start, (int, float)):
            return float(start)
    for seg in rec.get("segments") or []:
        start = seg.get("start")
        if isinstance(start, (int, float)):
            return float(start)
    return 0.0


def _already_done(item: dict[str, Any], video: Path) -> bool:
    rec = item.get("transcript")
    if not isinstance(rec, dict):
        return False
    if rec.get("status") not in TRANSCRIPT_STATUSES:
        return False
    try:
        stat = video.stat()
    except OSError:
        return False
    size = rec.get("sourceSizeBytes")
    modified = rec.get("sourceModifiedAt")
    if size != int(stat.st_size):
        return False
    if type(modified) is not str or modified == "":
        return False
    return modified == mtime_iso(video)


def _current_video_file(item: dict[str, Any], root: Path) -> Path | None:
    candidates = [
        loc
        for loc in item.get("locations") or []
        if loc.get("current") is True and loc.get("component") == "motion"
    ]
    if not candidates:
        candidates = [loc for loc in item.get("locations") or [] if loc.get("current") is True]
    candidates.sort(
        key=lambda loc: (
            0 if loc.get("role") == "primary" else 1,
            loc.get("sourceId") or "",
            loc.get("pathFromVolumeRoot") or loc.get("libraryRelativePath") or "",
        )
    )
    for loc in candidates:
        path = location_file(loc, root)
        if path is None or not path.is_file():
            continue
        if location_matches_stat(loc, path):
            return path
    return None


def _has_audio_stream(path: Path) -> bool:
    payload = ffprobe_json(path)
    if not isinstance(payload, dict):
        return False
    for stream in payload.get("streams") or []:
        if stream.get("codec_type") == "audio":
            return True
    return False


def _source_stamp(video: Path) -> tuple[int, str]:
    stat = video.stat()
    return int(stat.st_size), mtime_iso(video)


def _skipped_record(video: Path) -> dict[str, Any]:
    size, modified = _source_stamp(video)
    return _transcript_record(
        status="skipped",
        language=None,
        text="",
        segments=[],
        words=[],
        summary="",
        keywords=[],
        size=size,
        modified=modified,
        device="cpu",
    )


def _error_record(video: Path) -> dict[str, Any]:
    size, modified = _source_stamp(video)
    return _transcript_record(
        status="error",
        language=None,
        text="",
        segments=[],
        words=[],
        summary="",
        keywords=[],
        size=size,
        modified=modified,
        device="cpu",
    )


def _transcript_record(
    *,
    status: str,
    language: str | None,
    text: str,
    segments: list[dict[str, Any]],
    words: list[dict[str, Any]],
    summary: str,
    keywords: list[str],
    size: int,
    modified: str,
    device: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": status,
        "language": language,
        "text": text,
        "segments": segments,
        "words": words,
        "summary": summary,
        "keywords": keywords,
        "sourceSizeBytes": size,
        "sourceModifiedAt": modified,
        "model": f"{ENGINE}-{model_size()}",
        "device": device,
        "summaryMethod": "extractive",
    }


def _transcribe_one(root: Path, item_id: str, video: Path) -> dict[str, Any]:
    if not _has_audio_stream(video):
        record = _skipped_record(video)
        _publish_transcript(root, item_id, record)
        return record
    audio = _extract_wav(video)
    model, device = _whisper_model(root)
    segments_iter, info = model.transcribe(
        audio,
        language=None,
        word_timestamps=True,
        vad_filter=True,
        beam_size=1,
    )
    segments: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        start = float(seg.start or 0.0)
        end = float(seg.end or start)
        if text:
            texts.append(text)
            segments.append({"start": round(start, 3), "end": round(end, 3), "text": text})
        for word in seg.words or []:
            token = (word.word or "").strip()
            if not token:
                continue
            words.append(
                {
                    "start": round(float(word.start or start), 3),
                    "end": round(float(word.end or end), 3),
                    "word": token,
                }
            )
    language = getattr(info, "language", None)
    if type(language) is not str or language == "":
        language = None
    full = " ".join(texts).strip()
    if language and language.startswith("zh"):
        full = "".join(texts).strip()
    summary, keywords = extractive_summary(full, language)
    size, modified = _source_stamp(video)
    record = _transcript_record(
        status="ready",
        language=language,
        text=full,
        segments=segments,
        words=words,
        summary=summary,
        keywords=keywords,
        size=size,
        modified=modified,
        device=device,
    )
    _publish_transcript(root, item_id, record)
    return record


def _extract_wav(video: Path) -> Any:
    tmp = tempfile.NamedTemporaryFile(prefix="library-asr-", suffix=".wav", delete=False)
    tmp.close()
    dest = Path(tmp.name)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 44:
        dest.unlink(missing_ok=True)
        raise fail("decode-error")
    try:
        import numpy as np
    except ImportError as exc:
        dest.unlink(missing_ok=True)
        raise fail("dependency-missing") from exc
    try:
        with wave.open(str(dest), "rb") as handle:
            frames = handle.readframes(handle.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype("float32") / 32768.0
    finally:
        dest.unlink(missing_ok=True)
    return audio


def extractive_summary(text: str, language: str | None) -> tuple[str, list[str]]:
    """One or two sentences plus keywords. No local LLM; extractive only."""
    cleaned = (text or "").strip()
    if not cleaned:
        return "", []
    chinese = bool(language and str(language).startswith("zh")) or bool(re.search(r"[\u4e00-\u9fff]", cleaned))
    sentences = _split_sentences(cleaned, chinese=chinese)
    if chinese:
        summary = "".join(sentences[:2]).strip()
    else:
        summary = " ".join(sentences[:2]).strip()
    keywords = _keywords(cleaned, chinese=chinese, limit=6)
    return summary, keywords


def _split_sentences(text: str, *, chinese: bool) -> list[str]:
    if chinese:
        parts = re.split(r"(?<=[。！？!?])", text)
    else:
        parts = re.split(r"(?<=[.!?])\s+", text)
    out = [part.strip() for part in parts if part and part.strip()]
    return out or [text.strip()]


def _keywords(text: str, *, chinese: bool, limit: int) -> list[str]:
    counts: dict[str, int] = {}
    if chinese:
        for run in re.findall(r"[\u4e00-\u9fff]+", text):
            if len(run) == 1:
                token = run
                counts[token] = counts.get(token, 0) + 1
                continue
            if 2 <= len(run) <= 4:
                counts[run] = counts.get(run, 0) + 2
            for index in range(len(run) - 1):
                gram = run[index : index + 2]
                counts[gram] = counts.get(gram, 0) + 1
        for token in re.findall(r"[A-Za-z]{3,}", text):
            folded = token.casefold()
            if folded not in _EN_STOP:
                counts[folded] = counts.get(folded, 0) + 1
    else:
        for token in re.findall(r"[A-Za-z][A-Za-z']+", text):
            folded = token.casefold()
            if folded in _EN_STOP or len(folded) < 3:
                continue
            counts[folded] = counts.get(folded, 0) + 1
    ranked = sorted(counts.items(), key=lambda row: (-row[1], -len(row[0]), row[0]))
    out: list[str] = []
    for token, _count in ranked:
        if token in out:
            continue
        if any(token != other and token in other for other in out):
            continue
        out.append(token)
        if len(out) >= limit:
            break
    return out


def _publish_transcript(root: Path, item_id: str, record: dict[str, Any]) -> None:
    before = load_item(root, item_id)
    after = clone(before)
    after["transcript"] = record
    after = ordered_item(after)
    transact(root, [{"path": item_rel(item_id), "before": before, "after": after}])


def _pick_device() -> tuple[str, str]:
    try:
        import ctranslate2

        if int(ctranslate2.get_cuda_device_count() or 0) > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def _whisper_model(root: Path) -> tuple[Any, str]:
    global _WHISPER_MODEL, _WHISPER_DEVICE
    device, compute = _pick_device()
    if _WHISPER_MODEL is not None and _WHISPER_DEVICE == device:
        return _WHISPER_MODEL, device
    from faster_whisper import WhisperModel

    download_root = str(whisper_dir(root))
    _WHISPER_MODEL = WhisperModel(
        model_size(),
        device=device,
        compute_type=compute,
        download_root=download_root,
    )
    _WHISPER_DEVICE = device
    return _WHISPER_MODEL, device


def _seed_from_cache(dest: Path) -> None:
    if _has_model_bin(dest):
        return
    dest.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []
    env = os.environ.get("LIBRARY_WHISPER_CACHE")
    if type(env) is str and env.strip():
        candidates.append(Path(env.strip()))
    size_name = model_size()
    home_cache = Path.home() / ".cache"
    candidates.append(home_cache / "photoLibrary" / f"faster-whisper-{size_name}")
    candidates.append(home_cache / "huggingface" / "hub" / f"models--Systran--faster-whisper-{size_name}")
    for src in candidates:
        try:
            if not src.is_dir() or not _has_model_bin(src):
                continue
            shutil.copytree(src, dest, dirs_exist_ok=True)
            if _has_model_bin(dest):
                return
        except OSError:
            continue


def _download_model(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    from faster_whisper import WhisperModel

    device, compute = _pick_device()
    WhisperModel(
        model_size(),
        device=device,
        compute_type=compute,
        download_root=str(dest),
    )


def _ensure_runtime() -> None:
    try:
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401

        return
    except ImportError:
        pass
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *RUNTIME_PACKAGES, "numpy"],
        capture_output=True,
        text=True,
        check=False,
    )
    import importlib
    import site

    importlib.invalidate_caches()
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.append(user_site)
    try:
        import faster_whisper  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as exc:
        raise fail("dependency-missing") from exc
    if proc.returncode != 0:
        raise fail("dependency-missing")
