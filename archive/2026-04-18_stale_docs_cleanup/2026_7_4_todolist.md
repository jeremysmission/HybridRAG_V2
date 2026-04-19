# 2026_7_4_todolist

## Tomorrow's Priority Order

1. Fix workstation desktop installs.
   - Get both `CorpusForge` and `HybridRAG_V2` clean.
   - Verify `torch 2.7.1+cu128`, `built_cuda=12.8`, `cuda_available=True`.
   - Verify `tesseract` and `pdftoppm`.

2. Backup source.
   - This is the main dependency for the recovery sprint.
   - Once this is available, recovery dedup becomes the immediate first production action.

3. Start recovery dedup on the high-capacity local machine.
   - Do not wait on workstation chunking for this.
   - Use the machine with the known-good parser and OCR stack as the first trusted recovery lane.

4. Review a dedup sample before trusting the full reduction.
   - Use the document-level dedup review path first.
   - Do not rely on the chunk-level review report yet; that support slice is still conditional.

5. Prepare the reduced rebuild from the canonical list.
   - The goal is a smaller, cleaner corpus before rechunking and extraction.
   - Treat the rebuild as a recovery rebuild, not just a rerun.

6. Keep the workstation laptop as a helper lane if it passes full verification.
   - Controlled chunking tests
   - Shard support
   - Production support work

7. Make the workstation desktop the future 24/7 chunking lane once installs are stable.
   - Fixed location
   - Stable caches
   - No travel interruptions
   - Best fit for uninterrupted rechunking

## Immediate Dependencies

- The source folder is the main blocker for recovery dedup.
- Desktop install stability is the main blocker for a future 24/7 workstation lane.
- The first reduced rebuild should still happen on the high-capacity local machine because the parser and OCR stack there is already trusted.

## Short Version

- Backup the source folder.
- Fix desktop installs.
- Start dedup.
- Review duplicate samples.
- Prepare the reduced rebuild on the high-capacity local machine.
