# Tests & Test Data

This folder contains test data and test utilities.

## Contents

- `sample_transcripts/` — Real (non-sensitive) meeting transcripts for testing extraction quality

## Test Data Format

Use `.txt` or `.vtt` format transcripts. Test that the extraction agent:
- Correctly identifies action items
- Doesn't fabricate owners or dates
- Correctly excludes completed items from the active view
