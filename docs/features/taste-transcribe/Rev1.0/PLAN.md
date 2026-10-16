# Taste-Transcribe — optional local video speech

Sits on the Processing / Settings tip after #43. Does not close a Check.
No 23rd Check. No cloud API. No slyCut editing code.

Read PRODUCT F3 / F15 (`setup-ml transcribe`, `transcribe`, search),
CONTRACTS optional transcript, UI-SPEC Info + Processing, and this file.

slyCut's repo is private here; this slice uses the same Whisper-family
toolchain Steve already runs locally: **faster-whisper** `small`,
word timestamps, auto language, CTranslate2 GPU float16 with CPU int8
fallback, ffmpeg 16 kHz mono WAV (no PyAV). Setup.bat downloads the
model into `library-data/models/whisper/`.

## In scope

1. Queue stage **Transcribe** after objects. Videos with an audio
   stream only. Resumable. Same size+mtime is skipped. Settings
   `transcribeVideos` (default on) turns the stage off.
2. Store timestamped `transcript` on the item (segments + words),
   language, extractive one-or-two-sentence summary, and keywords.
   No local LLM is shipped; `summaryMethod` is `extractive`.
3. Search matches transcript / summary / keywords. Results show
   **Said in video** and open the viewer at that timestamp.
4. Info: collapsible transcript; a line click seeks. Chinese chrome.
5. Proofs use real spoken EN and ZH clips under
   `tests/fixtures/transcript/` (TTS; not silent or tone-only). A
   generated no-audio clip is only for the skip-no-audio path.

## Out of scope

slyCut timeline editing, cloud summarizers, a 23rd Check, S13/S14,
Win7 work.

## Gate

```
python -m tests.qa slice TASTE-TRANSCRIBE --root "$qaRoot/library-data" --artifacts $evidence
```

Artifacts under `docs/features/taste-transcribe/Rev1.0/assets/<run-id>/`.
16/22 unchanged.
