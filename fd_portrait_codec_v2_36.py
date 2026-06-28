#!/usr/bin/env python3
"""
Disciples: Sacred Lands - FD portrait decoder & encoder (standalone, no numpy)
VERSION 2.36

Requirement: pip install pillow

--------------------------------------------------------------------------
CHANGES SINCE v2.10 (the last published version):
  - `decode`/`list`/`replace` now work UNIFORMLY on any .DBI file (UNIT,
    MIDGARD, CAPITAL, BATTLE, ISO, TERRAIN, PALMAP, ScenEdit, Interf,
    Menus) - each block's format (portrait-style vs. ISO-style) is
    auto-detected, so one command handles every file and every block
    kind. (Previously needed separate decode/isodecode commands, and
    portrait- vs. ISO-blocks needed different replace commands.)
  - `encode`/`insert` (inserting a brand-new image under a new name) is
    now also unified: on UNIT.DBI it still uses its own, more compact,
    dedicated encoder with automatic name generation (e.g. `GP001`); on
    any other file it asks for an explicit name and uses the general
    ISO-style encoder. (Previously the latter was a separate `isoencode`
    command.)
  - Added `decodeall` - decodes every .DBI file found in a folder in one
    pass, each into its own output folder.
  - Added an `ow` flag (place it at the end of an encode/replace
    command) to overwrite the original file in place, with an automatic
    backup, instead of always creating a new `_mod` copy.
  - Added `info` (alongside `-h`/`--help`/no-args) to print this command
    reference.
  - Removed the `isodecode` and `isoencode` commands - both are fully
    covered by the now-unified `decode` and `encode`.
  - Dropped the optional IMGGRAB.BIN fallback for the Huffman init table
    (it was already unused internally - the table has been a built-in
    constant for a long time).
  - Major decoding-accuracy improvements across every file - large
    parts of MIDGARD.DBI, CAPITAL.DBI, Interf.dbi, ScenEdit.dbi, ISO.DBI
    and BATTLE.DBI that previously decoded as visible corruption (wrong
    colors, static-like noise, or missing rows) are now pixel-exact.
  - Fixed how transparency is handled for image areas that are partly
    "real" dark content and partly genuine empty background in the same
    picture (e.g. a building silhouette against open sky, or a roof's
    dark tiles) - both now render correctly in the same image, instead
    of the whole image being forced one way or the other.
  - Added a `--lang=ru` / `--lang=pl` switch (default: English) - every
    message the tool prints (this text, command output, errors) can now
    be shown in Russian or Polish instead.
  - Refined the transparency fix above for specific name-families where
    an "enclosed" dark region is genuine negative space, not real
    content (a sigil icon's open loop, a UI template's content slot,
    TERRAIN.DBI's object sprites) - confirmed in-game by the person.
  - Fixed the inverse problem on real head/bust portraits (UNIT.DBI
    especially): a stray dark pixel touching the canvas border could
    "drain" transparency into a much larger, genuinely-drawn dark area
    (hair, dark clothing) through a thin connected path. Portraits
    never have a real background margin, so these are now always
    rendered fully opaque.
  - Same fix for MIDGARD.DBI's TWD/TWE/TWH/TWU "terrain scene"
    backdrops (e.g. TWU0004) - their night sky was being rendered fully
    transparent instead of as a solid dark backdrop with stars, since
    these are complete standalone background images that never have a
    transparent margin either.
  - Added MIDGARD.DBI's THIEF item icons, ICONS.DBI's ICNSY badge icons,
    and the LOGOD/E/H/U per-race logo emblems to the "negative space,
    not real content" list from a couple of versions ago - the same
    lacy/cutout pattern (e.g. ICNSY000's ring was assumed to be a solid
    disc; it's a transparent-centered ring).
--------------------------------------------------------------------------

Usage:
  # Show this full command reference (also shown automatically for an
  # unrecognized/missing command):
  python fd_portrait_codec_standalone.py info

  # Export EVERY recognized block in a .DBI to PNG (auto-detects portrait
  # vs. ISO-style graphics per block - works on any .DBI file):
  python fd_portrait_codec_standalone.py decode UNIT.DBI output_dir/
  python fd_portrait_codec_standalone.py decode MIDGARD.DBI output_dir/

  # Decode EVERY .DBI file in a folder at once, each into its own
  # output folder named after the file (e.g. ISO.DBI -> ./ISO/) - handy
  # during active codec development, to re-export everything in one
  # shot after a change instead of calling 'decode' once per file:
  python fd_portrait_codec_standalone.py decodeall
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/ path/to/output/

  # Insert a NEW portrait into UNIT.DBI (default, recommended for modding -
  # does not overwrite anything, automatic GP### name generation):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI
  # Forced prefix+index (e.g. for native-style testing):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI FN150

  # Insert a NEW ISO-style graphic into any OTHER .DBI file - a NAME is
  # required (ISO object types use meaningful prefixes - e.g. GUN, GSY,
  # GLM, GIT, GRF - not an automatically generated number):
  python fd_portrait_codec_standalone.py encode my_image.png ISO.DBI NAME [ow]

  # Replace an EXISTING portrait slot (the old 'encode' behavior - overwrites
  # a given, named slot, no size limit):
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00

  # 'ow' flag (written at the END of the command, for encode/replace alike):
  # overwrites the original .DBI (with an automatic .dbi.bak backup first),
  # avoids UNIT_mod.DBI / UNIT_mod_mod.DBI chaining across several
  # consecutive insertions/replacements:
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI ow
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00 ow

  # List every recognized block in a .DBI, auto-classified as
  # portrait/iso/iso_partial (works the same on any .DBI file):
  python fd_portrait_codec_standalone.py list UNIT.DBI
  python fd_portrait_codec_standalone.py list MIDGARD.DBI

  # 'decode' also accepts an optional name-prefix filter:
  python fd_portrait_codec_standalone.py decode ISO.DBI output_dir/ GUN

  # EXPERIMENTAL: replace an EXISTING ISO-style graphic's image data
  # (keeps its name and bt; the new image's size does not need to match
  # the original) - 'replace' (above) already does this automatically
  # for any non-portrait block; call this directly only to force the
  # ISO-style encoder explicitly:
  python fd_portrait_codec_standalone.py isoreplace my_image.png ISO.DBI GUNN1307 [ow]
"""

import struct, sys, os, re, shutil
from pathlib import Path

# --- i18n: language switch (--lang=en|ru|pl, default en) ----------------
# Covers every user-facing runtime message (print()/sys.exit() calls in
# the cmd_* functions and main()) and the info/help text. Does NOT cover
# internal code comments/docstrings explaining algorithm mechanics -
# those stay English-only (for future development, not end users).

LANG = 'en'

STRINGS = {
    'en': {
        'no_palette': "Could not find a palette block (bt==2) in the file.",
        'loading_image': "Loading image: {path}",
        'ok': "OK",
        'overwrite_suffix': "  (overwritten, .bak saved)",
        'roundtrip_ok': "100% OK \u2713",
        'roundtrip_bad': "{pct:.2f}% - CHECK THIS!",
        'suspicious_entries': "{n} suspicious entries!",
        'toc_check_ok': "  TOC check: OK (all entries consistent)",

        # cmd_isoencode
        'iso_name_taken': "The name '{name}' is already taken in the file - choose a different one.",
        'iso_size': "  Size: {w}x{h}",
        'iso_raw_stream': "  Raw record stream: {n} bytes",
        'iso_compressed': "  Compressed: {n} bytes",
        'extending_index': "  Extending name-index table (inserting '{name}' at its alphabetical position)...",
        'iso_trailing_note': "  Note: there is {n} bytes of data AFTER the chain-TOC (a second "
                              "name-index table, already kept in sync with '{name}' by "
                              "insert_into_name_index() above - see find_all_name_index_blocks).",
        'iso_saved': "  Saved: {path}{suffix}  (file size {old} -> {new} bytes)",
        'iso_name_index_check': "  Name-index check: {result}",
        'iso_chain_toc_check': "  Chain-TOC check: {result}",
        'iso_roundtrip': "  Round-trip validation (decode back): {result}",
        'iso_new_name': "\n  NEW GRAPHIC NAME: {name}",

        # cmd_isoreplace
        'iso_no_graphic': "No ISO graphic named '{name}'.\nAvailable names (sample): {names}...",
        'iso_size_with_original': "  Size: {w}x{h}  (original was {ow}x{oh})",
        'iso_resize_line1': "\n  The encoded image ({n} bytes) does NOT fit in",
        'iso_resize_line2': "  slot '{name}'s original size ({n} bytes).",
        'iso_resize_mode': "  -> TOC-update mode: the block grows, the chain-TOC is updated automatically.",
        'iso_padding': "  Padding: +{n} bytes (so the block size and TOC offsets don't change)",
        'iso_toc_warning': "  \u26a0 WARNING: after the TOC update, {n} suspicious entries were found.",
        'isor_saved': "  Saved: {path}{suffix}  (block {sign}{delta} bytes)",

        # cmd_list
        'list_header': "{name:<12} {kind:>12} {size:>10}  {position}",
        'col_name': "Name",
        'col_kind': "Kind",
        'col_size': "Size",
        'col_position': "Position",
        'list_total': "\nTotal: {n} blocks ({summary})",

        # cmd_decode
        'decode_line_portrait': "  {name}.png  ({w}x{h}, portrait)  [OK]",
        'decode_line_iso': "  {name}.png  ({w}x{h} canvas, {cw}x{ch} cropped, {kind})  [{tag}]",
        'decode_tag_partial': "PARTIAL (gap_bytes={gb}, unconsumed={u})",
        'decode_error_line': "  {name}: ERROR ({e}) - skipped",
        'decode_summary': "\n{n} blocks processed -> {out_dir}  ({clean} clean, {partial} partial, {error} errors)",

        # cmd_decode_all
        'decodeall_dir_error': "Could not read directory '{dir}': {e}",
        'decodeall_none_found': "No .DBI files found in '{dir}'.",
        'decodeall_found': "Found {n} .DBI file(s) in '{dir}': {names}\n",
        'decodeall_processing': "=== {fname}  ->  {out_dir}/ ===",
        'decodeall_skipped': "  SKIPPED: {e}",
        'decodeall_skipped_unexpected': "  SKIPPED (unexpected error): {e}",
        'decodeall_summary_title': "decodeall SUMMARY",
        'decodeall_summary_skipped_line': "  {fname:<20} -> {out_dir:<20}  SKIPPED",
        'decodeall_summary_line': "  {fname:<20} -> {out_dir:<20}  {total:>4} blocks "
                                  "({clean} clean, {partial} partial, {error} errors)",

        # cmd_insert
        'insert_size_error': "Size error: the image height is {h}, but it must be 67.",
        'insert_generated_name': "  Generated name: {name}  (bt={bt})",
        'compressing': "Compressing ({w}x{h})...",
        'insert_index_followup': "  (the final, whole-file name-index check follows after saving)",
        'insert_saved': "  Saved: {path}{suffix}  (file size {old} -> {new} bytes, +{delta})",
        'insert_chain_toc_check': "  Chain-TOC check: {result}",
        'insert_name_index_check_final': "  Name-index check (on final file): {result}",
        'pixel_match': "  Pixel match: {result}",
        'pixel_match_ok': "100% OK \u2713",
        'pixel_match_err': "ERROR!",
        'insert_new_name': "\n  NEW PORTRAIT NAME: {name}",

        # cmd_encode
        'encode_no_portrait': "No portrait-style block named '{name}'.\nAvailable names (sample): {names}...",
        'encode_size_error': "Size error: the image is {w}x{h}, but the portrait must be {tw}x{th}",
        'encode_resize_line1': "\n  The encoded image ({n} bytes) does NOT fit in",
        'encode_resize_line2': "  slot '{name}'s original size ({n} bytes).",
        'encode_resize_line3': "  -> TOC-update mode: the block grows, the index table at the end of",
        'encode_resize_line4': "    the file and the global header pointer to it are updated automatically.",
        'encode_padding': "  Padding: +{n} bytes (the stream was shorter than the original slot; "
                           "padded so that the block size and TOC offsets don't change)",
        'encode_orig_stream': "  Original stream: {old} bytes -> New: {new} bytes",
        'encode_toc_warning': "  \u26a0 WARNING: after the TOC update, {n} suspicious entries were found "
                               "(details: can be checked by calling verify_dbi_toc after cmd_encode).",
        'encode_saved': "  Saved: {path}{suffix}",
        'encode_block_delta': "  (Block {sign}{delta} bytes)",
        'encode_checking': "Checking...",

        # main()
        'main_invalid_prefix': "Invalid prefix+index format: '{val}' (e.g. correct: FN150)",
        'main_encode_needs_name': "'{dbi}' is not UNIT.DBI, so 'encode' needs an explicit NAME:\n"
                                   "  python script.py encode {img} {dbi} NAME [ow]",
        'main_no_block_named': "No block named '{name}' found in {dbi}.\nAvailable names (sample): {names}...",
        'insert_bad_size': "Insert mode only supports 55x67 (S00) or 115x67 (L00) sized images, this is {w}x{h}.",
        'insert_name_taken': "The name '{name}' is already taken in the file - choose a different index.",
        'pillow_missing': "  [!] Pillow is not installed: pip install pillow",
        'pillow_missing_pixel_data': "  Pixel data: {w}x{h}, palette: {n} colors",
        'pillow_missing_short': "Error: pip install pillow",
    },

    'ru': {
        'no_palette': "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043d\u0430\u0439\u0442\u0438 \u0431\u043b\u043e\u043a \u043f\u0430\u043b\u0438\u0442\u0440\u044b (bt==2) \u0432 \u0444\u0430\u0439\u043b\u0435.",
        'loading_image': "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f: {path}",
        'ok': "OK",
        'overwrite_suffix': "  (\u0444\u0430\u0439\u043b \u043f\u0435\u0440\u0435\u0437\u0430\u043f\u0438\u0441\u0430\u043d, .bak \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d)",
        'roundtrip_ok': "100% OK \u2713",
        'roundtrip_bad': "{pct:.2f}% - \u043f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0432\u0440\u0443\u0447\u043d\u0443\u044e!",
        'suspicious_entries': "{n} \u043f\u043e\u0434\u043e\u0437\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u0437\u0430\u043f\u0438\u0441\u0435\u0439!",
        'toc_check_ok': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 TOC: OK (\u0432\u0441\u0435 \u0437\u0430\u043f\u0438\u0441\u0438 \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u044b)",

        'iso_name_taken': "\u0418\u043c\u044f '{name}' \u0443\u0436\u0435 \u0437\u0430\u043d\u044f\u0442\u043e \u0432 \u0444\u0430\u0439\u043b\u0435 - \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u0440\u0443\u0433\u043e\u0435.",
        'iso_size': "  \u0420\u0430\u0437\u043c\u0435\u0440: {w}x{h}",
        'iso_raw_stream': "  \u0421\u044b\u0440\u043e\u0439 \u043f\u043e\u0442\u043e\u043a \u0437\u0430\u043f\u0438\u0441\u0435\u0439: {n} \u0431\u0430\u0439\u0442",
        'iso_compressed': "  \u0421\u0436\u0430\u0442\u043e: {n} \u0431\u0430\u0439\u0442",
        'extending_index': "  \u0420\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u0438\u0435 \u0442\u0430\u0431\u043b\u0438\u0446\u044b \u0438\u043c\u0451\u043d (\u0432\u0441\u0442\u0430\u0432\u043b\u044f\u0435\u043c '{name}' \u043d\u0430 \u0435\u0451 \u0430\u043b\u0444\u0430\u0432\u0438\u0442\u043d\u0443\u044e \u043f\u043e\u0437\u0438\u0446\u0438\u044e)...",
        'iso_trailing_note': "  \u041f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u0435: \u043f\u043e\u0441\u043b\u0435 chain-TOC \u0435\u0441\u0442\u044c \u0435\u0449\u0451 {n} \u0431\u0430\u0439\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 "
                              "(\u0432\u0442\u043e\u0440\u0430\u044f \u0442\u0430\u0431\u043b\u0438\u0446\u0430 \u0438\u043c\u0451\u043d, \u0443\u0436\u0435 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u0430\u044f \u0441 '{name}' "
                              "\u0432\u044b\u0448\u0435 \u0432\u044b\u0437\u043e\u0432\u043e\u043c insert_into_name_index() - \u0441\u043c. find_all_name_index_blocks).",
        'iso_saved': "  \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {path}{suffix}  (\u0440\u0430\u0437\u043c\u0435\u0440 \u0444\u0430\u0439\u043b\u0430 {old} -> {new} \u0431\u0430\u0439\u0442)",
        'iso_name_index_check': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0442\u0430\u0431\u043b\u0438\u0446\u044b \u0438\u043c\u0451\u043d: {result}",
        'iso_chain_toc_check': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 chain-TOC: {result}",
        'iso_roundtrip': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043e\u0431\u0440\u0430\u0442\u043d\u044b\u043c \u0434\u0435\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435\u043c: {result}",
        'iso_new_name': "\n  \u041d\u041e\u0412\u041e\u0415 \u0418\u041c\u042f \u0418\u0417\u041e\u0411\u0420\u0410\u0416\u0415\u041d\u0418\u042f: {name}",

        'iso_no_graphic': "\u041d\u0435\u0442 ISO-\u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f \u0441 \u0438\u043c\u0435\u043d\u0435\u043c '{name}'.\n\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0438\u043c\u0435\u043d\u0430 (\u043f\u0440\u0438\u043c\u0435\u0440): {names}...",
        'iso_size_with_original': "  \u0420\u0430\u0437\u043c\u0435\u0440: {w}x{h}  (\u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b \u0431\u044b\u043b {ow}x{oh})",
        'iso_resize_line1': "\n  \u0417\u0430\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 ({n} \u0431\u0430\u0439\u0442) \u041d\u0435 \u0432\u043c\u0435\u0449\u0430\u0435\u0442\u0441\u044f \u0432",
        'iso_resize_line2': "  \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0440\u0430\u0437\u043c\u0435\u0440 \u0441\u043b\u043e\u0442\u0430 '{name}' ({n} \u0431\u0430\u0439\u0442).",
        'iso_resize_mode': "  -> \u0440\u0435\u0436\u0438\u043c \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f TOC: \u0431\u043b\u043e\u043a \u0443\u0432\u0435\u043b\u0438\u0447\u0438\u0432\u0430\u0435\u0442\u0441\u044f, chain-TOC \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u0435\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.",
        'iso_padding': "  \u0414\u043e\u0431\u0438\u0432\u043a\u0430: +{n} \u0431\u0430\u0439\u0442 (\u0447\u0442\u043e\u0431\u044b \u0440\u0430\u0437\u043c\u0435\u0440 \u0431\u043b\u043e\u043a\u0430 \u0438 \u0441\u043c\u0435\u0449\u0435\u043d\u0438\u044f TOC \u043d\u0435 \u0438\u0437\u043c\u0435\u043d\u0438\u043b\u0438\u0441\u044c)",
        'iso_toc_warning': "  \u26a0 \u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435: \u043f\u043e\u0441\u043b\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f TOC \u043d\u0430\u0439\u0434\u0435\u043d\u043e {n} \u043f\u043e\u0434\u043e\u0437\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u0437\u0430\u043f\u0438\u0441\u0435\u0439.",
        'isor_saved': "  \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {path}{suffix}  (\u0431\u043b\u043e\u043a {sign}{delta} \u0431\u0430\u0439\u0442)",

        'list_header': "{name:<12} {kind:>12} {size:>10}  {position}",
        'col_name': "\u0418\u043c\u044f",
        'col_kind': "\u0442\u0438\u043f",
        'col_size': "\u0440\u0430\u0437\u043c\u0435\u0440",
        'col_position': "\u041f\u043e\u0437\u0438\u0446\u0438\u044f",
        'list_total': "\n\u0412\u0441\u0435\u0433\u043e: {n} \u0431\u043b\u043e\u043a\u043e\u0432 ({summary})",

        'decode_line_portrait': "  {name}.png  ({w}x{h}, portrait)  [OK]",
        'decode_line_iso': "  {name}.png  ({w}x{h} \u0445\u043e\u043b\u0441\u0442, {cw}x{ch} \u043e\u0431\u0440\u0435\u0437\u0430\u043d\u043e, {kind})  [{tag}]",
        'decode_tag_partial': "\u0427\u0410\u0421\u0422\u0418\u0427\u041d\u041e (gap_bytes={gb}, unconsumed={u})",
        'decode_error_line': "  {name}: \u041e\u0428\u0418\u0411\u041a\u0410 ({e}) - \u043f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e",
        'decode_summary': "\n\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e \u0431\u043b\u043e\u043a\u043e\u0432: {n} -> {out_dir}  "
                          "({clean} \u0447\u0438\u0441\u0442\u044b\u0445, {partial} \u0447\u0430\u0441\u0442\u0438\u0447\u043d\u044b\u0445, {error} \u043e\u0448\u0438\u0431\u043e\u043a)",

        'decodeall_dir_error': "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u0442\u044c \u043f\u0430\u043f\u043a\u0443 '{dir}': {e}",
        'decodeall_none_found': "\u0424\u0430\u0439\u043b\u044b .DBI \u0432 '{dir}' \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b.",
        'decodeall_found': "\u041d\u0430\u0439\u0434\u0435\u043d\u043e {n} \u0444\u0430\u0439\u043b(\u043e\u0432) .DBI \u0432 '{dir}': {names}\n",
        'decodeall_processing': "=== {fname}  ->  {out_dir}/ ===",
        'decodeall_skipped': "  \u041f\u0420\u041e\u041f\u0423\u0429\u0415\u041d\u041e: {e}",
        'decodeall_skipped_unexpected': "  \u041f\u0420\u041e\u041f\u0423\u0429\u0415\u041d\u041e (\u043d\u0435\u043e\u0436\u0438\u0434\u0430\u043d\u043d\u0430\u044f \u043e\u0448\u0438\u0431\u043a\u0430): {e}",
        'decodeall_summary_title': "\u0438\u0442\u043e\u0433\u0438 decodeall",
        'decodeall_summary_skipped_line': "  {fname:<20} -> {out_dir:<20}  \u041f\u0420\u041e\u041f\u0423\u0429\u0415\u041d\u041e",
        'decodeall_summary_line': "  {fname:<20} -> {out_dir:<20}  {total:>4} \u0431\u043b\u043e\u043a\u043e\u0432 "
                                  "({clean} \u0447\u0438\u0441\u0442\u044b\u0445, {partial} \u0447\u0430\u0441\u0442\u0438\u0447\u043d\u044b\u0445, {error} \u043e\u0448\u0438\u0431\u043e\u043a)",

        'insert_size_error': "\u041e\u0448\u0438\u0431\u043a\u0430 \u0440\u0430\u0437\u043c\u0435\u0440\u0430: \u0432\u044b\u0441\u043e\u0442\u0430 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f {h}, \u0430 \u0434\u043e\u043b\u0436\u043d\u0430 \u0431\u044b\u0442\u044c 67.",
        'insert_generated_name': "  \u0421\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0435 \u0438\u043c\u044f: {name}  (bt={bt})",
        'compressing': "\u0421\u0436\u0430\u0442\u0438\u0435 ({w}x{h})...",
        'insert_index_followup': "  (\u0438\u0442\u043e\u0433\u043e\u0432\u0430\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0442\u0430\u0431\u043b\u0438\u0446\u044b \u0438\u043c\u0451\u043d \u043f\u043e \u0432\u0441\u0435\u043c\u0443 \u0444\u0430\u0439\u043b\u0443 \u0431\u0443\u0434\u0435\u0442 \u043f\u043e\u0441\u043b\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f)",
        'insert_saved': "  \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {path}{suffix}  (\u0440\u0430\u0437\u043c\u0435\u0440 \u0444\u0430\u0439\u043b\u0430 {old} -> {new} \u0431\u0430\u0439\u0442, +{delta})",
        'insert_chain_toc_check': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 chain-TOC: {result}",
        'insert_name_index_check_final': "  \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0442\u0430\u0431\u043b\u0438\u0446\u044b \u0438\u043c\u0451\u043d (\u0438\u0442\u043e\u0433\u043e\u0432\u044b\u0439 \u0444\u0430\u0439\u043b): {result}",
        'pixel_match': "  \u0421\u043e\u0432\u043f\u0430\u0434\u0435\u043d\u0438\u0435 \u043f\u0438\u043a\u0441\u0435\u043b\u0435\u0439: {result}",
        'pixel_match_ok': "100% OK \u2713",
        'pixel_match_err': "\u041e\u0428\u0418\u0411\u041a\u0410!",
        'insert_new_name': "\n  \u041d\u041e\u0412\u041e\u0415 \u0418\u041c\u042f \u041f\u041e\u0420\u0422\u0420\u0415\u0422\u0410: {name}",

        'encode_no_portrait': "\u041d\u0435\u0442 \u043f\u043e\u0440\u0442\u0440\u0435\u0442\u043d\u043e\u0433\u043e \u0431\u043b\u043e\u043a\u0430 \u0441 \u0438\u043c\u0435\u043d\u0435\u043c '{name}'.\n\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0438\u043c\u0435\u043d\u0430 (\u043f\u0440\u0438\u043c\u0435\u0440): {names}...",
        'encode_size_error': "\u041e\u0448\u0438\u0431\u043a\u0430 \u0440\u0430\u0437\u043c\u0435\u0440\u0430: \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 {w}x{h}, \u0430 \u043f\u043e\u0440\u0442\u0440\u0435\u0442 \u0434\u043e\u043b\u0436\u0435\u043d \u0438\u043c\u0435\u0442\u044c \u0440\u0430\u0437\u043c\u0435\u0440 {tw}x{th}",
        'encode_resize_line1': "\n  \u0417\u0430\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 ({n} \u0431\u0430\u0439\u0442) \u041d\u0435 \u0432\u043c\u0435\u0449\u0430\u0435\u0442\u0441\u044f \u0432",
        'encode_resize_line2': "  \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0440\u0430\u0437\u043c\u0435\u0440 \u0441\u043b\u043e\u0442\u0430 '{name}' ({n} \u0431\u0430\u0439\u0442).",
        'encode_resize_line3': "  -> \u0440\u0435\u0436\u0438\u043c \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f TOC: \u0431\u043b\u043e\u043a \u0443\u0432\u0435\u043b\u0438\u0447\u0438\u0432\u0430\u0435\u0442\u0441\u044f, \u0442\u0430\u0431\u043b\u0438\u0446\u0430 \u0432 \u043a\u043e\u043d\u0446\u0435 \u0444\u0430\u0439\u043b\u0430",
        'encode_resize_line4': "    \u0438 \u0433\u043b\u043e\u0431\u0430\u043b\u044c\u043d\u044b\u0439 \u0443\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044c \u0432 \u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043a\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u044e\u0442\u0441\u044f \u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u0438.",
        'encode_padding': "  \u0414\u043e\u0431\u0438\u0432\u043a\u0430: +{n} \u0431\u0430\u0439\u0442 (\u043f\u043e\u0442\u043e\u043a \u0431\u044b\u043b \u043a\u043e\u0440\u043e\u0442\u0447\u0435 \u0438\u0441\u0445\u043e\u0434\u043d\u043e\u0433\u043e \u0441\u043b\u043e\u0442\u0430; "
                          "\u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e, \u0447\u0442\u043e\u0431\u044b \u0440\u0430\u0437\u043c\u0435\u0440 \u0431\u043b\u043e\u043a\u0430 \u0438 \u0441\u043c\u0435\u0449\u0435\u043d\u0438\u044f TOC \u043d\u0435 \u0438\u0437\u043c\u0435\u043d\u0438\u043b\u0438\u0441\u044c)",
        'encode_orig_stream': "  \u0418\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u043f\u043e\u0442\u043e\u043a: {old} \u0431\u0430\u0439\u0442 -> \u043d\u043e\u0432\u044b\u0439: {new} \u0431\u0430\u0439\u0442",
        'encode_toc_warning': "  \u26a0 \u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435: \u043f\u043e\u0441\u043b\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f TOC \u043d\u0430\u0439\u0434\u0435\u043d\u043e {n} \u043f\u043e\u0434\u043e\u0437\u0440\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u0437\u0430\u043f\u0438\u0441\u0435\u0439 "
                              "(\u0434\u0435\u0442\u0430\u043b\u0438: \u043c\u043e\u0436\u043d\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0432\u044b\u0437\u043e\u0432\u043e\u043c verify_dbi_toc \u043f\u043e\u0441\u043b\u0435 cmd_encode).",
        'encode_saved': "  \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {path}{suffix}",
        'encode_block_delta': "  (\u0431\u043b\u043e\u043a {sign}{delta} \u0431\u0430\u0439\u0442)",
        'encode_checking': "\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430...",

        'main_invalid_prefix': "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 \u043f\u0440\u0435\u0444\u0438\u043a\u0441\u0430+\u0438\u043d\u0434\u0435\u043a\u0441\u0430: '{val}' (\u043d\u0430\u043f\u0440\u0438\u043c\u0435\u0440, \u0432\u0435\u0440\u043d\u043e: FN150)",
        'main_encode_needs_name': "'{dbi}' \u2014 \u044d\u0442\u043e \u043d\u0435 UNIT.DBI, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0434\u043b\u044f 'encode' \u043d\u0443\u0436\u043d\u043e \u044f\u0432\u043d\u043e \u0443\u043a\u0430\u0437\u0430\u0442\u044c \u0438\u043c\u044f:\n"
                                   "  python script.py encode {img} {dbi} NAME [ow]",
        'main_no_block_named': "\u0411\u043b\u043e\u043a \u0441 \u0438\u043c\u0435\u043d\u0435\u043c '{name}' \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0432 {dbi}.\n\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0438\u043c\u0435\u043d\u0430 (\u043f\u0440\u0438\u043c\u0435\u0440): {names}...",
        'insert_bad_size': "\u0420\u0435\u0436\u0438\u043c insert \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0440\u0430\u0437\u043c\u0435\u0440\u044b 55x67 (S00) \u0438\u043b\u0438 115x67 (L00), \u0430 \u044d\u0442\u043e {w}x{h}.",
        'insert_name_taken': "\u0418\u043c\u044f '{name}' \u0443\u0436\u0435 \u0437\u0430\u043d\u044f\u0442\u043e \u0432 \u0444\u0430\u0439\u043b\u0435 - \u0432\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0434\u0440\u0443\u0433\u043e\u0439 \u0438\u043d\u0434\u0435\u043a\u0441.",
        'pillow_missing': "  [!] Pillow \u043d\u0435 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d: pip install pillow",
        'pillow_missing_pixel_data': "  \u0414\u0430\u043d\u043d\u044b\u0435 \u043f\u0438\u043a\u0441\u0435\u043b\u0435\u0439: {w}x{h}, \u043f\u0430\u043b\u0438\u0442\u0440\u0430: {n} \u0446\u0432\u0435\u0442\u043e\u0432",
        'pillow_missing_short': "\u041e\u0448\u0438\u0431\u043a\u0430: pip install pillow",
    },

    'pl': {
        'no_palette': "Nie znaleziono bloku palety (bt==2) w pliku.",
        'loading_image': "Wczytywanie obrazu: {path}",
        'ok': "OK",
        'overwrite_suffix': "  (nadpisano, zapisano .bak)",
        'roundtrip_ok': "100% OK \u2713",
        'roundtrip_bad': "{pct:.2f}% - SPRAWD\u0179 TO!",
        'suspicious_entries': "{n} podejrzanych wpis\u00f3w!",
        'toc_check_ok': "  Sprawdzenie TOC: OK (wszystkie wpisy zgodne)",

        'iso_name_taken': "Nazwa '{name}' jest ju\u017c zaj\u0119ta w tym pliku - wybierz inn\u0105.",
        'iso_size': "  Rozmiar: {w}x{h}",
        'iso_raw_stream': "  Surowy strumie\u0144 rekord\u00f3w: {n} bajt\u00f3w",
        'iso_compressed': "  Skompresowano: {n} bajt\u00f3w",
        'extending_index': "  Rozszerzanie tabeli nazw (wstawianie '{name}' na jej alfabetycznej pozycji)...",
        'iso_trailing_note': "  Uwaga: po chain-TOC znajduje si\u0119 jeszcze {n} bajt\u00f3w danych "
                              "(druga tabela nazw, ju\u017c zsynchronizowana z '{name}' przez "
                              "insert_into_name_index() powy\u017cej - zob. find_all_name_index_blocks).",
        'iso_saved': "  Zapisano: {path}{suffix}  (rozmiar pliku {old} -> {new} bajt\u00f3w)",
        'iso_name_index_check': "  Sprawdzenie tabeli nazw: {result}",
        'iso_chain_toc_check': "  Sprawdzenie chain-TOC: {result}",
        'iso_roundtrip': "  Walidacja zwrotna (ponowne dekodowanie): {result}",
        'iso_new_name': "\n  NOWA NAZWA GRAFIKI: {name}",

        'iso_no_graphic': "Nie znaleziono grafiki ISO o nazwie '{name}'.\nDost\u0119pne nazwy (przyk\u0142ad): {names}...",
        'iso_size_with_original': "  Rozmiar: {w}x{h}  (oryginalny by\u0142 {ow}x{oh})",
        'iso_resize_line1': "\n  Zakodowany obraz ({n} bajt\u00f3w) NIE mie\u015bci si\u0119 w",
        'iso_resize_line2': "  oryginalnym rozmiarze slotu '{name}' ({n} bajt\u00f3w).",
        'iso_resize_mode': "  -> tryb aktualizacji TOC: blok si\u0119 powi\u0119ksza, chain-TOC jest aktualizowany automatycznie.",
        'iso_padding': "  Dope\u0142nienie: +{n} bajt\u00f3w (aby rozmiar bloku i przesuni\u0119cia TOC nie zmieni\u0142y si\u0119)",
        'iso_toc_warning': "  \u26a0 OSTRZE\u017bENIE: po aktualizacji TOC znaleziono {n} podejrzanych wpis\u00f3w.",
        'isor_saved': "  Zapisano: {path}{suffix}  (blok {sign}{delta} bajt\u00f3w)",

        'list_header': "{name:<12} {kind:>12} {size:>10}  {position}",
        'col_name': "Nazwa",
        'col_kind': "Typ",
        'col_size': "Rozmiar",
        'col_position': "Pozycja",
        'list_total': "\n\u0141\u0105cznie: {n} blok\u00f3w ({summary})",

        'decode_line_portrait': "  {name}.png  ({w}x{h}, portrait)  [OK]",
        'decode_line_iso': "  {name}.png  (p\u0142\u00f3tno {w}x{h}, przyci\u0119te do {cw}x{ch}, {kind})  [{tag}]",
        'decode_tag_partial': "CZ\u0118\u015aCIOWO (gap_bytes={gb}, unconsumed={u})",
        'decode_error_line': "  {name}: B\u0141\u0104D ({e}) - pomini\u0119to",
        'decode_summary': "\nPrzetworzono blok\u00f3w: {n} -> {out_dir}  "
                          "({clean} czystych, {partial} cz\u0119\u015bciowych, {error} b\u0142\u0119d\u00f3w)",

        'decodeall_dir_error': "Nie uda\u0142o si\u0119 odczyta\u0107 katalogu '{dir}': {e}",
        'decodeall_none_found': "Nie znaleziono plik\u00f3w .DBI w '{dir}'.",
        'decodeall_found': "Znaleziono {n} plik(\u00f3w) .DBI w '{dir}': {names}\n",
        'decodeall_processing': "=== {fname}  ->  {out_dir}/ ===",
        'decodeall_skipped': "  POMINI\u0118TO: {e}",
        'decodeall_skipped_unexpected': "  POMINI\u0118TO (nieoczekiwany b\u0142\u0105d): {e}",
        'decodeall_summary_title': "PODSUMOWANIE decodeall",
        'decodeall_summary_skipped_line': "  {fname:<20} -> {out_dir:<20}  POMINI\u0118TO",
        'decodeall_summary_line': "  {fname:<20} -> {out_dir:<20}  {total:>4} blok\u00f3w "
                                  "({clean} czystych, {partial} cz\u0119\u015bciowych, {error} b\u0142\u0119d\u00f3w)",

        'insert_size_error': "B\u0142\u0105d rozmiaru: wysoko\u015b\u0107 obrazu to {h}, a musi by\u0107 67.",
        'insert_generated_name': "  Wygenerowana nazwa: {name}  (bt={bt})",
        'compressing': "Kompresja ({w}x{h})...",
        'insert_index_followup': "  (ko\u0144cowe sprawdzenie tabeli nazw dla ca\u0142ego pliku nast\u0105pi po zapisaniu)",
        'insert_saved': "  Zapisano: {path}{suffix}  (rozmiar pliku {old} -> {new} bajt\u00f3w, +{delta})",
        'insert_chain_toc_check': "  Sprawdzenie chain-TOC: {result}",
        'insert_name_index_check_final': "  Sprawdzenie tabeli nazw (na ko\u0144cowym pliku): {result}",
        'pixel_match': "  Zgodno\u015b\u0107 pikseli: {result}",
        'pixel_match_ok': "100% OK \u2713",
        'pixel_match_err': "B\u0141\u0104D!",
        'insert_new_name': "\n  NOWA NAZWA PORTRETU: {name}",

        'encode_no_portrait': "Nie znaleziono bloku portretowego o nazwie '{name}'.\nDost\u0119pne nazwy (przyk\u0142ad): {names}...",
        'encode_size_error': "B\u0142\u0105d rozmiaru: obraz ma {w}x{h}, a portret musi mie\u0107 rozmiar {tw}x{th}",
        'encode_resize_line1': "\n  Zakodowany obraz ({n} bajt\u00f3w) NIE mie\u015bci si\u0119 w",
        'encode_resize_line2': "  oryginalnym rozmiarze slotu '{name}' ({n} bajt\u00f3w).",
        'encode_resize_line3': "  -> tryb aktualizacji TOC: blok si\u0119 powi\u0119ksza, tabela na ko\u0144cu pliku",
        'encode_resize_line4': "    i globalny wska\u017anik do niej s\u0105 aktualizowane automatycznie.",
        'encode_padding': "  Dope\u0142nienie: +{n} bajt\u00f3w (strumie\u0144 by\u0142 kr\u00f3tszy ni\u017c oryginalny slot; "
                          "dope\u0142niono, aby rozmiar bloku i przesuni\u0119cia TOC nie zmieni\u0142y si\u0119)",
        'encode_orig_stream': "  Oryginalny strumie\u0144: {old} bajt\u00f3w -> nowy: {new} bajt\u00f3w",
        'encode_toc_warning': "  \u26a0 OSTRZE\u017bENIE: po aktualizacji TOC znaleziono {n} podejrzanych wpis\u00f3w "
                              "(szczeg\u00f3\u0142y: mo\u017cna sprawdzi\u0107 wywo\u0142uj\u0105c verify_dbi_toc po cmd_encode).",
        'encode_saved': "  Zapisano: {path}{suffix}",
        'encode_block_delta': "  (blok {sign}{delta} bajt\u00f3w)",
        'encode_checking': "Sprawdzanie...",

        'main_invalid_prefix': "Nieprawid\u0142owy format prefiksu+indeksu: '{val}' (np. poprawnie: FN150)",
        'main_encode_needs_name': "'{dbi}' to nie UNIT.DBI, wi\u0119c 'encode' wymaga podania NAZWY:\n"
                                   "  python script.py encode {img} {dbi} NAME [ow]",
        'main_no_block_named': "Nie znaleziono bloku o nazwie '{name}' w {dbi}.\nDost\u0119pne nazwy (przyk\u0142ad): {names}...",
        'insert_bad_size': "Tryb insert obs\u0142uguje tylko obrazy o rozmiarze 55x67 (S00) lub 115x67 (L00), a to jest {w}x{h}.",
        'insert_name_taken': "Nazwa '{name}' jest ju\u017c zaj\u0119ta w tym pliku - wybierz inny indeks.",
        'pillow_missing': "  [!] Pillow nie jest zainstalowane: pip install pillow",
        'pillow_missing_pixel_data': "  Dane pikseli: {w}x{h}, paleta: {n} kolor\u00f3w",
        'pillow_missing_short': "B\u0142\u0105d: pip install pillow",
    },
}


def t(key, **kwargs):
    """Fetch and format a user-facing string in the current `LANG`,
    falling back to English if the key/language is missing."""
    table = STRINGS.get(LANG) or STRINGS['en']
    template = table.get(key) or STRINGS['en'].get(key, key)
    return template.format(**kwargs) if kwargs else template


# Full translated info/help text (header + changes-since-v2.10 + usage
# examples) for 'ru'/'pl'. The English version is NOT duplicated here -
# it's the module's own __doc__ (see print_help()), since that also
# doubles as the file's normal Python-level documentation.
HELP_TEXT = {
    'ru': """
Disciples: Sacred Lands - декодер и кодировщик портретов FD (автономный, без numpy)
ВЕРСИЯ 2.36

Требуется: pip install pillow

--------------------------------------------------------------------------
Изменения с версии v2.10 (последней опубликованной версии):
  - `decode`/`list`/`replace` теперь работают единообразно с любым
    файлом .DBI (UNIT, MIDGARD, CAPITAL, BATTLE, ISO, TERRAIN, PALMAP,
    ScenEdit, Interf, Menus) - формат каждого блока (портретный
    или ISO-стиль) определяется автоматически, поэтому одна
    команда обрабатывает любой файл и любой тип блока. (Раньше
    требовались отдельные команды decode/isodecode, а для
    портретных и ISO-блоков требовались разные команды replace.)
  - `encode`/`insert` (вставка совершенно нового изображения под
    новым именем) теперь также унифицирована: для UNIT.DBI
    всё ещё используется собственный, более компактный кодировщик
    с автоматической генерацией имени (например, `GP001`); для
    любого другого файла запрашивается явное имя, и используется
    общий кодировщик ISO-стиля. (Раньше это была отдельная
    команда `isoencode`.)
  - Добавлена команда `decodeall` - декодирует все файлы .DBI в
    папке за один проход, каждый в свою собственную выходную папку.
  - Добавлен флаг `ow` (указывается в конце команды
    encode/replace) для перезаписи исходного файла на месте, с
    автоматическим резервным копированием, вместо создания
    новой копии `_mod`.
  - Добавлена команда `info` (наряду с `-h`/`--help`/без
    аргументов) для вывода этого справочника команд.
  - Удалены команды `isodecode` и `isoencode` - обе полностью
    покрываются теперь унифицированными `decode` и `encode`.
  - Убран необязательный резервный вариант чтения таблицы
    инициализации хаффмана из IMGGRAB.BIN (он всё равно уже не
    использовался внутри - таблица уже давно является встроенной
    константой).
  - Существенные улучшения точности декодирования во всех
    файлах - большие участки MIDGARD.DBI, CAPITAL.DBI, Interf.dbi,
    ScenEdit.dbi, ISO.DBI и BATTLE.DBI, которые раньше декодировались
    с видимыми искажениями (неверные цвета, шум в виде помех, или
    пропущенные строки), теперь точны до байта.
  - Исправлена обработка прозрачности для участков изображения, где в
    одной и той же картинке одновременно есть "настоящий" тёмный
    рисунок и подлинно пустой фон (например, силуэт здания на фоне
    открытого неба, или тёмная черепица крыши) - теперь оба
    случая корректно отображаются в одной картинке, вместо того
    чтобы всё изображение принудительно обрабатывалось одним способом.
  - Добавлен переключатель `--lang=ru` / `--lang=pl` (по умолчанию:
    английский) - теперь любое сообщение программы (этот текст, вывод
    команд, ошибки) может отображаться на русском или польском.
  - Уточнена вышеупомянутая прозрачность для отдельных групп изображений,
    где "замкнутая" тёмная область - это настоящее пустое пространство,
    а не реальное содержимое (открытая петля символа-печати, слот для
    вставки контента в шаблоне интерфейса, объекты TERRAIN.DBI) -
    подтверждено человеком прямо в игре.
  - Исправлена обратная проблема на настоящих портретах лиц (особенно
    в UNIT.DBI): случайный тёмный пиксель у самого края холста мог
    "вытянуть" прозрачность через тонкую связанную дорожку в гораздо
    большую, реально нарисованную тёмную область (волосы, тёмная
    одежда). У портретов никогда не бывает настоящего фонового поля,
    поэтому теперь они всегда отображаются полностью непрозрачными.
  - Такое же исправление для фоновых "сцен местности" TWD/TWE/TWH/TWU
    в MIDGARD.DBI (например, TWU0004) - их ночное небо отображалось
    полностью прозрачным вместо плотного тёмного фона со звёздами,
    поскольку это полноценные самостоятельные фоновые изображения, у
    которых тоже никогда не бывает прозрачного поля.
  - В список "пустое пространство, а не реальное содержимое" из
    предыдущих версий добавлены предметные иконки THIEF (MIDGARD.DBI),
    значки ICNSY (ICONS.DBI) и эмблемы LOGOD/E/H/U (по расе) - тот же
    кружевной/вырезанный узор (например, кольцо ICNSY000 считалось
    сплошным диском, а на самом деле это кольцо с прозрачным центром).
--------------------------------------------------------------------------
--------------------------------------------------------------------------

Использование:
  # Показать этот полный справочник команд (также
  # показывается автоматически при нераспознанной/отсутствующей
  # команде):
  python fd_portrait_codec_standalone.py info

  # Экспортировать КАЖДЫЙ распознанный блок в файле .DBI в PNG
  # (автоматически определяет портретную или ISO-графику для
  # каждого блока - работает с любым файлом .DBI):
  python fd_portrait_codec_standalone.py decode UNIT.DBI output_dir/
  python fd_portrait_codec_standalone.py decode MIDGARD.DBI output_dir/

  # Декодировать ВСЕ файлы .DBI в папке за один раз,
  # каждый в свою собственную выходную папку, названную по имени
  # файла (например, ISO.DBI -> ./ISO/) - удобно во время
  # активной разработки кодека, чтобы переэкспортировать всё
  # за один шаг после изменения, вместо вызова `decode` отдельно
  # для каждого файла:
  python fd_portrait_codec_standalone.py decodeall
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/ path/to/output/

  # Вставить НОВЫЙ портрет в UNIT.DBI (по умолчанию,
  # рекомендуется для моддинга - ничего не перезаписывает,
  # автоматическая генерация имени GP###):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI
  # Вынужденный префикс+индекс (например, для
  # тестирования в "родном" стиле):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI FN150

  # Вставить НОВУЮ ISO-графику в любой ДРУГОЙ файл
  # .DBI - требуется ИМЯ (объекты ISO-типа используют
  # содержательные префиксы - например, GUN, GSY, GLM, GIT,
  # GRF - а не автоматически сгенерированный номер):
  python fd_portrait_codec_standalone.py encode my_image.png ISO.DBI NAME [ow]

  # Заменить СУЩЕСТВУЮЩИЙ слот портрета (старое
  # поведение `encode` - перезаписывает заданный, известный
  # по имени слот, без ограничения размера):
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00

  # флаг `ow` (указывается в КОНЦЕ команды, одинаково для
  # encode/replace): перезаписывает исходный файл .DBI (сначала
  # автоматически сохраняя резервную копию .dbi.bak), избегая
  # цепочки UNIT_mod.DBI / UNIT_mod_mod.DBI при нескольких
  # последовательных вставках/заменах:
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI ow
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00 ow

  # Вывести список всех распознанных блоков в файле
  # .DBI, автоматически классифицированных как
  # portrait/iso/iso_partial (работает одинаково с любым файлом
  # .DBI):
  python fd_portrait_codec_standalone.py list UNIT.DBI
  python fd_portrait_codec_standalone.py list MIDGARD.DBI

  # `decode` также принимает необязательный фильтр по
  # префиксу имени:
  python fd_portrait_codec_standalone.py decode ISO.DBI output_dir/ GUN

  # ЭКСПЕРИМЕНТАЛЬНО: заменить данные
  # изображения СУЩЕСТВУЮЩЕГО ISO-блока (сохраняя
  # его имя и bt; размер нового изображения не обязан
  # совпадать с оригиналом) - `replace` (выше) уже делает
  # это автоматически для любого не-портретного блока; вызывайте
  # эту команду напрямую только для явного вызова ISO-кодировщика:
  python fd_portrait_codec_standalone.py isoreplace my_image.png ISO.DBI GUNN1307 [ow]
""",
    'pl': """
Disciples: Sacred Lands - dekoder i koder portret\u00f3w FD (samodzielny, bez numpy)
WERSJA 2.36

Wymagania: pip install pillow

--------------------------------------------------------------------------
ZMIANY OD WERSJI v2.10 (ostatniej opublikowanej wersji):
  - `decode`/`list`/`replace` dzia\u0142aj\u0105 teraz JEDNOLICIE z ka\u017cdym
    plikiem .DBI (UNIT, MIDGARD, CAPITAL, BATTLE, ISO, TERRAIN, PALMAP,
    ScenEdit, Interf, Menus) - format ka\u017cdego bloku (typu
    portretowego lub ISO) jest wykrywany automatycznie, dzi\u0119ki czemu
    jedna komenda obs\u0142uguje ka\u017cdy plik i ka\u017cdy rodzaj bloku.
    (Wcze\u015bniej potrzebne by\u0142y odr\u0119bne komendy decode/isodecode, a
    blokom portretowym i ISO potrzebne by\u0142y r\u00f3\u017cne komendy replace.)
  - `encode`/`insert` (wstawianie zupe\u0142nie nowego obrazu pod now\u0105
    nazw\u0105) zosta\u0142o teraz r\u00f3wnie\u017c zunifikowane: dla UNIT.DBI wci\u0105\u017c
    u\u017cywany jest w\u0142asny, bardziej kompaktowy, dedykowany koder z
    automatycznym generowaniem nazwy (np. `GP001`); dla ka\u017cdego
    innego pliku wymagana jest podana nazwa, u\u017cywany jest og\u00f3lny
    koder w stylu ISO. (Wcze\u015bniej by\u0142a to odr\u0119bna komenda
    `isoencode`.)
  - Dodano komend\u0119 `decodeall` - dekoduje wszystkie pliki .DBI
    znalezione w folderze za jednym razem, ka\u017cdy do w\u0142asnego folderu
    wynikowego.
  - Dodano flag\u0119 `ow` (umieszczan\u0105 na KO\u0143CU komendy encode/replace)
    do nadpisania oryginalnego pliku w miejscu, z automatyczn\u0105 kopi\u0105
    zapasow\u0105, zamiast zawsze tworzenia nowej kopii `_mod`.
  - Dodano komend\u0119 `info` (obok `-h`/`--help`/braku argument\u00f3w) do
    wy\u015bwietlania tego opisu komend.
  - Usuni\u0119to komendy `isodecode` i `isoencode` - obie s\u0105 w pe\u0142ni
    obs\u0142ugiwane przez ujednolicone teraz `decode` i `encode`.
  - Usuni\u0119to opcjonalny mechanizm zapasowy odczytu tabeli
    inicjalizacji Huffmana z IMGGRAB.BIN (i tak nie by\u0142 ju\u017c u\u017cywany
    wewn\u0119trznie - tabela jest sta\u0142\u0105 wbudowan\u0105 w kod od d\u0142u\u017cszego
    czasu).
  - Du\u017ce usprawnienia dok\u0142adno\u015bci dekodowania we wszystkich plikach -
    du\u017ce fragmenty MIDGARD.DBI, CAPITAL.DBI, Interf.dbi, ScenEdit.dbi,
    ISO.DBI i BATTLE.DBI, kt\u00f3re wcze\u015bniej dekodowa\u0142y si\u0119 z
    widocznymi zniekszta\u0142ceniami (b\u0142\u0119dne kolory, szum przypominaj\u0105cy
    zak\u0142\u00f3cenia lub brakuj\u0105ce wiersze), s\u0105 teraz dok\u0142adne co do
    piksela.
  - Naprawiono obs\u0142ug\u0119 przezroczysto\u015bci dla obszar\u00f3w obrazu, w
    kt\u00f3rych w tym samym obrazku wyst\u0119puje jednocze\u015bnie "prawdziwa"
    ciemna tre\u015b\u0107 i autentycznie puste t\u0142o (np. sylwetka budynku na
    tle otwartego nieba, albo ciemne dach\u00f3wki) - oba przypadki s\u0105
    teraz poprawnie renderowane w tym samym obrazie, zamiast
    wymuszania jednego sposobu dla ca\u0142ego obrazu.
  - Dodano prze\u0142\u0105cznik `--lang=ru` / `--lang=pl` (domy\u015blnie: angielski)
    - ka\u017cdy komunikat wy\u015bwietlany przez program (ten tekst, wyniki
    komend, b\u0142\u0119dy) mo\u017ce teraz by\u0107 wy\u015bwietlany po rosyjsku lub po
    polsku.
  - Dopracowano powy\u017csz\u0105 przezroczysto\u015b\u0107 dla konkretnych grup obraz\u00f3w,
    gdzie "zamkni\u0119ty" ciemny obszar to prawdziwa pusta przestrze\u0144, a nie
    rzeczywista tre\u015b\u0107 (otwarta p\u0119tla ikony-pieczęci, slot na tre\u015b\u0107 w
    szablonie interfejsu, obiekty TERRAIN.DBI) - potwierdzone przez
    osob\u0119 bezpo\u015brednio w grze.
  - Naprawiono odwrotny problem na prawdziwych portretach twarzy
    (zw\u0142aszcza w UNIT.DBI): przypadkowy ciemny piksel dotykaj\u0105cy
    kraw\u0119dzi p\u0142\u00f3tna m\u00f3g\u0142 "wyci\u0105gn\u0105\u0107" przezroczysto\u015b\u0107 przez w\u0105sk\u0105
    po\u0142\u0105czon\u0105 \u015bcie\u017ck\u0119 do znacznie wi\u0119kszego, faktycznie narysowanego
    ciemnego obszaru (w\u0142osy, ciemne ubranie). Portrety nigdy nie maj\u0105
    prawdziwego marginesu t\u0142a, wi\u0119c teraz s\u0105 zawsze renderowane jako
    ca\u0142kowicie nieprzezroczyste.
  - Tak\u0105 sam\u0105 poprawk\u0119 zastosowano do t\u0142a "scen terenu" TWD/TWE/TWH/TWU
    w MIDGARD.DBI (np. TWU0004) - ich nocne niebo by\u0142o renderowane jako
    ca\u0142kowicie przezroczyste, zamiast jako pe\u0142ne, ciemne t\u0142o z
    gwiazdami, poniewa\u017c to kompletne, samodzielne obrazy t\u0142a, kt\u00f3re
    r\u00f3wnie\u017c nigdy nie maj\u0105 przezroczystego marginesu.
  - Do listy "puste miejsce, a nie rzeczywista tre\u015b\u0107" z poprzednich
    wersji dodano ikony przedmiot\u00f3w THIEF (MIDGARD.DBI), znaczki ICNSY
    (ICONS.DBI) oraz emblematy LOGOD/E/H/U (wed\u0142ug rasy) - ten sam
    koronkowy/wyci\u0119ty wz\u00f3r (np. pier\u015bcie\u0144 ICNSY000 zak\u0142adano jako pe\u0142ny
    dysk, a w rzeczywisto\u015bci to pier\u015bcie\u0144 z przezroczystym \u015brodkiem).
--------------------------------------------------------------------------
--------------------------------------------------------------------------
--------------------------------------------------------------------------

U\u017cycie:
  # Poka\u017c ten pe\u0142ny opis komend (wy\u015bwietlany te\u017c automatycznie przy
  # nierozpoznanej/brakuj\u0105cej komendzie):
  python fd_portrait_codec_standalone.py info

  # Eksportuj KA\u017bDY rozpoznany blok w pliku .DBI do PNG (automatycznie
  # wykrywa grafik\u0119 portretow\u0105 lub w stylu ISO dla ka\u017cdego bloku -
  # dzia\u0142a z ka\u017cdym plikiem .DBI):
  python fd_portrait_codec_standalone.py decode UNIT.DBI output_dir/
  python fd_portrait_codec_standalone.py decode MIDGARD.DBI output_dir/

  # Zdekoduj WSZYSTKIE pliki .DBI w folderze za jednym razem, ka\u017cdy
  # do w\u0142asnego folderu wynikowego nazwanego jak plik (np. ISO.DBI ->
  # ./ISO/) - przydatne podczas aktywnego rozwoju kodeka, aby ponownie
  # wyeksportowa\u0107 wszystko jednym krokiem po zmianie, zamiast
  # wywo\u0142ywa\u0107 `decode` dla ka\u017cdego pliku osobno:
  python fd_portrait_codec_standalone.py decodeall
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/
  python fd_portrait_codec_standalone.py decodeall path/to/dbi_folder/ path/to/output/

  # Wstaw NOWY portret do UNIT.DBI (domy\u015blnie, rekomendowane do
  # moddingu - nic nie nadpisuje, automatyczne generowanie nazwy
  # GP###):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI
  # Wymuszony prefiks+indeks (np. do test\u00f3w w stylu natywnym):
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI FN150

  # Wstaw NOW\u0104 grafik\u0119 w stylu ISO do KA\u017bDEGO INNEGO pliku .DBI -
  # wymagana jest NAZWA (obiekty typu ISO u\u017cywaj\u0105 znacz\u0105cych
  # prefiks\u00f3w - np. GUN, GSY, GLM, GIT, GRF - a nie automatycznie
  # generowanego numeru):
  python fd_portrait_codec_standalone.py encode my_image.png ISO.DBI NAME [ow]

  # Zast\u0105p ISTNIEJ\u0104CY slot portretu (stare zachowanie `encode` -
  # nadpisuje podany, nazwany slot, bez limitu rozmiaru):
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00

  # Flaga `ow` (umieszczana na KO\u0143CU komendy, tak samo dla
  # encode/replace): nadpisuje oryginalny plik .DBI (najpierw
  # automatycznie zapisuj\u0105c kopi\u0119 zapasow\u0105 .dbi.bak), unikaj\u0105c
  # \u0142a\u0144cuchowania UNIT_mod.DBI / UNIT_mod_mod.DBI przy kilku
  # kolejnych wstawieniach/zamianach:
  python fd_portrait_codec_standalone.py encode my_image.png UNIT.DBI ow
  python fd_portrait_codec_standalone.py replace my_image.png UNIT.DBI FD026S00 ow

  # Wy\u015bwietl list\u0119 wszystkich rozpoznanych blok\u00f3w w pliku .DBI,
  # automatycznie sklasyfikowanych jako portrait/iso/iso_partial
  # (dzia\u0142a tak samo z ka\u017cdym plikiem .DBI):
  python fd_portrait_codec_standalone.py list UNIT.DBI
  python fd_portrait_codec_standalone.py list MIDGARD.DBI

  # `decode` przyjmuje te\u017c opcjonalny filtr po prefiksie nazwy:
  python fd_portrait_codec_standalone.py decode ISO.DBI output_dir/ GUN

  # EKSPERYMENTALNE: zast\u0105p dane obrazu ISTNIEJ\u0104CEGO bloku grafiki w
  # stylu ISO (zachowuj\u0105c jego nazw\u0119 i bt; rozmiar nowego obrazu nie
  # musi odpowiada\u0107 oryginalnemu) - `replace` (powy\u017cej) robi to ju\u017c
  # automatycznie dla ka\u017cdego bloku nie-portretowego; wywo\u0142uj t\u0119
  # komend\u0119 bezpo\u015brednio tylko, aby jawnie wymusi\u0107 u\u017cycie kodera
  # ISO:
  python fd_portrait_codec_standalone.py isoreplace my_image.png ISO.DBI GUNN1307 [ow]
""",
}


def print_help():
    """Print the info/help text in the current LANG (falls back to the
    module's own English __doc__ for 'en' or any unknown language)."""
    print(HELP_TEXT.get(LANG, __doc__))


# --- Huffman tables (identical for every DBI image) ---------------------

DIST_TABLE = [(0,0),(0,1),(1,2),(2,4),(3,8),(4,16),(5,32),(6,64)]
LEN_TABLE  = [(1,8),(2,10),(3,14),(4,22),(5,38),(6,70),(7,134),(8,262)]

def load_init_codes():
    """Load the Huffman init codes.

    This is a COMPLETELY STATIC, 274-entry (length,value) table - the
    Disciples engine always uses the same one as the starting state of
    the adaptive Huffman decoder, regardless of which .DBI file is being
    read. Originally extracted from IMGGRAB.BIN (a helper tool bundled
    with the installer, for an unrelated purpose) at the fixed offset
    0x118A18 - since the table is a stateless constant, there's no need
    to re-read it at runtime from that file; it was extracted once and
    is kept here, in the code, as `_INIT_CODES_RAW` below.
    """
    return {pos: (l, v) for pos, (l, v) in enumerate(_INIT_CODES_RAW) if 1 <= l <= 16}


# The static table of Huffman init codes (274 entries, (length,value) pairs,
# position = symbol index). See the load_init_codes() docstring.
_INIT_CODES_RAW = (
    (7,20), (8,48), (8,49), (8,50), (8,51), (8,52), (8,53), (8,54), (8,55), (8,56),
    (8,57), (8,58), (8,59), (8,60), (8,61), (8,62), (8,63), (8,64), (8,65), (8,66),
    (8,67), (8,68), (8,69), (8,70), (8,71), (8,72), (8,73), (8,74), (8,75), (8,76),
    (8,77), (8,78), (7,21), (8,79), (8,80), (8,81), (8,82), (8,83), (8,84), (8,85),
    (8,86), (8,87), (8,88), (8,89), (8,90), (8,91), (8,92), (8,93), (7,22), (8,94),
    (8,95), (8,96), (8,97), (8,98), (8,99), (8,100), (8,101), (8,102), (8,103), (8,104),
    (8,105), (8,106), (8,107), (8,108), (8,109), (8,110), (8,111), (8,112), (8,113), (8,114),
    (8,115), (8,116), (8,117), (8,118), (8,119), (8,120), (8,121), (8,122), (8,123), (8,124),
    (8,125), (8,126), (8,127), (8,128), (8,129), (8,130), (8,131), (8,132), (8,133), (8,134),
    (8,135), (8,136), (8,137), (8,138), (8,139), (8,140), (8,141), (8,142), (8,143), (8,144),
    (8,145), (8,146), (8,147), (8,148), (8,149), (8,150), (8,151), (8,152), (8,153), (8,154),
    (8,155), (8,156), (8,157), (8,158), (8,159), (8,160), (8,161), (8,162), (8,163), (8,164),
    (8,165), (8,166), (8,167), (8,168), (8,169), (8,170), (8,171), (8,172), (8,173), (8,174),
    (8,175), (8,176), (8,177), (8,178), (8,179), (8,180), (8,181), (8,182), (8,183), (8,184),
    (8,185), (8,186), (8,187), (8,188), (8,189), (8,190), (8,191), (8,192), (8,193), (8,194),
    (8,195), (8,196), (8,197), (8,198), (8,199), (8,200), (8,201), (8,202), (8,203), (8,204),
    (8,205), (8,206), (8,207), (9,416), (9,417), (9,418), (9,419), (9,420), (9,421), (9,422),
    (9,423), (9,424), (9,425), (9,426), (9,427), (9,428), (9,429), (9,430), (9,431), (9,432),
    (9,433), (9,434), (9,435), (9,436), (9,437), (9,438), (9,439), (9,440), (9,441), (9,442),
    (9,443), (9,444), (9,445), (9,446), (9,447), (9,448), (9,449), (9,450), (9,451), (9,452),
    (9,453), (9,454), (9,455), (9,456), (9,457), (9,458), (9,459), (9,460), (9,461), (9,462),
    (9,463), (9,464), (9,465), (9,466), (9,467), (9,468), (9,469), (9,470), (9,471), (9,472),
    (9,473), (9,474), (9,475), (9,476), (9,477), (9,478), (9,479), (9,480), (9,481), (9,482),
    (9,483), (9,484), (9,485), (9,486), (9,487), (9,488), (9,489), (9,490), (9,491), (9,492),
    (9,493), (9,494), (9,495), (9,496), (9,497), (9,498), (9,499), (9,500), (9,501), (9,502),
    (9,503), (9,504), (9,505), (9,506), (9,507), (7,23), (6,0), (6,1), (6,2), (6,3),
    (7,8), (7,9), (7,10), (7,11), (7,12), (7,13), (7,14), (7,15), (7,16), (7,17),
    (7,18), (7,19), (9,508), (9,509),
)

# --- Bit I/O --------------------------------------------------------------

class BitReader:
    def __init__(self,data): self.data=data; self.pos=0
    def read_bit(self):
        b=self.pos>>3; bit=7-(self.pos&7)
        if b>=len(self.data): raise EOFError()
        v=(self.data[b]>>bit)&1; self.pos+=1; return v
    def read_bits(self,n):
        v=0
        for _ in range(n): v=(v<<1)|self.read_bit()
        return v

class BitWriter:
    def __init__(self): self.bits=[]
    def write_bits(self,v,n):
        for i in range(n-1,-1,-1): self.bits.append((v>>i)&1)
    def to_bytes(self):
        while len(self.bits)%8: self.bits.append(0)
        out=bytearray()
        for i in range(0,len(self.bits),8):
            b=0
            for bit in self.bits[i:i+8]: b=(b<<1)|bit
            out.append(b)
        return bytes(out)

# --- Decompressor -----------------------------------------------------------

def decompress(stream, init_codes, hp_target):
    """LZ77+Huffman decompression of hp_target bytes.

    For L00 (115x67) portraits, the compressor sends a Huffman table
    "rebuild" event (symbol=272) every 4096 decoded symbols. This is the
    algorithm as discovered by reverse-engineering the executable
    (Disciple.exe):
      1. Every element of the 274-entry freq[] array is halved (signed
         right shift, "sar"), and the symbols are sorted into ascending
         order with a Shell sort based on the OLD (pre-halving) values.
      2. A 16-level table is read from the bitstream: at each level, a
         unary-coded value ("esi", number of extra bits) is read (as
         many 0-bits as it signals, terminated by a 1-bit), which is
         cumulative (each level adds its own unary value to the previous
         one). The "base index" (where this level starts in the symbol
         table) comes from the sum of 2**esi over the previous levels.
      3. With the new code table: 4 bits determine the "level" (edi),
         then if the esi for that level is >0, esi more extra bits are
         read, and the result (base_idx[edi]+extra) indexes into the
         symbol table sorted by DESCENDING frequency (the most frequent
         symbol is at index=0).
    """
    # Lookup: code string -> symbol
    lookup={}; max_len=0
    for sym,(l,v) in init_codes.items():
        code=format(v,f'0{l}b')
        lookup[code]=sym
        if l>max_len: max_len=l

    br=BitReader(stream)
    hist=bytearray(max(65536, hp_target+1000))
    hp=0
    freq=[0]*274

    use_new_table=False
    esi_table=None; base_idx_table=None; sym_table=None

    def decode_sym():
        if not use_new_table:
            code=''
            for _ in range(max_len):
                code+=str(br.read_bit())
                if code in lookup: return lookup[code]
            raise ValueError(f"Unknown code: {code!r}")
        else:
            edi=br.read_bits(4)
            esi=esi_table[edi]
            if esi==0:
                idx=base_idx_table[edi]
            else:
                extra=br.read_bits(esi)
                idx=base_idx_table[edi]+extra
            if idx>=len(sym_table):
                raise ValueError("rebuild index too large")
            return sym_table[idx]

    def read_dist():
        pref=br.read_bits(3); eb,base=DIST_TABLE[pref]
        return (base<<9)|br.read_bits(9+eb)

    def do_rebuild():
        nonlocal use_new_table, esi_table, base_idx_table, sym_table
        pairs=[]
        for i in range(274):
            old=freq[i]
            old_signed = old-65536 if old>=32768 else old
            pairs.append((old, i))
            freq[i] = (old_signed >> 1) & 0xFFFF
        pairs.sort(key=lambda p: p[0])
        sorted_syms=[p[1] for p in pairs]
        sym_table=list(reversed(sorted_syms))
        et=[]; bit=[]; ebp=0; esp10=0
        for _level in range(16):
            cnt=0
            while True:
                b=br.read_bit()
                if b==0: cnt+=1
                else: break
            ebp+=cnt
            et.append(ebp); bit.append(esp10)
            esp10+=(1<<ebp)
        esi_table=et; base_idx_table=bit
        use_new_table=True

    while hp<hp_target:
        try: s=decode_sym()
        except: break

        freq[s]=min(freq[s]+1,0xFFFF)

        if s==272:
            try: do_rebuild()
            except Exception: break
            continue

        # DISCOVERY (2026-06-25): for multi-chunk blocks (byte39==0x01/
        # 0x02) the true content length isn't reliably knowable ahead of
        # time - the caller may pass a generous/oversized target so that
        # the existing chunk-boundary (symbol 273) logic can run all the
        # way through. When that happens, the LAST symbol's backreference
        # data legitimately runs out of real compressed bits (EOFError
        # from BitReader) - previously this escaped uncaught (read_dist()
        # and the history-copy loops were outside the try/except), losing
        # the whole result instead of just stopping gracefully at the
        # true end of content. Snapshot hp and roll back on any failure
        # here, same as the plain decode_sym() case above.
        hp_before = hp
        try:
            if s<256:
                hist[hp]=s; hp+=1
            elif s<264:
                d=read_dist(); l=(s-256)+4; st=hp-d
                for _ in range(l): hist[hp]=hist[st]; hp+=1; st+=1
            elif s<272:
                k=s-264; eb2,base2=LEN_TABLE[k]
                ex=br.read_bits(eb2); l=base2+ex+4
                d=read_dist(); st=hp-d
                for _ in range(l): hist[hp]=hist[st]; hp+=1; st+=1
            elif s==273:
                if hp < hp_target:
                    use_new_table = False
                    freq = [0]*274
                    continue
                break
        except Exception:
            hp = hp_before
            break

    return hist, hp



# --- Compressor ---------------------------------------------------------------

def compress(data, init_codes):
    """LZ77+Huffman compression (static Huffman, S portrait).

    Optimized: at every position, looks for the best (longest/cheapest)
    match using the hash table, with 256 lookback positions."""
    enc={sym:(l,v) for sym,(l,v) in init_codes.items()}

    bw=BitWriter()
    n=len(data)

    max_eb,max_base=DIST_TABLE[-1]
    MAX_D=(max_base<<9)+((1<<(9+max_eb))-1)

    # Symbol bit length for fast lookup
    sym_bits={sym:l for sym,(l,v) in init_codes.items()}

    def sym(s):
        l,v=enc[s]; bw.write_bits(v,l)

    def dist_bits(d):
        """How many bits are needed to encode the distance."""
        dh=d>>9; bp,be,bb=0,0,0
        for pf,(eb,base) in enumerate(DIST_TABLE):
            if base<=dh: bp,be,bb=pf,eb,base
        return 3+(9+be)

    def put_dist(d):
        dh=d>>9; bp,be,bb=0,0,0
        for pf,(eb,base) in enumerate(DIST_TABLE):
            if base<=dh: bp,be,bb=pf,eb,base
        bw.write_bits(bp,3); bw.write_bits(d-(bb<<9),9+be)

    def backref_bits(l,d):
        """How many bits are needed for an (l,d) back-reference."""
        db=dist_bits(d)
        if 4<=l<=11:
            return sym_bits[256+(l-4)]+db
        for k,(eb,base) in enumerate(LEN_TABLE):
            if base+4<=l<=base+(1<<eb)-1+4:
                return sym_bits[264+k]+eb+db
        return 999999

    def put_backref(l,d):
        if 4<=l<=11:
            s2=256+(l-4)
            sym(s2); put_dist(d); return True
        for k,(eb,base) in enumerate(LEN_TABLE):
            if base+4<=l<=base+(1<<eb)-1+4:
                sym(264+k); bw.write_bits(l-base-4,eb); put_dist(d); return True
        return False

    from collections import defaultdict
    ht=defaultdict(list)
    pos=0
    while pos<n:
        # Update hash table for the current position
        if pos+2<n:
            key=(data[pos],data[pos+1],data[pos+2])
            ht[key].append(pos)

        bl=0; bd=0; best_bits=sym_bits.get(data[pos],8)+1  # literal cost

        if pos+3<=n:
            key=(data[pos],data[pos+1],data[pos+2])
            candidates=ht.get(key,[])
            # Check the last 256 candidates (better compression)
            for c in reversed(candidates[-256:]):
                d=pos-c
                if d<=0 or d>MAX_D: continue
                ml=min(266,n-pos); l=0
                while l<ml and data[c+l]==data[pos+l]: l+=1
                if l>=4:
                    cost=backref_bits(l,d)
                    # Is this better than the literal cost?
                    lit_cost=sum(sym_bits.get(data[pos+i],8) for i in range(l))
                    if cost<lit_cost and l>bl:
                        bl=l; bd=d; best_bits=cost

        if bl>=4 and put_backref(bl,bd):
            # Update hash table for the skipped-over positions
            for j in range(1,bl):
                if pos+j+2<n:
                    ht[(data[pos+j],data[pos+j+1],data[pos+j+2])].append(pos+j)
            pos+=bl
        else:
            sym(data[pos]); pos+=1

    sym(273)  # END
    return bw.to_bytes()

# --- DBI structure ----------------------------------------------------------

def _search_marker(hist, W, hp, lo, hi, target_ctr, closest_to=None):
    """Search for a [K,p1,p2,p3] marker in the range [lo,hi), requiring
    p1==target_ctr and (if K<W) offset-formula validity. If closest_to is
    given, returns the match closest to it (for finding the FIRST marker);
    otherwise the FIRST match (for finding FURTHER patches of a given row,
    where order matters).

    FALSE-MARKER-COLLISION FIX (v2.21): when `closest_to` is given (i.e.
    we're picking the FIRST marker of a row), a candidate can be a
    coincidental false positive - ordinary pixel data that happens to
    satisfy the marker syntax (K<=W, p1==target_ctr, valid offset) purely
    by chance. Found on MIDGARD.DBI's FE000L03 row64: a false candidate
    sat just 2 bytes before the TRUE marker and was picked because it was
    closer to `closest_to`, swallowing the real marker's bytes into its
    own (bogus) K-byte data span and breaking the multi-patch
    continuation search downstream (see PROJECT_HANDOFF31).

    Detection: a candidate is "suspect" if ANOTHER valid marker for the
    SAME target_ctr is found embedded inside its own claimed [K]-byte
    data window - genuine row data is never expected to coincidentally
    contain a second fully-valid marker for the same row right where the
    first one claims its pixel payload lives. When this happens, the
    embedded one is almost certainly the real marker. Candidates that
    pass this check are preferred; if ALL candidates are "suspect" (so
    this heuristic can't discriminate), we fall back to the original
    closest-distance behavior to avoid regressing any previously-
    validated decode.
    """
    candidates = []
    for cand in range(lo, hi):
        if cand + 3 >= hp:
            break
        K = hist[cand]
        p1 = hist[cand+1]
        if K <= W and p1 == target_ctr:
            if K < W:
                p2c = hist[cand+2]; p3c = hist[cand+3]
                off_c = p3c*8 + (p2c // 32)
                if not (0 <= off_c <= W-K):
                    continue
            candidates.append(cand)
            if closest_to is None:
                return cand
    if not candidates:
        return None
    if closest_to is None:
        return None

    def _is_suspect(cand):
        K = hist[cand]
        if K >= W:
            # A FULL-row marker's payload is the entire row (up to ~115
            # bytes) - across that much arbitrary pixel data, finding
            # SOME coincidentally marker-shaped 4-byte run is likely by
            # chance alone, not a meaningful signal. Found on CFDW0039
            # row74: a genuine, correctly-positioned full-row marker was
            # wrongly demoted because of an unrelated coincidental match
            # deep inside its own pixel payload. Full-row candidates are
            # unambiguous (K==p1 already pins them to the right row) and
            # are never treated as suspect.
            return False
        end = min(cand + 4 + K, hp)
        for i in range(cand + 4, end - 3):
            Ki = hist[i]; p1i = hist[i+1]
            if 1 <= Ki <= W and p1i == target_ctr:
                if Ki < W:
                    p2i = hist[i+2]; p3i = hist[i+3]
                    off_i = p3i*8 + (p2i // 32)
                    if not (0 <= off_i <= W - Ki):
                        continue
                return True
        return False

    clean = [c for c in candidates if not _is_suspect(c)]
    pool = clean if clean else candidates
    return min(pool, key=lambda c: abs(c - closest_to))


def _rebuild_rows_v2(hist, W, H, hp):
    """
    NEW, validated row reconstruction (2026-06-18, session 5, updated with
    the "multiple patches per row" breakthrough):
    Each row is preceded by a 4-byte [K, p1, p2, p3] marker (sometimes with
    a 235 prefix, sometimes without), where p1=(4*row_index) mod 256. If
    K==W, the K bytes following the marker are the FULL row. If K<W, the
    K bytes following the marker are a PART of the row, whose starting
    column is: offset = p3*8 + p2//32.

    CRITICAL DISCOVERY: a row may have MULTIPLE such [K,p1,p2,p3] patches,
    with the SAME p1 value, one after another (validated: FN127S00 row37,
    two patches: [0,17) and [36,55), both matching ground truth byte for
    byte).

    Columns NOT covered by any marker are inherited from the SAME columns
    of the PREVIOUS (already reconstructed) row (an approximation for the
    remaining cases).
    """
    rows, _counts = _rebuild_rows_v2_with_counts(hist, W, H, hp)
    return rows


def _rebuild_rows_v2_with_counts(hist, W, H, hp):
    """Like _rebuild_rows_v2, but also returns the number of patches found
    for each row (0 = no marker/black row, 1 = one patch or full row,
    2+ = multiple patches - in these cases the reconstruction is based on
    byte-exact, validated explicit data, NOT an approximation)."""
    rows, _patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
    counts = [len(p) for p in _patches]
    return rows, counts


def _rebuild_rows_v2_with_patches(hist, W, H, hp):
    """Like _rebuild_rows_v2, but also returns the list of explicit patches
    found for each row, as (offset,K,explicit_bytes) tuples (for a FULL
    row, a single (0,W,explicit_bytes) element). This allows patches to be
    overlaid PRECISELY, at column granularity, onto another row
    reconstruction (e.g. the old heuristic), even if only ONE patch is
    found - since every patch found is byte-exact, validated explicit
    data, never an approximation."""
    rows = []
    all_patches = []
    pos = 0
    for r in range(H):
        target_ctr = (4 * r) % 256
        best = _search_marker(hist, W, hp, max(0, pos-5), min(hp-5, pos+30),
                               target_ctr, closest_to=pos)
        if best is None:
            best = _search_marker(hist, W, hp, max(0, pos-5), min(hp-5, pos+600),
                                   target_ctr, closest_to=pos)
        if best is None:
            # INHERIT the previous row (v2.15) instead of defaulting to
            # black. This matches the documented "skip redraw" semantics
            # found elsewhere in this format (a row with no marker at all
            # signals the renderer should reuse the previous row/frame,
            # not paint nothing) - confirmed by oracle comparison on
            # CFUN0083 row65 (was rendering solid black; oracle has the
            # same skin-tone content as row64 there).
            rows.append(rows[r-1][:] if r > 0 else [0]*W)
            all_patches.append([])
            pos += W
            continue

        base = rows[r-1][:] if r > 0 else [0]*W
        row = base[:]
        cur = best
        cur_end = pos
        row_patches = []
        while cur is not None:
            K = hist[cur]
            if K >= W:
                explicit = list(hist[cur+4:cur+4+K])[:W]
                if len(explicit) < W:
                    explicit = explicit + [0]*(W-len(explicit))
                row = explicit
                row_patches.append((0, W, explicit))
                cur_end = cur + 4 + K
                cur = None
                break
            else:
                p2 = hist[cur+2]; p3 = hist[cur+3]
                offset = p3*8 + (p2 // 32)
                offset = max(0, min(offset, W-K))
                explicit = list(hist[cur+4:cur+4+K])
                row[offset:offset+K] = explicit
                row_patches.append((offset, K, explicit))
                cur_end = cur + 4 + K
                cur = _search_marker(hist, W, hp, cur_end, min(hp-5, cur_end+10),
                                      target_ctr)
        rows.append(row[:W])
        all_patches.append(row_patches)
        pos = cur_end
    return rows, all_patches



def _collect_row_markers(hist, W, H, hp_end):

    """
    Collect row-boundary markers ([235, K, counter_lo, counter_hi?, ...]).
    The counter field can be 1 byte OR 2 bytes (LE) - this is needed for
    portraits with 64+ rows because of the 8-bit overflow, where the
    2-byte form can COLLIDE with the 1-byte counter of a lower row index.
    The collision is resolved by position-consistency (we pick whichever
    interpretation is closer to the row index estimated from the marker's
    position in the buffer).
    """
    candidates = []
    for i in range(4, min(hp_end, len(hist)) - 4):
        if hist[i] == 235 and hist[i+1] <= W:
            K_val = hist[i+1]
            est_r = i / (W + 5)
            c1 = hist[i+2]
            r1 = c1 // 4 - 1 if c1 > 0 and c1 % 4 == 0 else None
            c2 = hist[i+2] | (hist[i+3] << 8)
            r2 = c2 // 4 - 1 if c2 > 0 and c2 % 4 == 0 else None
            opts = []
            if r1 is not None and 0 <= r1 < H: opts.append(r1)
            if r2 is not None and 0 <= r2 < H and r2 != r1: opts.append(r2)
            if not opts: continue
            best_r = min(opts, key=lambda r: abs(r - est_r))
            candidates.append((i, K_val, best_r))

    markers_by_row = {}
    for pos, K, r in candidates:
        if r not in markers_by_row:
            markers_by_row[r] = (pos, K)
        else:
            old_pos, _old_K = markers_by_row[r]
            est_pos = r * (W + 5)
            if abs(pos - est_pos) < abs(old_pos - est_pos):
                markers_by_row[r] = (pos, K)
    return markers_by_row


def _find_short_row_pad(hist, pos, ec_full, W, hp_end):
    """
    Find the padding after a short row (returns the actual pixel count).
    Two-phase search:
      1. Strict pattern: exact match of [K2<=W, counter_lo, counter_hi, 0].
      2. Permissive pattern (only if 1. finds nothing): match of
         [K2<=W, counter_lo], ignoring counter_hi/remaining bytes.
    If the found sequence matches a Type C placeholder [A,X,B,4] pattern
    (B a multiple of 32, byte 4 is 4), it's not a real row-boundary
    marker but a placeholder that extends to the END OF THE ROW (no
    suffix) - in this case the returned end position (newpos) points to
    the position AFTER the placeholder, and the caller must treat this as
    the full data of the NEXT row (not short), shifting the marker search
    accordingly (validated with BMP: FN127S00 row35-45 chain). The
    `is_tail_placeholder` flag distinguishes this case.
    """
    ec_lo = ec_full & 0xFF
    ec_hi = (ec_full >> 8) & 0xFF

    for k_test in range(0, W + 1):
        ti = pos + k_test
        if (ti + 3 < hp_end and hist[ti] <= W and
                hist[ti+1] == ec_lo and hist[ti+2] == ec_hi and hist[ti+3] == 0):
            return k_test, hist[ti], ti + 4, False

    for k_test in range(0, W + 1):
        ti = pos + k_test
        if ti + 3 < hp_end and hist[ti] <= W and hist[ti+1] == ec_lo:
            if hist[ti+2] in (32, 64, 96, 128, 160, 192) and hist[ti+3] == 4:
                return k_test, hist[ti], ti + 4, True
            return k_test, hist[ti], ti + 4, False

    return None


# The "placeholder" byte sequence: this is how the compressor signals that
# it "skipped" a long, homogeneous/transitional image region from a short
# row's pixel data. Format: [P0, P1, P2, P3, X, P5, P6] (7 bytes), where
# X = 4 * (current row index), and [P0,P1,P2,P3] matches a known "type
# prefix" (types observed so far: (41,247,191,22) and (23,1,0,18)). The
# data before and after the sequence is real pixel data; the missing
# width in between is filled with a nearby background color (240).
_PLACEHOLDER_PREFIXES = (
    (41, 247, 191, 22),
    (23, 1, 0, 18),
)


def _decode_s00_chain_alt(hist, W, H, hp_end):
    """
    Alternative S00 row-reconstruction for portraits where the OLD
    heuristic (_collect_row_markers, which looks for a single 235
    sentinel byte) finds almost nothing. Found this session on
    ICONS.DBI's ICNAR*/ICNxx*-style item icons (shields etc.) - these
    use a DIFFERENT, previously-undocumented marker convention:

      - the row header is [K, c1, c2, c3] with c1 == 4*row_index
        EXACTLY (not shifted by 1 like the old 235-style counter).
      - the separator between rows is NOT a fixed single sentinel
        byte - it's a variable-length run (1-3 bytes, usually value
        250, sometimes ending in a stray 235) - so the next marker
        must be found by a small forward SEARCH (like _search_marker
        elsewhere in this file), not a fixed-offset skip.
      - a row can have multiple segments, same convention as the v2/
        L00 per-row patch system (handled here the same way: after
        applying a segment, check a small window for another segment
        of the SAME row before moving on).
      - the image's real content doesn't necessarily start at row 0,
        and a "main pass" through the wide middle rows can be followed
        by ADDITIONAL segments scattered later in the buffer with NO
        consistent order - observed on a shield icon: the pointed top
        AND bottom tips were both encoded after the main pass, in an
        order that wasn't simply "top then bottom" or vice versa, and
        some already-visited middle rows even got a second segment for
        their other half out there too. Trying to special-case an
        "alternating tips" order was fragile and incomplete; the robust
        fix that handles ALL of these uniformly is to track exactly
        which CELLS (not rows) are already filled, and free-scan the
        remainder of the buffer for any further valid [K,c1,c2,c3]
        record, applying it only where it doesn't collide with
        already-filled cells.

    Validated against 5 oracle BMPs (ICONS.DBI's ICNAR001-005): all
    reach 0.03%-0.91% mismatched px (most under 0.1%), vs. 48-60%
    mismatched px from the old 235-based heuristic on the same images.

    Returns (rows, covered): rows is a list of H bytearrays (W bytes
    each); covered is a parallel list of bool lists marking which
    cells came from real explicit data (vs. never-found/default-zero).
    Returns None if no usable starting chain was found at all (main
    chain length < 5 rows - not worth preferring over the old
    heuristic).
    """
    buf = bytes(hist[:hp_end])

    def chain_from(startrow, startpos, grid, covered):
        row = startrow; pos = startpos; n = 0; end = startpos
        while row < H and pos + 4 <= len(buf):
            K = buf[pos]; c1 = buf[pos+1]; c2 = buf[pos+2]; c3 = buf[pos+3]
            if c1 != 4*row or K > W:
                break
            off = c3*8 + c2//32 if K < W else 0
            if not (0 <= off <= W-K):
                break
            if pos+4+K > len(buf):
                # not enough buffer left for the claimed K bytes - a
                # slice assignment with a too-short value would shrink
                # the row below W bytes (found via "not enough image
                # data" crashes on ICUSP100/ICNPO*/ICNVA* etc. - those
                # are NOT this marker convention at all, they just also
                # happen to have few/zero old-style markers, so this
                # function gets tried on them and must fail safely).
                break
            explicit = buf[pos+4:pos+4+K]
            grid[row][off:off+K] = list(explicit)
            for c in range(off, off+K):
                covered[row][c] = True
            end = pos+4+K
            n += 1
            same_row_next = None
            for d in range(0, 15):
                p = end+d
                if p+4 > len(buf): break
                if buf[p+1] == 4*row and buf[p] <= W:
                    c2b = buf[p+2]; c3b = buf[p+3]; Kb = buf[p]
                    offb = c3b*8+c2b//32 if Kb < W else 0
                    if 0 <= offb <= W-Kb and p+4+Kb <= len(buf):
                        same_row_next = p; break
            if same_row_next is not None:
                pos = same_row_next
                continue
            row += 1
            target_c1 = 4*row
            nxt = None
            for d in range(0, 15):
                p = end+d
                if p+4 > len(buf): break
                if buf[p+1] == target_c1 and buf[p] <= W:
                    nxt = p; break
            if nxt is None:
                break
            pos = nxt
        return n, row-1, end

    best = None
    for r0 in range(0, min(30, H)):
        for i in range(0, min(60, max(0, len(buf)-4))):
            K = buf[i]; c1 = buf[i+1]
            if K <= W and c1 == 4*r0:
                grid = [[0]*W for _ in range(H)]
                covered = [[False]*W for _ in range(H)]
                n, lastrow, endpos = chain_from(r0, i, grid, covered)
                if best is None or n > best[1]:
                    best = (r0, n, grid, lastrow, i, endpos, covered)
    if best is None or best[1] < 5:
        return None
    r0, n, grid, lastrow, startpos, endpos, covered = best

    # Free-scan the rest of the buffer for supplementary segments
    # (tips, second-half segments for already-visited rows, etc.) -
    # apply only where it doesn't collide with already-filled cells.
    i = endpos
    while i < len(buf)-3:
        K = buf[i]; c1 = buf[i+1]; c2 = buf[i+2]; c3 = buf[i+3]
        if K > W or c1 % 4 != 0:
            i += 1; continue
        row = c1 // 4
        if row >= H:
            i += 1; continue
        off = c3*8 + c2//32 if K < W else 0
        if not (0 <= off <= W-K) or K < 3:
            i += 1; continue
        if i+4+K > len(buf):
            i += 1; continue
        if any(covered[row][off:off+K]):
            i += 1; continue
        explicit = buf[i+4:i+4+K]
        grid[row][off:off+K] = list(explicit)
        for c in range(off, off+K):
            covered[row][c] = True
        i += 4+K

    rows = [bytes(r) for r in grid]
    return rows, covered


def _reconstruct_short_row(raw_px, row_index, W, prev_row=None):
    """
    Finalize the pixel data of an extracted short row (raw_px, length
    k_test) to width W. If one of the known placeholder sequences is
    found within it, the homogeneous-region-fill rule is applied;
    otherwise a continuity heuristic chooses between left- or
    right-alignment (see below), relative to the previous decoded row
    (prev_row).
    """
    ph_idx = None
    limit = len(raw_px) - 6
    for i in range(max(0, limit)):
        chunk = tuple(raw_px[i:i+4])
        if chunk in _PLACEHOLDER_PREFIXES:
            ph_idx = i
            break

    if ph_idx is not None and ph_idx + 7 <= len(raw_px):
        prefix = raw_px[:ph_idx]
        # There are 2 "junk" bytes at the end of the data after the
        # sequence (the start of the next marker bleeds into the
        # extracted length) - we subtract this.
        suffix = raw_px[ph_idx+7:-2] if len(raw_px) - (ph_idx+7) >= 2 else raw_px[ph_idx+7:]
        fill_count = W - len(prefix) - len(suffix)
        if fill_count >= 0:
            fill_value = 240
            result = bytes(prefix) + bytes([fill_value]) * fill_count + bytes(suffix)
            return result[:W]

    # Type C: a shorter (4-byte) placeholder form [A, X, B, 4], where
    # X = 4*row_index (exact match - this is the disambiguating anchor,
    # same as for Type A/B), A is a small variable number (~17-22), B is
    # always a multiple of 32 (observed in the range 32-192). The "trail"
    # (the number of junk bytes after the sequence that must be cut off
    # the end of the suffix) follows a 4-element cyclic pattern:
    # trail = ((B//32) - 3) % 4 (validated with BMP on 13 rows, 5
    # different portraits: B=96->trail=0, 128->1, 160->2, 192->3, 32->2,
    # 64->3 - the modulo-4 cyclicity presumably comes from B encoding the
    # low bits of some internal counter).
    target_X = 4 * row_index
    ph_idx_c = None
    for i in range(len(raw_px) - 3):
        if (raw_px[i+1] == target_X and raw_px[i+3] == 4
                and raw_px[i+2] in (32, 64, 96, 128, 160, 192)):
            ph_idx_c = i
            break

    if ph_idx_c is not None:
        A, X, B, _C = raw_px[ph_idx_c:ph_idx_c+4]
        trail = ((B // 32) - 3) % 4
        prefix = raw_px[:ph_idx_c]
        tail_start = ph_idx_c + 4
        if trail > 0 and len(raw_px) - tail_start > trail:
            suffix = raw_px[tail_start:-trail]
        else:
            suffix = raw_px[tail_start:]
        fill_count = W - len(prefix) - len(suffix)
        if fill_count >= 0:
            fill_value = 240
            result = bytes(prefix) + bytes([fill_value]) * fill_count + bytes(suffix)
            return result[:W]

    # Base case: no recognized placeholder. First we remove any trailing
    # [1, 0] "junk" 2 bytes from the end - this appears when two (or
    # more) consecutive rows are both short, and the marker between them
    # has the form [K2, 1, 0] instead of the expected [K2, ec_lo, ec_hi, 0]
    # form (the compressor adds an extra signal when continuing the chain)
    # - validated with BMP (FU080S00 row9/10/11).
    if len(raw_px) >= 2 and raw_px[-2] == 1 and raw_px[-1] == 0:
        raw_px = raw_px[:-2]

    # L00-internal (non-"235"-prefixed) short row marker case: the
    # extracted raw_px has an orphan "0" byte left at the end (the 3rd
    # byte of the 4-byte [K2,ec_lo,0,0] marker bled in, because the
    # marker itself doesn't use a 5-byte "235" prefix). We cut this off;
    # the fill value is not the fixed 240, but the most frequent value
    # among the pixels already decoded in the row - this tends to be a
    # frame/background color (validated with BMP: FH018L00 row0/1 - the
    # most frequent pixel (here 42) gives a much better approximation
    # than 240, 87/115 -> 103/115). Note: this missing region is likely a
    # framebuffer-level "not redrawn" area in the game (the position of
    # the noise/discrepancy varies per the user's observation), so there
    # is a fundamental limit to perfect reconstruction here - this is
    # just the best achievable approximation. ONLY applied for L00
    # (W=115) - for S00 (W=55) the orphan "0" often comes from the [1,0]
    # pattern or from actual pixel data, and the old 240/continuity logic
    # is more reliable (validated with BMP: FD026S00 row2 showed a
    # regression when this heuristic was also activated for S00).
    if W > 55 and len(raw_px) >= 1 and raw_px[-1] == 0 and len(raw_px) < W:
        raw_px_trimmed = raw_px[:-1]
        if len(raw_px_trimmed) > 0:
            counts = {}
            for v in raw_px_trimmed:
                counts[v] = counts.get(v, 0) + 1
            common_val = max(counts.items(), key=lambda kv: kv[1])[0]
            pad = W - len(raw_px_trimmed)
            result = bytes(raw_px_trimmed) + bytes([common_val]) * pad
            return result[:W]

    # There are two possible alignments: left (data at the start of the
    # row, fill at the end) or right (fill at the start, data at the end
    # of the row) - both occur in practice (see FH011S00 row29-31,
    # FH014S00 row40). We decide with a continuity heuristic: compared to
    # the previous decoded row (prev_row), which alignment gives a
    # smaller total absolute difference in the corresponding columns -
    # this relies on portraits mostly consisting of smooth, slowly
    # changing color gradients, so the correct alignment "fits" the
    # neighboring row better.
    if len(raw_px) == 0:
        return bytes(W)
    fill_value = 240
    pad = W - len(raw_px)
    left_aligned = bytes(raw_px) + bytes([fill_value]) * pad
    if pad == 0 or prev_row is None:
        return left_aligned[:W]

    right_aligned = bytes([fill_value]) * pad + bytes(raw_px)

    def _continuity_score(row):
        return sum(abs(a - b) for a, b in zip(row, prev_row))

    if _continuity_score(right_aligned) < _continuity_score(left_aligned):
        return right_aligned[:W]
    return left_aligned[:W]


def _get_trailer_bytes(hist, W, H, hp_end):
    """
    Extract the "trailing patch block" found at the END of the
    decompressed stream (a closing fix-up block). This is a structure
    that was previously unknown, and follows AFTER the main per-row
    decoding, starting with the fixed header [235,0,0,0,128]. Contents:
    1) Section1 - explicit-pixel-data patch entries
    [count,p1=4*row,p2,p3]+count data bytes (padded to 4-byte alignment),
    2) [0,0,0,128] separator, 3) Section2 - 8-byte, per-row index table
    entries (meaning not yet fully understood), 4) [0,0,0,128] closing
    terminator. Currently only Section1 is used (see
    _parse_trailer_patches).
    """
    markers = _collect_row_markers(hist, W, H, hp_end)
    if not markers:
        return b''
    last_marker_row = max(markers.keys())
    lm, _lk = markers[last_marker_row]
    steps = (H - 1) - last_marker_row
    eo = (lm - W) + steps * (W + 5)
    tail_start = eo + W
    if tail_start < 0 or tail_start > hp_end:
        return b''
    return bytes(hist[tail_start:hp_end])


def _parse_trailer_patches(trailer, W, H, main_patches=None):
    """
    Process the Section1 part of the trailing patch block: extract
    explicit-pixel-data patch entries (count, row, p2, p3, data).
    Destination column: see _apply_trailer_patches (direct formula,
    same as Section2/main markers - NOT a left/right-alignment guess,
    that was an earlier, superseded theory). Entries follow each other
    4-byte aligned (4-byte header + count data bytes, then padded with
    zeros to the next 4-byte boundary by (-(4+count))%4).

    ROW DISAMBIGUATION (v2.18): `p1` is only 1 byte, so it can only
    encode `(4*row) mod 256` - i.e. row mod 64, not the real row, for
    any H>64. This is the SAME underlying limitation already found and
    fixed in Section2 (_parse_trailer_section2, v2.13) - but Section2's
    fix (detecting wraps by entries appearing in increasing real-row
    order) does NOT apply here: confirmed Section1's entries are NOT
    written in row order at all (e.g. raw rows
    11,29,16,15,28,37,5,20,24,... on CFUN0080 - no order to exploit).

    Instead, disambiguation uses COVERAGE: a genuine Section1 entry
    exists to fill a column range NOT already covered by the row's own
    main per-row patch (see _rebuild_rows_v2_with_patches) - that's the
    whole point of a "patch". So if an entry's destination range is
    found to be ALREADY fully covered by the (raw_row mod 64)'s main
    patch, the entry almost certainly belongs to the wrapped row
    (raw_row + 64) instead, where the SAME destination range is
    genuinely uncovered. Validated on CFHU0014: entries nominally for
    raw rows 27-30 were all fully covered already at those rows, but
    NOT at rows 91-94 (their +64 wraps) - and those are exactly the two
    defect regions (rows 28-30 and 91-94) the person spotted by eye.
    Requires `main_patches` (the second return value of
    _rebuild_rows_v2_with_patches) - without it, no disambiguation is
    attempted (kept backward compatible: raw_row is used as-is).

    Returns: [(row, count, p2, p3, data), ...]
    """
    def _is_covered(row, off, count):
        if main_patches is None or row >= len(main_patches):
            return False
        for (poff, pK, _) in main_patches[row]:
            if poff <= off and off + count <= poff + pK:
                return True
        return False

    entries = []
    if len(trailer) < 5 or trailer[0] != 235:
        return entries
    pos = 5
    n = len(trailer)
    while pos + 4 <= n:
        c, p1, p2, p3 = trailer[pos], trailer[pos+1], trailer[pos+2], trailer[pos+3]
        if c == 0:
            break
        if not (1 <= c <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H and pos+4+c <= n):
            break
        raw_row = p1 // 4
        offset = p3 * 8 + (p2 // 32)
        row = raw_row
        if raw_row + 64 < H and _is_covered(raw_row, offset, c):
            row = raw_row + 64
        data = trailer[pos+4:pos+4+c]
        entries.append((row, c, p2, p3, data))
        newpos = pos + 4 + c
        pad = (-(4 + c)) % 4
        pos = newpos + pad
    return entries


def _apply_trailer_patches(rows, entries, W, main_patches=None):
    """Inserts the Section1 patches into the appropriate row, overwriting
    the previous (placeholder/fallback) content.

    DESTINATION FORMULA (v2.14, superseding the old left/right-alignment
    guess): the destination column is `offset = p3*8 + (p2//32)` - THE
    SAME formula already used for the main per-row [K,p1,p2,p3] markers
    (see _rebuild_rows_v2_with_patches) and for Section2 (see
    _apply_trailer_section2). Validated end-to-end against oracle BMPs:
    e.g. CFUN0080 row33's three S1 entries (p2/p3 = (224,2),(0,0),(224,6))
    decode to offsets 23, 0, 55 - all three land exactly where the oracle
    image has matching pixel data, vs. the old "all p2=p3=0 -> left edge,
    else -> right edge" guess, which was only ever a coarse approximation
    that happened to hold for the cases it was validated on at the time.

    SKIP FULL ROWS (v2.14): if a row already has a full (K>=W) explicit
    patch from the main reconstruction, it has no real "gap" to patch -
    applying a Section1 entry there was found to occasionally overwrite
    perfectly correct pixel data with a stray/duplicate patch (seen on
    FU000L04). `main_patches`, if given, is used to detect and skip this.
    """
    full_rows = set()
    if main_patches is not None:
        for ri, plist in enumerate(main_patches):
            for (_off, K, _explicit) in plist:
                if K >= W:
                    full_rows.add(ri)
    for row, count, p2, p3, data in entries:
        if row >= len(rows) or count > W or count <= 0 or row in full_rows:
            continue
        old = rows[row]
        if len(old) != W:
            continue
        offset = p3 * 8 + (p2 // 32)
        offset = max(0, min(offset, W - count))
        new_row = old[:offset] + bytes(data) + old[offset+count:]
        rows[row] = new_row
    return rows


def _parse_trailer_section2(trailer, W, H):
    """
    Process the Section2 part of the trailing patch block. Each entry is
    8 bytes: [X, p1=4*row, p2, p3, Y, Z, 0, 0]. MEANING (validated against
    BMP ground truth, on ~30 entries, see the session notes): this is an
    LZ-style "back-reference" - the Y,Z fields TOGETHER encode an
    ABSOLUTE position in the decompressed `hist` buffer (16-bit, little
    endian: position = Z*256 + Y), from which X bytes must be copied into
    the row. See _apply_trailer_section2 for the destination column.

    ROW UNWRAPPING (v2.12): `p1` is only 1 byte, so it can only encode
    `(4*row) mod 256` - i.e. it disambiguates row mod 64, not the real
    row, for any H>64 (true for MIDGARD's 115x127 portraits). Entries
    are written in increasing real-row order, so a row value that drops
    BELOW the previous entry's row signals a wrap to the next 64-row
    block. Without this, e.g. real row 65's entry gets misread as row 1
    and collides with row 1's own (correct) entry - this was the cause
    of a "white box" defect seen on several MIDGARD.DBI portraits
    (e.g. CFUN0080, FU000L03) where a legitimate gap-fill for a high row
    got applied to the wrong, low-numbered row instead, overwriting
    correct dark pixel data with an unrelated light-colored patch.
    """
    if len(trailer) < 5 or trailer[0] != 235:
        return []
    pos = 5
    n = len(trailer)
    while pos + 4 <= n:
        c, p1 = trailer[pos], trailer[pos+1]
        if c == 0:
            break
        if not (1 <= c <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H and pos+4+c <= n):
            break
        newpos = pos + 4 + c
        pad = (-(4 + c)) % 4
        pos = newpos + pad
    if trailer[pos:pos+4] != bytes([0, 0, 0, 128]):
        return []
    pos += 4
    entries = []
    wrap = 0
    prev_raw_row = -1
    while pos + 8 <= n:
        X, p1, p2, p3, Y, Z, z1, z2 = trailer[pos:pos+8]
        if X == 0 and p1 == 0:
            break
        if not (0 < X <= W and p1 % 4 == 0 and 0 <= p1 // 4 < H):
            break
        raw_row = p1 // 4
        if raw_row < prev_raw_row:
            wrap += 64
        prev_raw_row = raw_row
        row = raw_row + wrap
        if row >= H:
            # Past the real row count - either genuinely malformed data,
            # or (H % 64 == 0 edge case aside) we mis-detected a wrap.
            # Stop rather than risk attributing entries to a bogus row.
            break
        entries.append((row, X, p2, p3, Y, Z))
        pos += 8
    return entries



def _apply_trailer_section2(rows, entries, s1_entries, hist, W, main_patches=None):
    """
    Apply the Section2 entries: copy X bytes from absolute position
    Z*256+Y of the `hist` buffer to the appropriate place in the row.

    DESTINATION FORMULA (v2.14, superseding the old gap-matching
    heuristic): the destination column is `offset = p3*8 + (p2//32)` -
    THE SAME formula used for the main per-row markers and for Section1
    (see _apply_trailer_patches). The previous approach tried to INFER
    the destination by matching Section2 entries 1:1 against the "gaps"
    left between known anchors (main patch / Section1), falling back to
    a guessed formula when the count didn't match exactly. That broke
    down whenever a row's gap(s) were filled by a DIFFERENT number of
    Section2 entries than there were gaps (e.g. one row, one big gap,
    but three sequential Section2 entries meant to tile across it) -
    seen as a "white box" defect on CFUN0080/FU000L03/FU000L04. Since the
    destination is actually given directly by p2/p3 on each entry, no
    gap-counting or entry-matching is needed at all - confirmed by
    end-to-end pixel-exact validation against 7 oracle BMPs (see
    PROJECT_HANDOFF).

    SKIP FULL ROWS (v2.14): a row that already has a full (K>=W) main
    patch has no real gap - applying a Section2 copy there was found to
    occasionally overwrite correct explicit pixel data with an unrelated
    (and visibly wrong - usually background/light-colored) patch, seen
    clearly on FU000L04 rows 1-8. `main_patches`, if given, is used to
    detect and skip this.

    `s1_entries` is accepted but no longer used for destination
    inference - kept as a parameter for call-site compatibility.
    """
    full_rows = set()
    if main_patches is not None:
        for ri, plist in enumerate(main_patches):
            for (_off, K, _explicit) in plist:
                if K >= W:
                    full_rows.add(ri)

    hist_bytes = bytes(hist)
    for (row, X, p2, p3, Y, Z) in entries:
        if row >= len(rows) or X <= 0 or X > W or row in full_rows:
            continue
        old = rows[row]
        if len(old) != W:
            continue
        offset = p3 * 8 + (p2 // 32)
        offset = max(0, min(offset, W - X))
        srcpos = Z * 256 + Y
        if srcpos < 0 or srcpos + X > len(hist_bytes):
            continue
        copied = hist_bytes[srcpos:srcpos+X]
        new_row = old[:offset] + copied + old[offset+X:]
        rows[row] = new_row
    return rows


def decode_portrait_block(data, pp, init_codes):
    """Decode a single FD-style portrait MQRC block at offset `pp`.

    GENERIC IN H (v2.12): earlier versions only ran this for H==67
    (UNIT.DBI's S00/L00 portraits). The algorithm itself never actually
    depended on H==67 anywhere - that was just an overly narrow guard in
    the caller. Confirmed by direct trace/test: MIDGARD.DBI's CF*/FH*
    portraits (H=127) decode correctly through this exact same pipeline
    once it's actually invoked with the block's real H - this is what
    fixed the "black box" defect on e.g. CFHU0007/FH000L01 (see CHANGELOG).

    Returns a dict: {'name','bt','W','H','rows','pp','sA','hp_end',
    'trailer_patches','trailer_section2'} - same shape as before, just
    without the palette (caller attaches the active palette).
    Returns None if `pp`'s block has W not in (55,115) - that's the one
    real structural requirement (it picks the L00 vs. S00 algorithm
    branch). NOTE: there is deliberately no `bt` check here (e.g. the
    old UNIT.DBI-specific `bt>=164` heuristic) - `bt` numbering is NOT
    consistent across .DBI files/categories (MIDGARD.DBI's CF*/FH*
    portraits use bt=52/53/125, which the old heuristic would have
    wrongly rejected). Whether a block IS a portrait-style block at all
    is the caller's/classifier's job (see classify_block_kind()).
    """
    W=data[pp+40]; H=data[pp+42]
    if W not in (55,115):
        return None
    bt=struct.unpack_from('<I',data,pp+8)[0]

    sA=struct.unpack_from('<I',data,pp+12)[0]
    hp_end=data[pp+37]|(data[pp+38]<<8)
    stream=data[pp+48:pp+28+sA]
    name=data[pp+28:pp+36].rstrip(b'\x00').decode('ascii','replace')

    hist,hp=decompress(stream,init_codes,hp_end)
    if W == 115:
        # NEW, validated algorithm for L00 (2026-06-18, session 5):
        # see the _rebuild_rows_v2 documentation. Each row is
        # preceded by a [K,p1=4*row,p2,p3] marker; if K<W,
        # offset=p3*8+p2//32 (validated on ~20+ samples with
        # 100% match), columns outside the marker are
        # inherited from the previous row (an approximation).
        rows, _all_patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
        rows = [bytes(r) for r in rows]
    else:
        # OLD, heuristic fine-tuned for S00 (position-consistent
        # marker collection + two-phase short-row chain search -
        # see _collect_row_markers / _find_short_row_pad). KEPT,
        # because the new algorithm caused a regression on S00
        # (99.45% -> ~95%) - probably needs the S00-specific
        # placeholder patterns (_PLACEHOLDER_PREFIXES), which
        # the new algorithm doesn't know about.
        _ec_offset = 1
        rows=[]
        sorted_markers=sorted(_collect_row_markers(hist,W,H,hp_end).items())
        r=0; midx=0
        while r<H:
            if midx<len(sorted_markers) and sorted_markers[midx][0]==r:
                _mrow,(_mpos,_K)=sorted_markers[midx]; midx+=1
                # EXTRA-SENTINEL FIX (found this session, Menus.dbi's
                # FHUA/FDWA/FHED/FHUB/GODHU): the byte(s) immediately
                # before the marker can themselves be stray 235 bytes -
                # NOT real pixel data, just happening to share the same
                # value as the marker's own sentinel byte. A naive
                # "look back exactly W bytes from the marker" window
                # then silently includes 1-2 bytes too many at the BACK
                # of the window while implicitly dropping that many real
                # pixels off the FRONT (since the window is fixed-width)
                # - this is what showed up as a small, row-by-row
                # horizontal shift (-1, -2px...) confined to whichever
                # rows are reconstructed by this direct-marker path
                # (rows handled by the newer v2 per-row patch system are
                # unaffected and were already pixel-perfect).
                # FIX: count how many consecutive 235 bytes sit right
                # before the marker, and shift the lookback window back
                # by exactly that many bytes on BOTH ends. Validated on
                # FHUA: 31/38 directly-marked rows go from a wide range
                # of mismatches (40-50+ px) down to 0, most others to
                # just 1 (residual unrelated noise) - 5 rows still have
                # a separate, larger defect (rows 30/45/48/52/56),
                # currently believed to be a different mechanism (the
                # short-row continuation chain / placeholder logic),
                # being investigated separately.
                _extra=0
                while _mpos-1-_extra>=0 and hist[_mpos-1-_extra]==235:
                    _extra+=1
                _rs=_mpos-W-_extra
                px=bytes(hist[max(0,_rs):_mpos-_extra])
                if len(px)<W: px=px+bytes(W-len(px))
                rows.append(px[:W]); r+=1
                if _K<W:
                    _pos=_mpos+5; _cr=r
                    while _cr<H:
                        _ec_full=4*(_cr+_ec_offset)
                        _result=_find_short_row_pad(hist,_pos,_ec_full,W,hp_end)
                        if _result is None: break
                        _k,_K2,_newpos,_is_tail=_result
                        _spx=bytes(hist[_pos:_pos+_k])
                        if _is_tail:
                            rows.append(_reconstruct_short_row(_spx,_cr,W,rows[-1] if rows else None))
                            _cr+=1; r+=1
                            if _cr>=H: break
                            _next_ec=4*(_cr+_ec_offset)
                            _next_result=_find_short_row_pad(hist,_newpos,_next_ec,W,hp_end)
                            if _next_result is not None and _next_result[0]<W:
                                _pos=_newpos
                                continue
                            _npx=bytes(hist[_newpos:_newpos+W])
                            if len(_npx)<W: _npx=_npx+bytes(W-len(_npx))
                            rows.append(_npx[:W]); _cr+=1; r+=1
                            _pos=_newpos+W
                            continue
                        rows.append(_reconstruct_short_row(_spx,_cr,W,rows[-1] if rows else None))
                        _pos=_newpos; _cr+=1; r+=1
                        if _K2==W: break
            else:
                if rows and midx>0:
                    _lr,(_lm,_lk)=sorted_markers[min(midx-1,len(sorted_markers)-1)]
                    _steps=r-_lr
                    _eo=(_lm-W)+_steps*(W+5)
                    rows.append(bytes(hist[max(0,_eo):_eo+W]))
                else:
                    rows.append(bytes(W))
                r+=1

        # ALTERNATE-MARKER-CONVENTION FALLBACK (found this session,
        # ICONS.DBI's ICNAR*/ICNxx* item icons): when the old 235-
        # sentinel heuristic above finds almost nothing (a normal,
        # well-formed S00 portrait finds markers for most of its rows;
        # these item icons found markers for as few as 4 of 67 rows),
        # the block is very likely using the different marker
        # convention described in `_decode_s00_chain_alt` instead.
        # NOTE: we do NOT compare "non-zero byte coverage" between the
        # old and new result to decide - tried that first, but the old
        # heuristic's row-estimate fallback (`_eo=(_lm-W)+_steps*(W+5)`)
        # grabs essentially random bytes from the buffer when markers
        # are this sparse, and random bytes are usually non-zero too,
        # so that comparison falsely favored the old (garbage) result
        # on 3 of the 5 validation samples. Sparse old-marker-count is
        # itself a strong enough signal on its own: if there's a usable
        # alt-chain at all, prefer it unconditionally in this case.
        _used_alt = False
        if len(sorted_markers) < max(10, H*0.25):
            _alt = _decode_s00_chain_alt(hist, W, H, hp_end)
            if _alt is not None:
                rows, _alt_covered = _alt
                _used_alt = True

        # HYBRID (session 5, section 3.10, refined): we also run
        # the new, validated multi-patch algorithm, and OVERWRITE
        # the old heuristic's result AT COLUMN LEVEL with EVERY
        # patch found (even just 1 - every patch is byte-exact,
        # validated explicit data, never an approximation).
        # Columns NOT covered by patches keep the old heuristic's
        # result (placeholder/alignment logic), since that gives
        # a better approximation than naive "inherit from
        # previous row" (validated: FN127S00 row40 - 1 patch,
        # [32,55), byte-exact; in the [0,32) range the old
        # heuristic's result remains).
        # SKIPPED when `_decode_s00_chain_alt` was used instead (see
        # above): on the ICNAR* validation samples, this overlay was
        # found to occasionally apply a spurious coincidental v2-style
        # patch on top of the alt result (e.g. ICNAR003 row27), making
        # an already-good alt decode slightly worse. `_all_patches` is
        # still computed (the trailer-patches step below needs it
        # regardless), just not applied to `rows` in this case.
        _new_rows, _all_patches = _rebuild_rows_v2_with_patches(hist, W, H, hp)
        if not _used_alt:
            rows = [bytearray(row) for row in rows]
            for _ri in range(min(H, len(rows))):
                for _off, _K, _explicit in _all_patches[_ri]:
                    rows[_ri][_off:_off+_K] = bytes(_explicit)
            rows = [bytes(row) for row in rows]

    _trailer = _get_trailer_bytes(hist, W, H, hp_end)
    _patches = _parse_trailer_patches(_trailer, W, H, _all_patches)
    if _patches:
        rows = _apply_trailer_patches(list(rows), _patches, W, _all_patches)
    _s2patches = _parse_trailer_section2(_trailer, W, H)
    if _s2patches:
        rows = _apply_trailer_section2(list(rows), _s2patches, _patches, hist, W, _all_patches)

    return {
        'name':name,'bt':bt,'W':W,'H':H,
        'rows':rows,
        'pp':pp,'sA':sA,'hp_end':hp_end,
        'trailer_patches':_patches,'trailer_section2':_s2patches
    }


def read_portraits(dbi_path, init_codes):
    """Read all FD portraits from a .DBI file (originally written for
    UNIT.DBI, but works on any file using this block layout - e.g.
    MIDGARD.DBI's CF*/FH* portraits, since v2.12). Thin wrapper around
    decode_portrait_block() that also tracks the active palette and
    walks every MQRC block in the file."""
    with open(dbi_path,'rb') as f: data=f.read()
    portraits=[]; last_pal=[(0,0,0)]*256; p=0

    while True:
        pp=data.find(b'MQRC',p)
        if pp==-1: break
        bt=struct.unpack_from('<I',data,pp+8)[0]

        if bt==2:  # paletta blokk
            last_pal=[]
            for i in range(256):
                B=data[pp+28+i*4]; G=data[pp+28+i*4+1]; R=data[pp+28+i*4+2]
                last_pal.append((R,G,B))

        elif bt>=164:
            result = decode_portrait_block(data, pp, init_codes)
            if result is not None:
                result['palette'] = list(last_pal)
                portraits.append(result)
        p=pp+1
    return portraits, data


def _minimal_row_patch(row, prev_row, W):
    """Returns the (offset, K) pair: the smallest contiguous
    [offset,offset+K) range OUTSIDE of which `row` matches `prev_row`
    exactly. If prev_row is None (first row): (0, W) - full row explicit.

    IMPORTANT: K=0 is NEVER allowed, even if the row is COMPLETELY
    identical to the previous one! The reason: with K=0, the decoder's
    offset check (0<=offset<=W-K) is ALWAYS true (W-0=W), so a K=0 marker
    is accepted PRACTICALLY WITHOUT FILTERING - this leads to random
    false positives in the "search for next patch" logic if a [0,
    target_ctr] byte pair happens to occur PURELY BY CHANCE in the pixel
    data (validated: FH008S00 row64 - a false K=0 match in row65's pixel
    data completely wiped out the correct decoding of row65 and row66).
    If the row matches the previous one exactly, we write K=1 (a single,
    arbitrary - here: the first - column duplicated explicitly), which
    guarantees avoiding this risk at the cost of a negligible size
    increase.
    """
    if prev_row is None:
        return (0, W)
    lead = 0
    while lead < W and row[lead] == prev_row[lead]:
        lead += 1
    if lead == W:
        return (0, 1)  # matches exactly - minimal, safe K=1
    trail = 0
    while trail < W - lead and row[W-1-trail] == prev_row[W-1-trail]:
        trail += 1
    offset = lead
    K = W - lead - trail
    return (offset, K)


def _multi_row_patches(row, prev_row, W, min_gap=6):
    """Returns the [(offset,K), ...] list: each "island" that differs from
    the PREVIOUS row as a SEPARATE patch (validated: the native format
    allows MULTIPLE [K,p1,p2,p3] patches per row, see section 3.9).
    If two differing islands are separated by fewer than `min_gap`
    matching columns, they are merged into a single patch (because of the
    4-byte marker overhead, this gives a smaller total size than two
    separate patches). If prev_row is None (first row): [(0, W)] - full
    row explicit.
    """
    if prev_row is None:
        return [(0, W)]
    diff = [row[c] != prev_row[c] for c in range(W)]
    if not any(diff):
        return [(0, 1)]  # matches exactly - minimal, safe K=1
    islands = []
    c = 0
    while c < W:
        if diff[c]:
            start = c
            while c < W and diff[c]:
                c += 1
            islands.append([start, c])  # [start, end)
        else:
            c += 1
    # Merge small gaps (overhead reduction)
    merged = [islands[0]]
    for s, e in islands[1:]:
        if s - merged[-1][1] < min_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e - s) for s, e in merged]


def make_hist_buffer(rows, W, H):
    """Raw history buffer for the encoder (v2.2 - follows the native
    structure, with VARIABLE-LENGTH rows, MULTI-PATCH encoding, and a
    SELF-CHECKING build).

    PREVIOUS BUGS:
    - v2.0: every row was written at FULL (K=W) length, with a FIXED
      stride (W+5), which did not match the native structure -> the
      game's native decoder produced noise/crashes.
    - v2.1: a SINGLE, contiguous explicit patch was generated for each
      row (the smallest [offset,offset+K) range covering ALL differing
      columns relative to the previous row). This was correct, but for
      SCATTERED differences (especially in wide L00 portraits) it
      produced needlessly LARGE patches (the range between the two
      outermost differences, even the parts that actually MATCHED, ended
      up in the explicit data) - this often made the stream LARGER than
      the native slot size.

    v2.2: for each row, the actual difference "islands" are encoded as
    SEPARATE patches (see _multi_row_patches) - validated by the section
    3.9 discovery that a row can contain MULTIPLE [K,p1,p2,p3] patches,
    all with the same p1 (=4*row_index) value.

    Structure of each row in the linear buffer:
      (for row>0, BEFORE EVERY patch:) [235 prefix]
      [K] [p1=(4*r)%256] [p2] [p3]
      [K explicit pixel bytes]
      (further patches of the row follow the same way, one after another,
      with the SAME p1)
    where for K<W, offset = p3*8 + p2//32, and for K==W the K bytes are
    the FULL row (p2=p3=0, only a single patch is possible in that case).

    SELF-CHECK (critical, see v2.1 documentation): AFTER every buffer
    build, we decode it back with our own validated decoder; any row that
    doesn't match exactly (e.g. a random false patch match in the pixel
    data) is forced to a FULL (K=W) row, and we rebuild, until every row
    matches exactly.
    """
    def build(force_full):
        buf = bytearray()
        prev_row = None
        for r in range(H):
            row = bytes(rows[r][:W])
            ctr = 4 * r
            p1 = ctr % 256
            # For portraits with 64+ rows (H>64), the p1 field (1 byte,
            # %256) repeats every 64 rows (4*64=256=0 mod 256) -- this
            # causes a shift in the game (empirically validated: the data
            # of rows 64-66 ends up in the place of rows 0-2). The old
            # _collect_row_markers heuristic already documented this
            # ("for portraits with 64+ rows ... 8-bit overflow"), handling
            # it as a 2-byte (p1=LO, p2 BIT0=HI) counter. FIX: we write the
            # high bit (ctr>>8)&1 into the LOWEST BIT (bit0) of the p2
            # field - this does NOT interfere with the offset formula used
            # for K<W (offset=p3*8+p2//32, which only uses bits 5-7 of p2,
            # leaving bits 0-4 free).
            hi_bit = (ctr >> 8) & 1
            if r in force_full or prev_row is None:
                if r > 0:
                    buf += bytes([235])
                buf += bytes([W, p1, hi_bit, 0])
                buf += row
            else:
                patches = _multi_row_patches(row, prev_row, W)
                for offset, K in patches:
                    buf += bytes([235])
                    if K >= W:
                        buf += bytes([W, p1, hi_bit, 0]); buf += row
                    else:
                        p3 = offset // 8
                        p2 = (offset % 8) * 32 | hi_bit
                        buf += bytes([K, p1, p2, p3])
                        buf += row[offset:offset+K]
            prev_row = row
        trailer = bytes([235, 0, 0, 0, 128, 0, 0, 0, 128, 0, 0, 0, 128])
        buf += trailer
        return buf, len(buf)

    # IMPORTANT (2026-06-19, validated with in-game testing): the patch/
    # inherit ("inherit from previous row") encoding does NOT do the same
    # thing in the GAME's actual renderer as in our PURE decoder - it
    # caused in-game noise exactly on the columns that the patch system
    # left to be "inherited". Our own self-check would never have caught
    # this, because OUR decoder handles inheritance correctly - only the
    # NATIVE one doesn't. Until we find the real inheritance rule, we
    # write EVERY row FULLY explicit (K=W) - this gives a correct,
    # validated in-game result, at the cost of compression efficiency.
    force_full = set(range(H))
    for _ in range(H + 2):  # at most H+2 iterations - guaranteed to converge
        buf, hp_end = build(force_full)
        check_rows, _ = _rebuild_rows_v2_with_patches(buf, W, H, hp_end)
        bad = [r for r in range(H) if bytes(check_rows[r]) != bytes(rows[r][:W])]
        if not bad:
            return bytearray(buf), hp_end
        force_full.update(bad)
    # Final safety attempt: every row full (must always be correct)
    buf, hp_end = build(set(range(H)))
    return bytearray(buf), hp_end

def build_mqrc(compressed, W, H, bt, name, hp_end):
    """Assemble an MQRC block.
    CRITICAL fields:
      [16..19] = copy of sA (without it: empty portrait in the game!)
      [20..23] = flag 1 (without it: empty portrait in the game!)
    """
    sA=20+len(compressed)
    hdr=bytearray(48)
    hdr[0:4]=b'MQRC'
    struct.pack_into('<I',hdr,8,bt)
    struct.pack_into('<I',hdr,12,sA)
    struct.pack_into('<I',hdr,16,sA)   # COPY OF sA - required!
    struct.pack_into('<I',hdr,20,1)    # flag=1 - required!
    hdr[37]=hp_end&0xFF; hdr[38]=(hp_end>>8)&0xFF
    hdr[39]=0x80   # REQUIRED - present as 0x80 in 158/159 sampled real records (2026-06-25)
    hdr[44]=hdr[37]; hdr[45]=hdr[38]
    hdr[40]=W; hdr[42]=H
    nb=name.encode('ascii')[:8]; hdr[28:28+len(nb)]=nb
    return bytes(hdr)+compressed

# --- Image I/O (Pillow) ------------------------------------------------------

def save_portrait_png(rows, palette, W, H, path):
    """Save a portrait as an RGBA PNG (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        print(t('pillow_missing'))
        print(t('pillow_missing_pixel_data', w=W, h=H, n=len(palette)))
        return
    img=Image.new('P',(W,H))
    flat_pal=[]
    for r,g,b in palette: flat_pal+=[r,g,b]
    img.putpalette(flat_pal)
    px=bytearray()
    for row in rows: px+=bytes(row[:W])
    img.frombytes(bytes(px))
    img.save(path)

def load_portrait_png(path, palette):
    """Load a PNG as palettized pixels.

    Finds the best match to the DBI palette from the image's own palette.
    """
    try:
        from PIL import Image
    except ImportError:
        sys.exit(t('pillow_missing_short'))
    img=Image.open(path)
    W,H=img.size

    # Palette mode: use directly
    if img.mode=='P':
        px=list(img.tobytes())
        rows=[bytes(px[r*W:(r+1)*W]) for r in range(H)]
        return rows, W, H

    # RGB(A) -> closest palette color
    img=img.convert('RGB')
    px=list(img.tobytes())
    rows=[]
    for r in range(H):
        row=bytearray()
        for c in range(W):
            ri,gi,bi=px[(r*W+c)*3],px[(r*W+c)*3+1],px[(r*W+c)*3+2]
            best_i=0; best_d=10**9
            for i,(rp,gp,bp) in enumerate(palette):
                d=(ri-rp)**2+(gi-gp)**2+(bi-bp)**2
                if d<best_d: best_d=d; best_i=i
            row.append(best_i)
        rows.append(bytes(row))
    return rows, W, H

# --- ISO.DBI graphics decoding (EXPERIMENTAL, NEW - 2026-06-23) -------------
#
# ISO.DBI (and presumably other, non-portrait DBI files) graphics blocks do
# NOT store pixels as a raw WxH raster, but in order-independent, 4-BYTE
# ALIGNED records that skip palette index 0 (=transparent):
#
#   [K, c1, c2, c3, <K bytes of pixel data>]   - size 4+K, rounded up to 4
#
#   K   = number of explicit (non-transparent) pixels in the patch
#   c1  = 4 * row index (1 byte -> wraps around at row 64, see below)
#   c2,c3 -> offset = c3*8 + c2//32  (the patch's starting column, if K<W)
#   if K>=W, the full row is explicit, there is no offset
#
# VALIDATED (2026-06-23): 3 reference images (unit, flag, and landmark
# sprite), all three matching PIXEL-EXACTLY (100.00%) against an
# independent, user-provided ground-truth BMP.
#
# KNOWN LIMITATION: for large graphics with many single-color areas (e.g.
# GCAD0018, a "capital" building) the chain breaks at some point on a
# presumably SEPARATE, RLE-like "repeated color" sequence - this has not
# yet been explored. decode_iso_block() flags this (status['clean']=False),
# and the image may be incomplete/corrupted from that row downward.
# Disambiguating the 64-row wraparound (which multiple of 64 to add to the
# 0-63 range value obtained from c1) is also NOT YET solved - our samples
# so far (max. 88-tall canvas, but actual content never went above 64)
# didn't require it, and note for the records right before the GCAD0018
# break above: the row index increases evenly, in order (NOT grouped by K,
# as in the smaller sprites) - this is an important, not yet finalized
# conclusion: it SEEMS the ordering convention may DIFFER PER IMAGE (small
# sprites grouped by K, large ones in row order).

def _find_palette_in_dbi(data):
    """Read the last bt==2 (palette) block from a generic (not just
    UNIT.DBI-specific) .DBI file."""
    palette = None
    p = 0
    while True:
        pp = data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', data, pp + 8)[0]
        if bt == 2:
            palette = [(data[pp + 28 + i * 4 + 2], data[pp + 28 + i * 4 + 1], data[pp + 28 + i * 4])
                       for i in range(256)]
        p = pp + 1
    return palette


def list_iso_graphics(data):
    """List the graphics blocks of an ISO.DBI (or similar) file: every
    MQRC block whose name is 8 printable ASCII characters, and which is
    not the palette (bt==2) or the starting name-index table (sA%16==0
    AND sA2!=sA pattern - see read_name_index_block). Returns
    [(pp,name,bt,W,H), ...].
    """
    out = []
    p = 0
    while True:
        pp = data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', data, pp + 8)[0]
        sA = struct.unpack_from('<I', data, pp + 12)[0]
        sA2 = struct.unpack_from('<I', data, pp + 16)[0]
        name_raw = data[pp + 28:pp + 36]
        is_name_index = (sA == 0 and sA2 > 0 and sA2 % 16 == 0)
        if bt != 2 and not is_name_index and sA > 0:
            try:
                name = name_raw.rstrip(b'\x00').decode('ascii')
                if name and all(32 <= b < 127 for b in name_raw if b != 0):
                    W = struct.unpack_from('<H', data, pp + 40)[0]
                    H = struct.unpack_from('<H', data, pp + 42)[0]
                    out.append((pp, name, bt, W, H))
            except UnicodeDecodeError:
                pass
        p = pp + 1
    return out


def classify_block_kind(name, W, H, bt, data=None, pp=None, init_codes=None, palette=None):
    """Best-effort classification of a single MQRC block into a decode
    'kind': 'portrait', 'iso', or 'iso_partial' (decoded via the same ISO
    algorithm as 'iso', but flagged separately because the algorithm is
    KNOWN to still be incomplete for this category - see PROJECT_HANDOFF
    notes on TWD/TWE/TWH/TWU's "compact-fill/raw-row-block" mystery).

    This is intentionally a THREE-LAYER heuristic, not a lookup table
    that has to be kept in sync by hand for every possible name prefix:

      1. NAME-based override for the categories we've explicitly mapped
         so far (see the project handoff history). This catches the
         known cases where the structural rule below would guess wrong.
      2. STRUCTURAL fallback: every confirmed portrait-style block found
         so far (UNIT.DBI's FD/FN/GP, MIDGARD's CF*/FH*) has W in
         (55,115) - this is what the L00/S00 decompression algorithm is
         built around. Anything else defaults to the ISO-style algorithm,
         which handles arbitrary W/H.
      3. CONTENT-based refinement (v2.19, only runs if `data`/`pp`/
         `init_codes`/`palette` are given - cheap structural checks don't
         have these, so this layer is skipped for plain classify-only
         calls): BATTLE.DBI turned out to have 11 small UI effect icons
         (BOOST1-3, RETRTSD, RUPGRAD, SPBOOST, SPLOWER, PARALYZE, PETRIFY,
         PTBOOST, RETRTSA) that structurally look exactly like a real
         portrait (W=55,H=67,byte39=0x80 - byte-for-byte the same header
         shape) but are actually tiny icons that happen to use the SAME
         canvas size. No name prefix distinguishes them either. What
         DOES: decoding them via the ISO algorithm succeeds cleanly
         (0 gaps) with the real content cropped to a TINY fraction of
         the nominal canvas (6-9% on the 11 confirmed cases), whereas
         every confirmed real portrait checked this way (MIDGARD's
         CFHU0007, ICONS.DBI's ICUSP100) is either 45% or 100% - a wide,
         safe margin. So: if the structural rule says 'portrait', but a
         clean ISO decode crops to under ~25% of the canvas, it's
         reclassified as 'iso'.

    NOT guaranteed to be exhaustive - if a new prefix shows up that
    doesn't fit, decode_any_block() also has a runtime fallback (try
    portrait, fall back to ISO on failure/degenerate result).
    """
    name = (name or '').upper()
    iso_partial_prefixes = ('TWD', 'TWE', 'TWH', 'TWU')
    iso_prefixes = ('ABIL', 'HAND', 'GCUN', 'GSAB', 'LOGO', 'GUN', 'VU', 'VH', 'VD', 'VC', 'THIEF',
                     'ICDSP', 'ICESP', 'ICHSP', 'ICNBAN')
    portrait_prefixes = ('CF', 'FH', 'FD', 'FN', 'GP')

    for pre in iso_partial_prefixes:
        if name.startswith(pre):
            return 'iso_partial'
    for pre in iso_prefixes:
        if name.startswith(pre):
            return 'iso'
    for pre in portrait_prefixes:
        if name.startswith(pre):
            return 'portrait'

    # Unknown prefix - fall back to the structural rule.
    kind = 'portrait' if W in (55, 115) else 'iso'

    if kind == 'portrait' and data is not None and pp is not None and init_codes is not None:
        try:
            grid, gW, gH, status = decode_iso_block(data, pp, init_codes, palette)
            if status['clean'] and gW and gH:
                img = iso_grid_to_image(grid, gW, gH, palette or [(0, 0, 0)] * 256)
                bbox = img.getbbox()
                crop_frac = ((bbox[2]-bbox[0]) * (bbox[3]-bbox[1])) / (gW * gH) if bbox else 0
                if crop_frac < 0.25:
                    kind = 'iso'
        except Exception:
            pass  # any failure here just means "stick with the structural guess"

    return kind


def scan_dbi_blocks(data, init_codes=None, palette=None):
    """Universal block scanner: like list_iso_graphics(), but additionally
    classifies each block's likely decode 'kind' (see classify_block_kind).
    Works on ANY .DBI file - UNIT.DBI, MIDGARD.DBI, CAPITAL.DBI,
    BATTLE.DBI, ISO.DBI, ... - and is the basis for the unified
    decode/list commands (v2.12). Returns
    [{'pp','name','bt','W','H','kind'}, ...].

    If `init_codes`/`palette` are given, classify_block_kind's v2.19
    content-based icon-vs-portrait check also runs (see its docstring) -
    this costs one extra trial decode per structurally-ambiguous block,
    but is the only way `list` can show the SAME classification that
    `decode` will actually use. Pass `palette=None` explicitly only if
    you genuinely don't have one yet; without `init_codes` this
    refinement step is skipped entirely (cheap, name/structure-only).
    """
    out = []
    for pp, name, bt, W, H in list_iso_graphics(data):
        kind = classify_block_kind(name, W, H, bt, data=data, pp=pp,
                                    init_codes=init_codes, palette=palette)
        out.append({'pp': pp, 'name': name, 'bt': bt, 'W': W, 'H': H, 'kind': kind})
    return out



def decode_any_block(data, pp, init_codes, palette, kind=None, name=None, W=None, H=None):
    """Unified decode dispatcher for a single MQRC block (v2.12).

    Picks the portrait (Huffman/L00/S00) or ISO-style algorithm based on
    `kind` (from classify_block_kind - pass it in if you already called
    scan_dbi_blocks(), to avoid re-deriving it). Falls back from portrait
    to ISO at runtime if the portrait path can't handle the block
    structurally (W not in (55,115)) - this makes the dispatcher robust
    even if the name-based classification guessed wrong.

    Returns a uniform dict:
      {'name','kind','W','H','rows'}       - portrait result (rows: list
                                              of W-byte palette-index rows)
      {'name','kind','W','H','grid','status'} - ISO result (grid: see
                                              decode_iso_block; status:
                                              {'clean':bool,...})
    Raises on genuine decode errors (caller should catch per-block, the
    same way cmd_decode already does per-block, so one bad block doesn't abort
    a whole-file batch run).
    """
    if name is None or W is None or H is None:
        bt0 = struct.unpack_from('<I', data, pp + 8)[0]
        name = data[pp + 28:pp + 36].rstrip(b'\x00').decode('ascii', 'replace')
        W = struct.unpack_from('<H', data, pp + 40)[0]
        H = struct.unpack_from('<H', data, pp + 42)[0]
        if kind is None:
            kind = classify_block_kind(name, W, H, bt0, data=data, pp=pp,
                                        init_codes=init_codes, palette=palette)
    elif kind is None:
        bt0 = struct.unpack_from('<I', data, pp + 8)[0]
        kind = classify_block_kind(name, W, H, bt0, data=data, pp=pp,
                                    init_codes=init_codes, palette=palette)

    if kind == 'portrait':
        # ISO-FIRST UNIFIED PATH (v2.26, 2026-06-28) - NOW UNIVERSAL.
        # A full oracle pack (~3593 BMPs across BATTLE/CAPITAL/ICONS/
        # MIDGARD/PALMAP/TERRAIN/ISO/Interf/Menus/ScenEdit) was tested
        # head-to-head: for every one of those files, decode_iso_block()
        # +bbox-crop vs. the dedicated portrait codec. RESULT: in not
        # ONE case, anywhere, was the portrait codec uniquely correct
        # where the ISO path failed ("only-portrait-correct" = 0 on
        # every file, including MIDGARD's CFHU*/CFDW*/FH000L* and
        # Menus.dbi's FHUA/FDWA/FHED/FHUB/GODHU family - the v2.23 fix's
        # own target, now 0/0/0/0/0 mismatched px via the ISO path).
        # Either ISO matches the oracle (and the portrait codec doesn't,
        # or also matches), or BOTH fail (a handful of genuine, deeper
        # residual bugs - EXCHANGE, the TWD/TWE/TWU family, etc. - see
        # PROJECT_HANDOFF for the current list). The dedicated S00/L00
        # portrait-specific machinery (marker search, placeholder
        # reconstruction, chain_alt) is therefore kept only as a
        # fallback for the rare case the ISO decode isn't clean.
        try:
            _grid, _gW, _gH, _status = decode_iso_block(data, pp, init_codes, palette)
        except Exception:
            _status = None
        if _status is not None and _status.get('clean'):
            _img = iso_grid_to_image(_grid, _gW, _gH, palette)
            _bbox = _img.getbbox()
            if _bbox:
                return {'name': name, 'kind': 'iso_unified', 'W': _gW, 'H': _gH,
                        'grid': _grid, 'status': _status, 'bbox': _bbox}
        result = decode_portrait_block(data, pp, init_codes)
        if result is not None:
            return {'name': result['name'], 'kind': 'portrait',
                    'W': result['W'], 'H': result['H'], 'rows': result['rows']}
        # Structural fallback: classifier said "portrait" but W doesn't
        # actually fit the portrait algorithm - try ISO instead.

    grid, gW, gH, status = decode_iso_block(data, pp, init_codes, palette)
    return {'name': name, 'kind': kind if kind != 'portrait' else 'iso',
            'W': gW, 'H': gH, 'grid': grid, 'status': status}


def decode_iso_block(data, pp, init_codes, palette=None):
    """Decode an ISO.DBI-style graphics block.

    Row index and column offset are computed with the SAME formula for
    every record type encountered so far (normal, compact, and the K=0
    raw-row marker, see below):

        row = (c1 // 4) + 64 * (c2 % 32)      # c2's lower 5 bits = wrap band
        off = c3 * 8 + c2 // 32                # c2's upper 3 bits + c3

    Three record layers are handled, tried in this order whenever normal
    parsing gets stuck:

    1. NORMAL record: `[K, c1, c2, c3, <K bytes of pixel data>]`.
    2. COMPACT record (8 bytes, appears after a `[0,0,0,128]` sentinel in
       blocks with large/varied textured areas - "fog of war" clouds,
       building textures, terrain scenes): `[K, c1, c2, c3, <4-byte
       absolute position>]` - no inline pixel bytes; instead, the 4
       trailing bytes are a 32-bit little-endian ABSOLUTE POSITION into
       the decompressed buffer, and K bytes are COPIED from there into
       the row at `off`. This is an LZ-style back-reference, structurally
       identical to the portrait codec's trailer Section2 mechanism (see
       _apply_trailer_section2) - NOT a flat color fill, despite the
       name (kept for continuity with earlier session notes). Mode
       selection (normal vs. compact) is decided by comparing which
       interpretation yields a longer, self-consistent chain right after
       the sentinel.
    3. RAW ROW BLOCK (for large, noisy/incompressible texture bands - was
       originally found as a best-effort fallback for "capital" buildings'
       remaining gaps, now confirmed (alongside the v2.29 sentinel-
       lookahead and decompression-target fixes) to bring CAPITAL.DBI to
       a full, oracle-exact 70/70): a `[K=0, c1, c2, c3]` marker uses the
       SAME row/offset formula as a normal record, but signals that what
       follows is headerless raw pixel data for one or more rows,
       continuing until the next recognizable record.

    Returns: (grid, W, H, status), see the fields below.
    """
    sA = struct.unpack_from('<I', data, pp + 12)[0]
    hp_end = data[pp + 37] | (data[pp + 38] << 8)
    W = struct.unpack_from('<H', data, pp + 40)[0]
    H = struct.unpack_from('<H', data, pp + 42)[0]
    stream = data[pp + 48:pp + 28 + sA]
    # DISCOVERY (2026-06-25): byte 39 of the header is not always 0x80.
    # Large, single-piece background images (e.g. BATTLE.DBI's full-size
    # race terrains) instead have byte39==0x01 - and their declared
    # hp_end is only the length of the FIRST Huffman "chunk" (symbol 272/
    # 273 mid-stream table resets - see decompress()'s do_rebuild/chunk
    # logic, originally found for portraits). For these, decompressing
    # with a target of W*H instead of hp_end lets the existing chunk-
    # boundary handling continue straight through to the real end and
    # recovers the full image (validated pixel-exact against an oracle
    # BMP for BATTLE.DBI's CITY). Ordinary single-chunk blocks (byte39==
    # 0x80) must keep using hp_end as-is - using W*H there would make
    # decompress() try to read past the real end of the stream.
    if data[pp + 39] != 0x80:
        # Safe now that decompress() stops gracefully on running out of
        # real compressed data (see its EOFError handling) instead of
        # raising - so it's fine to always ask for a generous target for
        # any non-standard (multi-chunk) block, regardless of whether
        # it's the 0x01 or 0x02 variant.
        #
        # FIX (v2.29, MIDGARD's TWE0001/2/4/5): W*H alone isn't always
        # generous enough - these blocks have a large compact-record
        # "second pass" that, since compact records can overlap/re-cover
        # already-written pixels via LZ-copies, needs MORE decompressed
        # bytes than the canvas's raw pixel count would suggest (TWE0001
        # needed 1212 bytes past W*H to reach its true end - decompress()
        # naturally plateaus there regardless of how much higher the
        # target is set, so there's no real downside to asking for more).
        hp_target = max(hp_end, W * H * 2)
    else:
        hp_target = hp_end
    hist, hp = decompress(stream, init_codes, hp_target)
    buf = bytes(hist[:hp])
    palette = palette if palette is not None else _find_palette_in_dbi(data)

    def is_valid(p):
        if p + 4 > len(buf):
            return None
        c1, c2, c3 = buf[p + 1], buf[p + 2], buf[p + 3]
        # DISCOVERY (2026-06-25): K is not just byte0 - it's a 10-bit
        # field, byte0 | ((c1&3)<<8), allowing runs up to 1023 pixels.
        # The low 2 bits of c1 are "borrowed" for this; the row formula
        # below only ever used c1>>2 anyway, so this is fully backward
        # compatible (every record encoded so far happens to have had
        # c1&3==0, since K was always <256 for small sprites - this only
        # matters for large, dense/textured regions with long runs).
        K = buf[p] | ((c1 & 3) << 8)
        if K > W:
            return None
        off = 0
        if K < W:
            off = c3 * 8 + c2 // 32
            if not (0 <= off <= W - K):
                return None
        if p + 4 + K > len(buf):
            # The declared K would require more bytes than what's still
            # available in the decompressed buffer - this is NOT a real
            # content record, it's just a coincidental "hit" running into
            # the closing/footer section. Mark it invalid.
            return None
        rec_size = 4 * ((4 + K + 3) // 4)
        return (K, off, rec_size)

    def is_valid_compact(p):
        """Check a compact (8-byte) record header. NOTE (v2.15): despite
        the name, this is NOT a uniform-color fill - see the docstring
        update above. The header (K, off) check is unchanged; only what
        the record MEANS changed."""
        if p + 8 > len(buf):
            return None
        c1, c2, c3 = buf[p + 1], buf[p + 2], buf[p + 3]
        K = buf[p] | ((c1 & 3) << 8)  # extended 10-bit length, see is_valid()
        if K > W:
            return None
        off = c3 * 8 + c2 // 32 if K < W else 0
        if not (0 <= off <= W - K):
            return None
        return (K, off)

    def chain_len(start, steps=6):
        p = start
        n = 0
        for _ in range(steps):
            v = is_valid(p)
            if v is None:
                return n
            p += v[2]
            n += 1
        return n

    SENTINEL = b'\x00\x00\x00\x80'
    GAP_SEARCH_WINDOW = 3000

    grid = [[0] * W for _ in range(H)]
    pos = 0
    nrec = 0
    gaps = []
    compact_used = False

    def compact_chain_len(start, steps=6):
        p = start
        n = 0
        for _ in range(steps):
            if p + 8 > len(buf) or buf[p:p + 4] == SENTINEL:
                return n
            vc = is_valid_compact(p)
            if vc is None:
                return n
            p += 8
            n += 1
        return n

    while pos + 4 <= len(buf):
        if buf[pos:pos + 4] == SENTINEL:
            pos += 4
            # After the sentinel, two continuations are possible (normal
            # or compact-fill record form) - since the compact form's
            # header can accidentally look valid as a normal record (and
            # vice versa), we pick whichever mode gives a LONGER,
            # reliably continuing chain from here.
            #
            # LOOKAHEAD FIX (v2.21, found on Interf.dbi's EXCHANGE):
            # 6 steps is too short a lookahead - on EXCHANGE, both modes
            # validate for exactly 6 steps (a tie), so `>` picked normal
            # (the tie-break default) even though normal is WRONG here:
            # at 20+ steps, normal_len plateaus at 16 (it genuinely runs
            # out of room for its large declared K values near the end
            # of the buffer) while compact_len keeps climbing linearly
            # (200, 400, ... - i.e. compact is unambiguously the real
            # format). Since normal-mode records consume far more bytes
            # per step than the true 8-byte compact stride, choosing
            # normal here doesn't just fail at the very end - it
            # silently decodes WRONG content for every record in
            # between too (each one lands on a different, unintended
            # byte offset), which is invisible until the eventual
            # failure finally surfaces as a small reported "gap" near
            # the end of the run. 30 steps was enough to reveal the
            # divergence on this sample; kept well short of
            # GAP_SEARCH_WINDOW to stay cheap.
            # LOOKAHEAD FIX (v2.29, found on MIDGARD's TWD0002): 30 steps
            # is STILL sometimes too short - on TWD0002 (and likely the
            # rest of the TWD*/TWE*/TWH*/TWU* family), both modes
            # validate for EXACTLY 30 steps (a tie, broken by `>` in
            # favor of normal - wrong), continuing to tie even at 50
            # steps. Only past 50 does it resolve: normal_len plateaus
            # at 50 (genuinely runs out of room) while compact_len keeps
            # climbing past 500 - the identical "normal plateaus,
            # compact climbs" signature as the v2.21 EXCHANGE fix that
            # originally motivated extending this lookahead from 6 to
            # 30. Extended to 150 (comfortably past the 50-step
            # plateau seen here, cheap enough to keep doing on every
            # sentinel).
            normal_len = chain_len(pos, 150) if is_valid(pos) else 0
            compact_len = compact_chain_len(pos, 150)
            if compact_len > normal_len:
                while pos + 8 <= len(buf) and buf[pos:pos + 4] != SENTINEL:
                    vc = is_valid_compact(pos)
                    if vc is None:
                        break
                    K, off = vc
                    c1 = buf[pos + 1]
                    row = (c1 // 4) + 64 * (buf[pos + 2] % 32)
                    # DISCOVERY (this session): the 4 bytes at pos+4..+7
                    # are NOT "unknown" and this is NOT a flat color
                    # fill - they're a 32-bit little-endian ABSOLUTE
                    # POSITION into `buf`, from which K bytes must be
                    # COPIED (an LZ-style back-reference, structurally
                    # identical to the portrait codec's trailer Section2
                    # mechanism - see _apply_trailer_section2). Validated
                    # PIXEL-PERFECT (0 mismatched pixels out of 188160)
                    # against MIDGARD.DBI's TWD0001 oracle BMP, which was
                    # previously the textbook example of this defect
                    # (widespread white/light streaks through snow,
                    # trees, and mountains - the streaks were always
                    # this record type rendering as a wrong guessed flat
                    # color instead of the real, varied source pixels).
                    srcpos = (buf[pos+4] | (buf[pos+5] << 8) |
                              (buf[pos+6] << 16) | (buf[pos+7] << 24))
                    if row < H and off + K <= W and 0 <= srcpos and srcpos + K <= len(buf):
                        grid[row][off:off + K] = list(buf[srcpos:srcpos + K])
                    compact_used = True
                    pos += 8
            continue
        v = is_valid(pos)
        if v is None:
            # FIX (v2.28, MIDGARD's TWD*/TWE*/TWH*/TWU* family): before
            # falling through to gap-recovery, check whether the BASE
            # (byte0-only) K - ignoring the (c1&3)<<8 extension - gives a
            # real record here instead. Deliberately done ONLY at this
            # one call site (the main loop's primary position), NOT
            # inside is_valid() itself: an earlier attempt added the
            # fallback inside is_valid() directly, which also changed
            # every SPECULATIVE candidate check during gap-recovery's
            # brute-force search (chain_len, compact_chain_len, and the
            # up-to-3000-byte recovery scans all call is_valid() on many
            # candidate positions, not just real record starts) -
            # regressed badly (broke the previously-perfect TWU0001) for
            # exactly that reason. Keeping is_valid() itself strict/
            # unchanged everywhere else avoids that.
            c1b, c2b, c3b = buf[pos + 1], buf[pos + 2], buf[pos + 3]
            K_ext = buf[pos] | ((c1b & 3) << 8)
            if K_ext > W:
                K_base = buf[pos]
                off_base = 0
                if K_base < W:
                    off_base = c3b * 8 + c2b // 32
                base_ok = (K_base <= W and (K_base == W or 0 <= off_base <= W - K_base)
                           and pos + 4 + K_base <= len(buf))
                if base_ok:
                    rec_size_base = 4 * ((4 + K_base + 3) // 4)
                    if chain_len(pos + rec_size_base, 20) >= 15:
                        v = (K_base, off_base, rec_size_base)
        if v is None:
            if len(buf) - pos < 100:
                break
            # THIRD format ("raw row block"): for large, noisy/
            # incompressible texture bands (snow, lava), the stream
            # switches to a short [K=0,c1,c2,c3] marker, followed by
            # headerless raw pixel row(s). DISCOVERY (2026-06-24): this
            # is NOT a separate format - the marker follows the SAME
            # row/offset formula as normal records (`row=(c1//4)+64*
            # (c2%32)`, `off=c3*8+c2//32`), K=0 just signals that
            # headerless raw data follows, NOT K explicit pixels.
            # Validated on all three "capital" buildings (97-99% pixel
            # match, vs. the ~96-98% obtained with the earlier estimated/
            # heuristic offset). Two sub-patterns are observed:
            #  - ALTERNATING: a short raw row, then 1 normal record, then
            #    a raw row again, etc. (the next valid header falls on a
            #    nearby row: row_guess or row_guess+1, within a short -
            #    <400 byte - distance).
            #  - SINGLE BLOCK: one LARGER raw block spanning several
            #    rows, where the next valid header is further away, but
            #    its row is still >= row_guess (monotonically
            #    continuing) - in this case the MARKER's off applies to
            #    ALL affected rows (the available width for each row is
            #    `W-off`).
            X, Y, Z = buf[pos + 1], buf[pos + 2], buf[pos + 3]
            row_guess = (X // 4) + 64 * (Y % 32)
            off_guess = Z * 8 + Y // 32
            if not (0 <= row_guess < H and 0 <= off_guess < W):
                row_guess = None
            recov = None
            if row_guess is not None:
                for g in range(4, 400):
                    cand = pos + g
                    if cand + 4 > len(buf):
                        break
                    v2 = is_valid(cand)
                    if v2:
                        c1c, c2c = buf[cand + 1], buf[cand + 2]
                        rowc = (c1c // 4) + 64 * (c2c % 32)
                        if rowc in (row_guess, row_guess + 1):
                            recov = cand
                            break
            if recov is None and row_guess is not None:
                for g in range(1, GAP_SEARCH_WINDOW):
                    cand = pos + g
                    if buf[cand:cand + 4] == SENTINEL:
                        break
                    v2 = is_valid(cand)
                    if v2 and chain_len(cand, 5) >= 5:
                        c1c, c2c = buf[cand + 1], buf[cand + 2]
                        rowc = (c1c // 4) + 64 * (c2c % 32)
                        if rowc >= row_guess:
                            recov = cand
                            break
            if recov is not None:
                gap_len = recov - (pos + 4)
                avail_width = max(1, W - off_guess)
                nrows = (gap_len + avail_width - 1) // avail_width
                cur = pos + 4
                for r in range(nrows):
                    seg_end = min(cur + avail_width, recov)
                    rowbytes = buf[cur:seg_end]
                    target_row = row_guess + r
                    if target_row < H and rowbytes:
                        grid[target_row][off_guess:off_guess + len(rowbytes)] = list(rowbytes)
                    cur = seg_end
                compact_used = True
                gaps.append((pos, recov))
                pos = recov
                continue
            # DISCOVERY (2026-06-25): if no further valid record is found
            # because we're simply near the TRUE end of the buffer (no
            # more data to recover INTO), the remaining bytes are still
            # genuine, headerless raw pixel data for row_guess onward -
            # not garbage to discard. Apply them the same way as the
            # gap-filling branch above, then finish cleanly.
            if row_guess is not None and len(buf) - (pos + 4) <= GAP_SEARCH_WINDOW:
                avail_width = max(1, W - off_guess)
                cur = pos + 4
                r = 0
                while cur < len(buf):
                    seg_end = min(cur + avail_width, len(buf))
                    rowbytes = buf[cur:seg_end]
                    target_row = row_guess + r
                    if target_row < H and rowbytes:
                        grid[target_row][off_guess:off_guess + len(rowbytes)] = list(rowbytes)
                    cur = seg_end
                    r += 1
                compact_used = True
                pos = len(buf)
                break
            # Final, format-agnostic fallback: look for a definitely
            # reliable (5+ chain) continuation point, without a row
            # check - the area in between stays empty/transparent.
            recov = None
            for g in range(1, GAP_SEARCH_WINDOW):
                cand = pos + g
                if buf[cand:cand + 4] == SENTINEL:
                    recov = cand
                    break
                v2 = is_valid(cand)
                if v2 and chain_len(cand, 6) >= 5:
                    recov = cand
                    break
            if recov is None:
                break
            gaps.append((pos, recov))
            pos = recov
            continue
        K, off, rec_size = v
        c1, c2 = buf[pos + 1], buf[pos + 2]
        row = (c1 // 4) + 64 * (c2 % 32)
        if row < H and K > 0 and off + K <= W:
            pix = list(buf[pos + 4:pos + 4 + K])
            grid[row][off:off + K] = pix[:K]
        nrec += 1
        pos += rec_size

    unconsumed = len(buf) - pos
    status = {
        'records': nrec,
        'gaps': gaps,
        'gap_bytes': sum(b - a for a, b in gaps),
        'unconsumed_bytes': unconsumed,
        'clean': len(gaps) == 0 and unconsumed <= 16,
        'compact_used': compact_used,
    }
    return grid, W, H, status


# Name-prefixes (checked case-insensitively, anywhere in any file) whose
# enclosed index-0 regions are genuine negative space, not real content -
# see render_iso_image()'s `flat_transparent` parameter for the full
# reasoning and the in-game-confirmed examples behind each entry.
# Name-prefixes for genuine head/bust portraits (CF=MIDGARD, FH/FD/FN/
# FU/FE/FG=UNIT.DBI + some MIDGARD/Menus crossover, GP=new inserts) -
# these never have a real background margin, so they're rendered fully
# opaque (see render_iso_image's `force_opaque`). NOT the same list as
# classify_block_kind()'s `portrait_prefixes` (that one is broader/looser
# on purpose, for decode-ALGORITHM routing - this one is deliberately
# narrow, for the alpha decision, since it must exclude structurally-
# similar-sized but NOT-actually-a-portrait blocks like ICONS.DBI's
# CITYHU/CITYHE/CITYUN/ICNSY (which classify_block_kind() also calls
# 'portrait' via its structural fallback, but which DO have a real,
# legitimate margin that force_opaque would wrongly erase).
PORTRAIT_FORCE_OPAQUE_PREFIXES = ('CF', 'FH', 'FD', 'FN', 'FU', 'FE', 'FG', 'GP')

# MIDGARD.DBI's TWD/TWE/TWH/TWU "terrain scene" family (the iso_partial
# category - complete, full-canvas night-town/mountain backdrops) - same
# underlying reasoning as the portrait case above, just for a different
# kind of content: these are complete, standalone background images,
# never composited as a cutout over something else, so they never have
# a real transparent margin either. Found on TWU0002-0005: their night
# sky (painted mostly in the palette's black entry, with sparse bright
# star pixels) touches the canvas border on all sides, so flood-fill
# classified the ENTIRE sky as "background" and made it transparent
# (28.3% of the canvas on TWU0004) - confirmed wrong by the person
# (in-game, the sky is a solid dark backdrop, not a see-through hole).
SCENE_FORCE_OPAQUE_PREFIXES = ('TWD', 'TWE', 'TWH', 'TWU')


def _is_force_opaque_portrait(name):
    name = (name or '').upper()
    if re.match(r'^GP\d{3}(S00|L00)$', name):
        return True
    if any(name.startswith(pre) for pre in SCENE_FORCE_OPAQUE_PREFIXES):
        return True
    return any(name.startswith(pre) for pre in PORTRAIT_FORCE_OPAQUE_PREFIXES if pre != 'GP')


FLAT_TRANSPARENT_PREFIXES = (
    'ICDSP', 'ICESP', 'ICHSP', 'ICUSP',   # ICONS.DBI "spell sigil" icon families
    'GSAB',                                # MIDGARD.DBI hourglass/ability icons
    'BUILTT', 'BREIFING', 'STRAVIDE',      # Interf.dbi UI templates/backgrounds
    'SC2',                                 # Menus.dbi text-label buttons (letters have real holes - HOST's "O", etc.)
    'THIEF',                               # MIDGARD.DBI item icons (noose, hands) - confirmed by the person
    'ICNSY',                               # ICONS.DBI badge icons (the red-ringed circle was assumed solid - it isn't)
    'LOGO',                                # MIDGARD.DBI/Menus.dbi per-race logo emblems (LOGOD/E/H/U)
)

# Whole files where this also applies uniformly - see render_iso_image()'s
# docstring (TERRAIN.DBI's tile/object sprites never seem to need the
# enclosed-opaque exception).
FLAT_TRANSPARENT_FILES = ('TERRAIN.DBI',)


def _uses_flat_transparent(name, dbi_path):
    """Decide whether `name` (from `dbi_path`) should use the simple
    all-index-0-is-transparent rule instead of border-flood-fill - see
    FLAT_TRANSPARENT_PREFIXES/FLAT_TRANSPARENT_FILES above."""
    base = os.path.basename(dbi_path or '').upper()
    if base in FLAT_TRANSPARENT_FILES:
        return True
    name = (name or '').upper()
    return any(name.startswith(pre) for pre in FLAT_TRANSPARENT_PREFIXES)


def render_iso_image(grid, W, H, palette, flat_transparent=False, force_opaque=False):
    """Render a decoded ISO grid (0=transparent convention) to a final,
    save-ready image - decides per-PIXEL (not per-image) whether each
    index-0 (palette black) pixel is genuine empty background or real
    drawn content (v2.31 fix, replacing the v2.27 whole-image heuristic):

    Flood-fills from the canvas border across connected index-0 pixels.
    Anything that connected region REACHES is genuine background (the
    "outside" of whatever's drawn) and becomes transparent. Any index-0
    pixel NOT reachable from the border - enclosed by non-zero pixels -
    is real content (a dark window recess, shadow, roof tile, scattered
    black fur/hair) and stays opaque, in its own (black) color.

    v2.33 EXCEPTION (`flat_transparent=True`, set by the caller for
    specific name-families - see FLAT_TRANSPARENT_PREFIXES below): for
    some content, an "enclosed" index-0 region is NOT real content but
    genuine negative space that just happens not to touch the border -
    e.g. the open loop of a wax-seal/sigil icon or a letterform (the
    hole in an "O"), the gap between two adjacent tree crowns that
    happen to touch, or a UI template's designated "insert other
    content here" slot. For these, ALL index-0 pixels are treated as
    transparent, with no enclosed/border distinction at all (the
    simple, pre-v2.31 rule). Found by the person testing in-game and
    comparing several concrete cases: CAPITAL.DBI's VU01/VU02
    (architecture - keep the flood-fill split), Interf.dbi's
    BUILTT07/BUILTT11/BREIFING/STRAVIDE (UI templates - confirmed
    in-game to be fully transparent there), ICONS.DBI's
    ICESP/ICHSP/ICDSP/ICUSP "spell sigil" icon families, MIDGARD's
    GSAB hourglass icons, and Menus.dbi's SC2* text-label buttons
    (lacy/cutout/letterform designs - confirmed broken by the
    flood-fill rule), versus ICONS.DBI's CITYHU/CITYHE/ICNSY and the
    *BG background families (real architectural shading - keep the
    flood-fill split). TERRAIN.DBI is also fully `flat_transparent`
    (its tile/object sprites never seem to need the enclosed-opaque
    exception; only the tile diamonds' 4 corner-touches and the rare
    touching-object case were ever at stake, and both are handled
    correctly by treating all index-0 as transparent).

    v2.34 EXCEPTION (`force_opaque=True`, set by the caller for names
    matching PORTRAIT_FORCE_OPAQUE_PREFIXES - genuine head/bust
    portraits): the INVERSE problem turned up on UNIT.DBI's portraits (e.g. FU080S00) - a close-up face/bust never
    has a real background margin at all, but a stray dark pixel or two
    touching the literal canvas border (a hair lock, a collar edge) lets
    the flood-fill "drain" transparency from the border all the way
    into a much larger, genuinely-drawn dark region (hair, dark
    clothing) through a thin connected path - a moth-eaten look,
    visually confirmed on FU080S00 (10.7% of the canvas wrongly
    punched transparent). Since every real portrait checked has turned
    out to need ~100% opacity anyway (this is the same content category
    `render_iso_image` had no trouble with before flood-fill existed -
    see the v2.27 changelog), the fix for this category is simply to
    skip the border/enclosed distinction entirely and render fully
    opaque, exactly like the original (pre-v2.31) whole-image rule did.

    `flat_transparent` and `force_opaque` are mutually exclusive; if
    both are somehow passed True, `force_opaque` wins.

    Pure Python (no numpy, per this module's "standalone" design) -
    uses a deque-based BFS and flat bytearrays for the pixel buffers.

    Returns (image, bbox) - bbox is None only for a fully-empty block.
    """
    from PIL import Image
    from collections import deque

    is_bg = bytearray(W * H)  # 1 = reachable from the border (background)

    if force_opaque:
        pass  # is_bg stays all-zero - every pixel renders in its own color
    elif flat_transparent:
        for y in range(H):
            row = grid[y]
            base = y * W
            for x in range(W):
                if row[x] == 0:
                    is_bg[base + x] = 1
    else:
        visited = bytearray(W * H)
        q = deque()

        def idx(x, y):
            return y * W + x

        for x in range(W):
            for y in (0, H - 1):
                i = idx(x, y)
                if grid[y][x] == 0 and not visited[i]:
                    visited[i] = 1
                    q.append((x, y))
        for y in range(H):
            for x in (0, W - 1):
                i = idx(x, y)
                if grid[y][x] == 0 and not visited[i]:
                    visited[i] = 1
                    q.append((x, y))
        while q:
            x, y = q.popleft()
            is_bg[idx(x, y)] = 1
            if x > 0 and grid[y][x - 1] == 0 and not visited[idx(x - 1, y)]:
                visited[idx(x - 1, y)] = 1
                q.append((x - 1, y))
            if x < W - 1 and grid[y][x + 1] == 0 and not visited[idx(x + 1, y)]:
                visited[idx(x + 1, y)] = 1
                q.append((x + 1, y))
            if y > 0 and grid[y - 1][x] == 0 and not visited[idx(x, y - 1)]:
                visited[idx(x, y - 1)] = 1
                q.append((x, y - 1))
            if y < H - 1 and grid[y + 1][x] == 0 and not visited[idx(x, y + 1)]:
                visited[idx(x, y + 1)] = 1
                q.append((x, y + 1))

    img = Image.new('RGBA', (W, H))
    put = img.putpixel
    for y in range(H):
        row = grid[y]
        base = y * W
        for x in range(W):
            v = row[x]
            if v == 0 and is_bg[base + x]:
                put((x, y), (0, 0, 0, 0))
            else:
                r, gg, b = palette[v]
                put((x, y), (r, gg, b, 255))
    bbox = img.getbbox()
    if bbox is None:
        return img, bbox
    return img.crop(bbox), bbox


def iso_grid_to_image(grid, W, H, palette):
    """Convert a palette-index grid (0=transparent) into an RGBA Pillow image."""
    from PIL import Image
    img = Image.new('RGBA', (W, H))
    for y in range(H):
        row = grid[y]
        for x in range(W):
            idx = row[x]
            if idx == 0:
                img.putpixel((x, y), (0, 0, 0, 0))
            else:
                r, g, b = palette[idx]
                img.putpixel((x, y), (r, g, b, 255))
    return img


def encode_iso_graphic_stream(grid, W, H):
    """Encode a palette-index grid (H rows, W columns, 0=transparent) into
    the ISO.DBI-style, headerless (decompressed) record byte stream.

    The exact inverse of decode_iso_block(): for each row, finds the
    contiguous NON-transparent (non-0) runs, and builds a
    `[K, c1, c2, c3, <K bytes of pixel data>]` record for each (4-byte
    aligned), using the validated formulas:

        c1 = (row % 64) * 4
        wrap = row // 64
        off = the patch's starting column
        c3 = off // 8 ;  c2 = ((off % 8) << 5) | wrap

    (if the patch covers the FULL row, `K==W`, the offset is implicit 0 -
    in that case `c2=wrap, c3=0`, because the decoder does not read the
    offset when K>=W).

    Splits any run longer than 255 into multiple records (K is one byte).

    VALIDATED (2026-06-24): all 16 (non-"capital") reference images give
    EXACTLY 100.00%, "clean" results through the
    encode->compress->decompress->`decode_iso_block()` round trip.
    """
    out = bytearray()
    for row in range(H):
        rowdata = grid[row]
        x = 0
        runs = []
        while x < W:
            if rowdata[x] == 0:
                x += 1
                continue
            start = x
            while x < W and rowdata[x] != 0:
                x += 1
            runs.append((start, x - start))
        wrap = row // 64
        if wrap > 31:
            raise ValueError(f"Row ({row}) wrap value ({wrap}) is too large (max 31) - "
                              f"the image height (H={H}) exceeds the format's limit.")
        c1 = (row % 64) * 4
        for (off, length) in runs:
            pos = 0
            while pos < length:
                chunklen = min(length - pos, 255)
                chunk_off = off + pos
                if chunklen == W:
                    c2, c3 = wrap, 0
                else:
                    c3 = chunk_off // 8
                    c2 = ((chunk_off % 8) << 5) | wrap
                rec = bytes([chunklen, c1, c2, c3]) + bytes(rowdata[chunk_off:chunk_off + chunklen])
                rec += bytes((-len(rec)) % 4)
                out += rec
                pos += chunklen
    # REQUIRED trailing terminator (found 2026-06-25): every genuine ISO
    # graphic stream ends with the SENTINEL (\x00\x00\x00\x80) written
    # TWICE, included in hp_end. Our own decode_iso_block() tolerates its
    # absence (so encode->decode round trips looked "clean" without it),
    # but the real game engine apparently relies on it to know where the
    # image data ends - omitting it is the likely cause of the in-game
    # position-shift / spilling-row bug seen on isoreplace'd graphics.
    out += b'\x00\x00\x00\x80' * 2
    return bytes(out)


def build_mqrc_iso(compressed, W, H, bt, name, hp_end):
    """Assemble an MQRC block for an ISO-style graphic - a generalization
    of the portrait version of `build_mqrc()`: writes the W/H fields as
    2 BYTES (not 1), since ISO graphics can have a canvas size well above
    255. Same critical fields (sA-copy, flag=1) as in the portrait
    version."""
    if hp_end > 0xFFFF:
        raise ValueError(f"hp_end ({hp_end}) is too large for the 16-bit field (max 65535) - "
                          f"the image is too large/detailed for this format.")
    sA = 20 + len(compressed)
    hdr = bytearray(48)
    hdr[0:4] = b'MQRC'
    struct.pack_into('<I', hdr, 8, bt)
    struct.pack_into('<I', hdr, 12, sA)
    struct.pack_into('<I', hdr, 16, sA)
    struct.pack_into('<I', hdr, 20, 1)
    hdr[37] = hp_end & 0xFF
    hdr[38] = (hp_end >> 8) & 0xFF
    hdr[39] = 0x80   # REQUIRED - present as 0x80 in 776/777 sampled real ISO records (2026-06-25);
                     # build_mqrc_iso previously left this 0x00, which is the likely cause of the
                     # in-game position-shift + spilling-row bug seen on isoreplace'd graphics.
    hdr[44], hdr[45] = hdr[37], hdr[38]
    struct.pack_into('<H', hdr, 40, W)
    struct.pack_into('<H', hdr, 42, H)
    nb = name.encode('ascii')[:8]
    hdr[28:28 + len(nb)] = nb
    return bytes(hdr) + compressed


def load_iso_png(path, palette):
    """Load an RGBA PNG for ISO graphics encoding: returns a palette-index
    grid (0=transparent). Decides based on the alpha channel (alpha<128
    -> index 0), UNLIKE the portrait loader, which does not handle
    transparency - this is CRITICAL here, because the whole point of ISO
    graphics is background transparency."""
    from PIL import Image
    img = Image.open(path).convert('RGBA')
    W, H = img.size
    px = img.load()
    cache = {}

    def closest(rgb):
        if rgb in cache:
            return cache[rgb]
        best = (None, 1)
        for i, (r, g, b) in enumerate(palette):
            if i == 0:
                continue
            d = (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2
            if best[0] is None or d < best[0]:
                best = (d, i)
        cache[rgb] = best[1]
        return best[1]

    grid = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a >= 128:
                grid[y][x] = closest((r, g, b))
    return grid, W, H


def cmd_isoencode(img_path, dbi_path, name, overwrite=False):
    """EXPERIMENTAL: insert a completely NEW ISO-style graphic (e.g. into
    an ISO.DBI file) - uses the same infrastructure (name-index table +
    chain-TOC extension) as the UNIT.DBI portrait `cmd_insert()`, but with
    the ISO-compatible `encode_iso_graphic_stream()`/`build_mqrc_iso()`
    encoder. The `name` is given explicitly by the user (ISO object types
    use meaningful prefixes - e.g. `GUN`, `GSY`, `GLM`, `GIT`, `GRF` -
    not an automatically generated number)."""
    init_codes = load_init_codes()
    with open(dbi_path, 'rb') as f:
        orig_data = f.read()
    palette = _find_palette_in_dbi(orig_data)
    if palette is None:
        sys.exit(t('no_palette'))

    blocks = _scan_all_blocks(orig_data)
    used_names = {nm for _, _, nm in blocks}
    if name in used_names:
        sys.exit(t('iso_name_taken', name=name))
    used_bts = {bt for _, bt, _ in blocks}
    new_bt = max(used_bts) + 1

    print(t('loading_image', path=img_path))
    grid, W, H = load_iso_png(img_path, palette)
    print(t('iso_size', w=W, h=H))

    raw = encode_iso_graphic_stream(grid, W, H)
    print(t('iso_raw_stream', n=len(raw)))
    compressed = compress(raw, init_codes)
    print(t('iso_compressed', n=len(compressed)))
    mqrc = build_mqrc_iso(compressed, W, H, new_bt, name, hp_end=len(raw))

    print(t('extending_index', name=name))
    data_after_index = insert_into_name_index(orig_data, name, new_bt)

    toc_start, count, entries = read_dbi_toc(data_after_index)
    new_sA = struct.unpack_from('<I', mqrc, 12)[0]
    new_block_offset = toc_start

    old_toc_byte_len = (count + 1) * 16
    trailing = data_after_index[toc_start + old_toc_byte_len:]
    if trailing:
        print(t('iso_trailing_note', n=len(trailing), name=name))

    entries[count]['next_bt'] = new_bt
    entries[count]['next_sA'] = new_sA
    entries[count]['next_sA2'] = new_sA
    entries.append({'offset': new_block_offset, 'next_bt': 0, 'next_sA': 0, 'next_sA2': 0})
    entries[0]['offset'] = count + 1

    new_toc_byte_len = len(entries) * 16
    # A (rare) chain entry may point INTO the area after the TOC (e.g. if
    # there are real MQRC blocks there too, not just the preserved
    # "trailing" data's start) - these must also be shifted by the offset
    # introduced by the insertion+TOC-extension, otherwise they would
    # point to an invalid offset.
    trailing_shift = len(mqrc) + new_toc_byte_len - old_toc_byte_len
    for e in entries:
        if e['offset'] > toc_start:
            e['offset'] += trailing_shift

    toc_bytes = b''.join(
        struct.pack('<4I', e['offset'], e['next_bt'], e['next_sA'], e['next_sA2']) for e in entries
    )
    new_data = bytearray(data_after_index[:toc_start] + mqrc + toc_bytes + trailing)
    struct.pack_into('<I', new_data, 24, toc_start + len(mqrc))

    out_path = dbi_path if overwrite else dbi_path.replace('.DBI', '_mod.DBI').replace('.dbi', '_mod.dbi')
    if not overwrite and out_path == dbi_path:
        out_path = dbi_path + '.mod'
    if overwrite:
        _make_backup(dbi_path)
    with open(out_path, 'wb') as f:
        f.write(bytes(new_data))
    print(t('iso_saved', path=out_path, suffix=(t('overwrite_suffix') if overwrite else ''),
            old=len(orig_data), new=len(new_data)))

    idx_problems = verify_name_index(bytes(new_data))
    print(t('iso_name_index_check', result=(t('ok') if not idx_problems else idx_problems)))
    bad = verify_dbi_toc(bytes(new_data))
    print(t('iso_chain_toc_check', result=(t('ok') if not bad else t('suspicious_entries', n=len(bad)))))

    # round-trip validation: decode the newly inserted block back
    p = 0
    pp_new = None
    while True:
        fp = new_data.find(b'MQRC', p)
        if fp == -1:
            break
        if new_data[fp + 28:fp + 36].rstrip(b'\x00').decode('ascii', 'replace') == name:
            pp_new = fp
            break
        p = fp + 1
    if pp_new is not None:
        grid_v, gW, gH, status_v = decode_iso_block(bytes(new_data), pp_new, init_codes, palette)
        match = sum(1 for y in range(H) for x in range(W) if grid_v[y][x] == grid[y][x])
        ok = match == W * H and status_v['clean']
        print(t('iso_roundtrip', result=(t('roundtrip_ok') if ok else t('roundtrip_bad', pct=100*match/(W*H)))))
    print(t('iso_new_name', name=name))
    return name



def cmd_isoreplace(img_path, dbi_path, target_name, overwrite=False):
    """EXPERIMENTAL: replace an EXISTING ISO-style graphic block's image
    data, keeping its name and bt. Combines the size-fitting logic of
    the portrait `cmd_encode()`/`replace` (pad if it fits, resize the TOC
    if it doesn't) with the ISO-compatible encoder
    (`encode_iso_graphic_stream()`/`build_mqrc_iso()`).

    Unlike portrait replace, the new image does NOT need to match the
    original block's W/H exactly - each ISO graphic block stores its own
    canvas size, so a different-sized replacement is written with its
    own correct W/H header fields. (Whether the game's other logic
    assumes a fixed size for a given slot is unknown - if in doubt, keep
    the original dimensions.)
    """
    init_codes = load_init_codes()
    with open(dbi_path, 'rb') as f:
        orig_data = f.read()
    palette = _find_palette_in_dbi(orig_data)
    if palette is None:
        sys.exit(t('no_palette'))

    graphics = list_iso_graphics(orig_data)
    target = [g for g in graphics if g[1] == target_name]
    if not target:
        names = [g[1] for g in graphics]
        sys.exit(t('iso_no_graphic', name=target_name, names=names[:5]))
    pp, name, bt, old_W, old_H = target[0]
    old_sA = struct.unpack_from('<I', orig_data, pp + 12)[0]

    print(t('loading_image', path=img_path))
    grid, W, H = load_iso_png(img_path, palette)
    if (W, H) != (old_W, old_H):
        print(t('iso_size_with_original', w=W, h=H, ow=old_W, oh=old_H))
    else:
        print(t('iso_size', w=W, h=H))

    raw = encode_iso_graphic_stream(grid, W, H)
    print(t('iso_raw_stream', n=len(raw)))
    compressed = compress(raw, init_codes)
    print(t('iso_compressed', n=len(compressed)))

    orig_stream_len = old_sA - 20  # the original compressed stream's length
    needs_resize = len(compressed) > orig_stream_len
    if needs_resize:
        print(t('iso_resize_line1', n=len(compressed)))
        print(t('iso_resize_line2', name=target_name, n=orig_stream_len))
        print(t('iso_resize_mode'))
    else:
        pad_len = orig_stream_len - len(compressed)
        if pad_len > 0:
            compressed = compressed + bytes(pad_len)
            print(t('iso_padding', n=pad_len))

    mqrc = build_mqrc_iso(compressed, W, H, bt, name, hp_end=len(raw))
    old_size = 28 + old_sA
    new_size = len(mqrc)

    if needs_resize:
        new_data = resize_patch_toc(orig_data, pp, old_size, mqrc)
        bad = verify_dbi_toc(new_data)
        if bad:
            print(t('iso_toc_warning', n=len(bad)))
        else:
            print(t('toc_check_ok'))
    else:
        new_data = orig_data[:pp] + mqrc + orig_data[pp + old_size:]

    out_path = dbi_path if overwrite else dbi_path.replace('.DBI', '_mod.DBI').replace('.dbi', '_mod.dbi')
    if not overwrite and out_path == dbi_path:
        out_path = dbi_path + '.mod'
    if overwrite:
        _make_backup(dbi_path)
    with open(out_path, 'wb') as f:
        f.write(new_data)
    print(t('isor_saved', path=out_path, suffix=(t('overwrite_suffix') if overwrite else ''),
            sign=('+' if new_size >= old_size else ''), delta=new_size - old_size))

    idx_problems = verify_name_index(bytes(new_data))
    print(t('iso_name_index_check', result=(t('ok') if not idx_problems else idx_problems)))

    # round-trip validation
    p = 0
    pp_new = None
    while True:
        fp = new_data.find(b'MQRC', p)
        if fp == -1:
            break
        if new_data[fp + 28:fp + 36].rstrip(b'\x00').decode('ascii', 'replace') == name:
            pp_new = fp
            break
        p = fp + 1
    if pp_new is not None:
        grid_v, gW, gH, status_v = decode_iso_block(bytes(new_data), pp_new, init_codes, palette)
        match = sum(1 for y in range(H) for x in range(W) if grid_v[y][x] == grid[y][x])
        ok = match == W * H and status_v['clean']
        print(t('iso_roundtrip', result=(t('roundtrip_ok') if ok else t('roundtrip_bad', pct=100*match/(W*H)))))



def cmd_list(dbi_path):
    """UNIFIED (v2.12): lists every recognized block in ANY .DBI file,
    auto-classified as 'portrait' or 'iso'/'iso_partial' - no more
    separate list-vs-isolist distinction. See classify_block_kind()."""
    init_codes = load_init_codes()
    with open(dbi_path, 'rb') as f:
        data = f.read()
    palette = _find_palette_in_dbi(data)
    blocks = scan_dbi_blocks(data, init_codes=init_codes, palette=palette)
    print(t('list_header', name=t('col_name'), kind=t('col_kind'), size=t('col_size'), position=t('col_position')))
    print('-' * 50)
    for b in blocks:
        print(f"{b['name']:<12} {b['kind']:>12}  {b['W']}x{b['H']:<6}  @{b['pp']:#08x}")
    from collections import Counter
    counts = Counter(b['kind'] for b in blocks)
    summary = ', '.join(f"{v} {k}" for k, v in counts.items())
    print(t('list_total', n=len(blocks), summary=summary))


def cmd_decode(dbi_path, out_dir, name_filter=None):
    """UNIFIED (v2.12): exports EVERY recognized block in ANY .DBI file
    to PNG, auto-detecting portrait vs. ISO-style graphics per block
    (see classify_block_kind() / decode_any_block()) - one command
    handles mixed-category files like MIDGARD.DBI transparently."""
    init_codes = load_init_codes()
    with open(dbi_path, 'rb') as f:
        data = f.read()
    palette = _find_palette_in_dbi(data)
    if palette is None:
        sys.exit(t('no_palette'))
    blocks = scan_dbi_blocks(data, init_codes=init_codes, palette=palette)
    if name_filter:
        blocks = [b for b in blocks if b['name'].startswith(name_filter)]
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    n_clean = 0
    n_partial = 0
    n_error = 0
    for b in blocks:
        try:
            res = decode_any_block(data, b['pp'], init_codes, palette,
                                    kind=b['kind'], name=b['name'], W=b['W'], H=b['H'])
            out_path = os.path.join(out_dir, f"{res['name']}.png")
            if 'rows' in res:
                # Portrait result: full WxH grid, no cropping.
                save_portrait_png(res['rows'], palette, res['W'], res['H'], out_path)
                print(t('decode_line_portrait', name=res['name'], w=res['W'], h=res['H']))
                n_clean += 1
            else:
                out_img, bbox = render_iso_image(
                    res['grid'], res['W'], res['H'], palette,
                    force_opaque=_is_force_opaque_portrait(res['name']),
                    flat_transparent=_uses_flat_transparent(res['name'], dbi_path))
                out_img.save(out_path)
                status = res['status']
                tag = t('ok') if status['clean'] else \
                    t('decode_tag_partial', gb=status['gap_bytes'], u=status['unconsumed_bytes'])
                kind_tag = res['kind'] if res['kind'] != 'iso' else 'iso'
                print(t('decode_line_iso', name=res['name'], w=res['W'], h=res['H'],
                        cw=out_img.size[0], ch=out_img.size[1], kind=kind_tag, tag=tag))
                if status['clean']:
                    n_clean += 1
                else:
                    n_partial += 1
        except Exception as e:
            print(t('decode_error_line', name=b['name'], e=e))
            n_error += 1
    print(t('decode_summary', n=len(blocks), out_dir=out_dir, clean=n_clean, partial=n_partial, error=n_error))
    return {'total': len(blocks), 'clean': n_clean, 'partial': n_partial, 'error': n_error}


def cmd_decode_all(search_dir='.', out_base_dir=None):
    """NEW (v2.20): finds EVERY .DBI file in `search_dir` (case-
    insensitive, non-recursive) and decodes each one into its own
    output folder named after the file (e.g. 'MIDGARD.DBI' ->
    './MIDGARD/'), using the same unified, auto-detecting decoder as
    `decode`. Meant to speed up the "change the codec, re-decode
    everything, eyeball the results for new defects" loop during active
    development - one command instead of one `decode` call per file.

    `out_base_dir` defaults to `search_dir` itself (so e.g. running this
    from the folder that has ISO.DBI/UNIT.DBI/MIDGARD.DBI in it creates
    ISO/, UNIT/, MIDGARD/ as siblings of those files) - pass a different
    path to collect all the output folders somewhere else instead.

    A single file's failure (no palette found, unexpected exception)
    does NOT abort the rest of the batch - it's reported and skipped.
    """
    if out_base_dir is None:
        out_base_dir = search_dir
    try:
        dbi_files = sorted(p for p in os.listdir(search_dir) if p.lower().endswith('.dbi'))
    except OSError as e:
        sys.exit(t('decodeall_dir_error', dir=search_dir, e=e))
    if not dbi_files:
        print(t('decodeall_none_found', dir=search_dir))
        return

    print(t('decodeall_found', n=len(dbi_files), dir=search_dir, names=', '.join(dbi_files)))
    results = []
    for fname in dbi_files:
        base = os.path.splitext(fname)[0]
        out_dir = os.path.join(out_base_dir, base)
        full_path = os.path.join(search_dir, fname)
        print(t('decodeall_processing', fname=fname, out_dir=out_dir))
        try:
            summary = cmd_decode(full_path, out_dir)
        except SystemExit as e:
            print(t('decodeall_skipped', e=e))
            summary = None
        except Exception as e:
            print(t('decodeall_skipped_unexpected', e=e))
            summary = None
        results.append((fname, out_dir, summary))
        print()

    print("=" * 64)
    print(t('decodeall_summary_title'))
    print("=" * 64)
    for fname, out_dir, summary in results:
        if summary is None:
            print(t('decodeall_summary_skipped_line', fname=fname, out_dir=out_dir))
        else:
            print(t('decodeall_summary_line', fname=fname, out_dir=out_dir, total=summary['total'],
                    clean=summary['clean'], partial=summary['partial'], error=summary['error']))


def read_dbi_toc(data, header_toc_ptr_offset=24):
    """Read the file's trailing absolute-offset TOC.
    Returns: (toc_start, count, entries), where entries[0] is the header
    row (its offset field=count, not a real offset), entries[1..count]
    are the real entries: {'off','offset','next_bt','next_sA','next_sA2'}.
    """
    toc_start = struct.unpack_from('<I', data, header_toc_ptr_offset)[0]
    count = struct.unpack_from('<I', data, toc_start)[0]
    n = count + 1
    vals = struct.unpack_from('<%dI' % (n * 4), data, toc_start)
    entries = []
    for i in range(0, n * 4, 4):
        entries.append({'off': toc_start + i * 4, 'offset': vals[i],
                         'next_bt': vals[i + 1], 'next_sA': vals[i + 2], 'next_sA2': vals[i + 3]})
    return toc_start, count, entries


def resize_patch_toc(orig_data, pp, old_size, mqrc, header_toc_ptr_offset=24):
    """Replace an MQRC block with content of a DIFFERENT size (even
    longer), consistently updating the file's trailing TOC (and the
    global header's TOC pointer). Validated: the offset of every block
    after the target block shifts by the size difference, the preceding
    TOC entry's next_sA cache field is updated, and the TOC's own
    position (and the global pointer to it) correctly follows the file's
    size change.

    POSITION-AWARE (v2.17): a block being resized can be tracked by a
    chain-TOC entry REGARDLESS of whether it sits before or after the
    TOC array's own physical position in the file (confirmed on ISO.DBI:
    a second, large name-index-style table sits AFTER the TOC, yet is
    still tracked by one of its entries) - so the search for a matching
    entry (by `offset`) and the "shift any entry whose offset is past
    pp" step always run, unconditionally, same as before. The ONE thing
    that must be conditional is the TOC array's OWN position: the global
    TOC pointer only needs to change if `pp` is BEFORE toc_start (data
    was inserted/removed ahead of the TOC, so the TOC itself physically
    moved) - resizing something AFTER toc_start never moves the TOC
    array itself. Treating that as unconditional (the pre-v2.17
    behavior, inherited from when this function only ever needed to
    handle blocks before the TOC) corrupted the global TOC pointer when
    used on a block after it - confirmed by reproducing the corruption
    (read_dbi_toc started reading garbage) before this fix.
    """
    new_size = len(mqrc)
    size_diff = new_size - old_size
    toc_start, count, entries = read_dbi_toc(orig_data, header_toc_ptr_offset)
    matches = [i for i in range(1, len(entries)) if entries[i]['offset'] == pp]
    if len(matches) > 1:
        raise ValueError(f"Cannot unambiguously find the block in the TOC (pp={pp}, matches={matches})")
    # In some files (e.g. ISO.DBI) the block being modified (typically the
    # starting name-index table) is NOT directly tracked in the
    # chain-TOC (there's no entry pointing to it) - in that case step 3
    # (updating the "previous" entry's cache) is simply skipped; the rest
    # (shifting later offsets, and the TOC pointer if applicable) is
    # still valid and necessary regardless.
    k = matches[0] if matches else None

    new_data = bytearray(orig_data[:pp] + mqrc + orig_data[pp + old_size:])

    # We always read the new sA back from the freshly written block's OWN
    # header (rather than computing it from a separate formula), to avoid
    # the risk of drift.
    new_sA = struct.unpack_from('<I', new_data, pp + 12)[0]

    # 1. global TOC pointer in the file header - ONLY if the TOC array
    #    itself sits AFTER pp (otherwise its position is unaffected).
    if pp < toc_start:
        old_ptr = struct.unpack_from('<I', new_data, header_toc_ptr_offset)[0]
        struct.pack_into('<I', new_data, header_toc_ptr_offset, old_ptr + size_diff)

    # 2. every TOC entry's offset that pointed AFTER the modified block
    #    (unconditional - entries can point anywhere in the file,
    #    independent of where the TOC array itself happens to sit)
    for i in range(1, len(entries)):
        e = entries[i]
        phys_pos = e['off'] + size_diff if pp < toc_start else e['off']
        if e['offset'] > pp:
            struct.pack_into('<I', new_data, phys_pos, e['offset'] + size_diff)

    # 3. the preceding (in array order) entry's next_sA/next_sA2 cache
    #    - only if the block is actually tracked in the chain (see above)
    if k is not None:
        prev = entries[k - 1]
        prev_phys = prev['off'] + size_diff if pp < toc_start else prev['off']
        struct.pack_into('<I', new_data, prev_phys + 8, new_sA)
        struct.pack_into('<I', new_data, prev_phys + 12, new_sA)

    return bytes(new_data)


def verify_dbi_toc(data, header_toc_ptr_offset=24):
    """Diagnostic check: does every TOC entry's offset point to a real
    MQRC block, and do the next_bt/next_sA cache fields match the actual
    next block's data? Returns the list of bad entries.
    """
    toc_start, count, entries = read_dbi_toc(data, header_toc_ptr_offset)
    positions = set(m.start() for m in re.finditer(b'MQRC', data))
    bad = []
    for i in range(1, len(entries)):
        e = entries[i]
        if e['offset'] not in positions:
            bad.append(('bad_offset', i, e))
            continue
        bt = struct.unpack_from('<I', data, e['offset'] + 8)[0]
        sA = struct.unpack_from('<I', data, e['offset'] + 12)[0]
        prev = entries[i - 1]
        if prev['next_bt'] != bt or prev['next_sA'] != sA or prev['next_sA2'] != sA:
            bad.append(('bad_link', i, prev, bt, sA))
    return bad


def _scan_all_blocks(data):
    """Collect (bt, name) pairs for all MQRC blocks in the file."""
    out = []
    p = 0
    while True:
        pp = data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', data, pp + 8)[0]
        name = data[pp + 28:pp + 36].rstrip(b'\x00').decode('ascii', 'replace')
        out.append((pp, bt, name))
        p = pp + 1
    return out


def find_all_name_index_blocks(data):
    """Systematic, structure-based scan for EVERY 'sorted 16-byte
    name(8)+pad(4)+value(4)' table block in the file - NOT just the one
    at the fixed pp=28 position right after the global header.

    DISCOVERY (v2.17): ISO.DBI (and presumably other large, multi-
    category files) has TWO such tables, not one - confirmed on
    ISO.DBI: one at pp=28 (own bt happens to be 956, not the "bt=3"
    convention seen elsewhere) with 933 entries, and a SEPARATE, larger
    one elsewhere in the file (bt=3, 936 entries originally). Both
    store the exact same (name -> real bt) mapping for every name they
    share - validated against several real blocks' own bt fields. The
    previous insert_into_name_index() only knew about the pp=28 table,
    so a newly inserted name (e.g. a new 'capital' image, GCAT0018)
    would be missing from the SECOND table - which is what the game
    actually seemed to consult, going by the in-game "Invalid value...
    in field IMGID" error this caused. UNIT.DBI-style files with only
    one table are unaffected (this just finds the one table they have).

    Detection is purely structural (no bt/name assumptions): a block
    qualifies if its body length is a multiple of 16, has at least 10
    entries, every entry's first 8 bytes are printable ASCII, and the
    list of (8-byte, NUL-stripped) names is already alphabetically
    sorted - real pixel/compressed data essentially never satisfies
    this by chance.

    Returns a list of pp positions (ascending).
    """
    found = []
    p = 0
    while True:
        pp = data.find(b'MQRC', p)
        if pp == -1:
            break
        header = data[pp:pp + 28]
        sA = struct.unpack_from('<I', header, 12)[0]
        sA2 = struct.unpack_from('<I', header, 16)[0]
        real_sA = sA if sA != 0 else sA2
        if real_sA and real_sA % 16 == 0:
            n = real_sA // 16
            body_start = pp + 28
            if n >= 10 and body_start + n * 16 <= len(data):
                names = []
                ok = True
                for i in range(n):
                    o = body_start + i * 16
                    nb = data[o:o + 8]
                    stripped = nb.rstrip(b'\x00')
                    if not all(32 <= c < 127 for c in stripped):
                        ok = False
                        break
                    names.append(stripped)
                if ok and names == sorted(names):
                    found.append(pp)
        p = pp + 1
    return found


def read_name_index_block(data, pp=28):
    """Read the NAME->bt index table at the given position `pp` (an
    MQRC block, defaults to the fixed pp=28 right after the global
    header for backward compatibility - but see find_all_name_index_blocks
    for files that have more than one such table, e.g. ISO.DBI).

    This is a SEPARATE MQRC block (typically bt=3, per our experimental
    findings), whose body consists of 16-byte entries: [8-byte name]
    [4 zero bytes][4-byte bt (uint32 LE)], SORTED ALPHABETICALLY BY NAME.
    The engine presumably resolves a portrait name to a bt through this
    (a sorted structure suitable for binary search) - this is INDEPENDENT
    of the trailing chain-TOC, which is handled by
    resize_patch_toc/read_dbi_toc.

    Returns: (pp, header (28 raw bytes), bt, flag, old_sA, entries, is_raw),
    """
    if data[pp:pp + 4] != b'MQRC':
        raise ValueError(f"Not an MQRC block at position pp={pp} - the file format differs from expected.")
    header = bytes(data[pp:pp + 28])
    bt = struct.unpack_from('<I', header, 8)[0]
    sA = struct.unpack_from('<I', header, 12)[0]
    sA2 = struct.unpack_from('<I', header, 16)[0]
    flag = struct.unpack_from('<I', header, 20)[0]
    is_raw = False
    if sA != sA2:
        # In some files (e.g. ISO.DBI) the name-index table is stored as
        # a LARGE, RAW (uncompressed) block: in that case sA=0, and the
        # real length is in sA2 (the same convention as for other large,
        # raw ISO blocks). We handle this, but elsewhere (sA!=0 AND
        # sA!=sA2) we still raise an error, because that really would be
        # unexpected.
        if sA != 0:
            raise ValueError("The index block's sA and sA-copy fields do not match - unexpected format.")
        sA = sA2
        is_raw = True
    if sA % 16 != 0:
        raise ValueError(f"The index block's size ({sA}) is not a multiple of 16 - not the expected 16-byte entry format.")
    body_start = pp + 28
    n = sA // 16
    entries = []
    for i in range(n):
        o = body_start + i * 16
        name = data[o:o + 8].rstrip(b'\x00').decode('ascii', 'replace')
        ebt = struct.unpack_from('<I', data, o + 12)[0]
        entries.append((name, ebt))
    return pp, header, bt, flag, sA, entries, is_raw


def build_name_index_block(header, bt, flag, entries_sorted, is_raw=False):
    """Assemble a new index-block byte sequence from the (name,bt) list.
    entries_sorted: an already alphabetically sorted [(name, bt), ...]
    list. If is_raw=True, preserves the original "raw" convention (sA=0,
    sA-copy=real length) - see the note in read_name_index_block."""
    new_sA = len(entries_sorted) * 16
    new_header = bytearray(header)
    struct.pack_into('<I', new_header, 8, bt)
    struct.pack_into('<I', new_header, 12, 0 if is_raw else new_sA)
    struct.pack_into('<I', new_header, 16, new_sA)
    struct.pack_into('<I', new_header, 20, flag)
    body = bytearray()
    for name, ebt in entries_sorted:
        nb = name.encode('ascii')[:8].ljust(8, b'\x00')
        body += nb + bytes(4) + struct.pack('<I', ebt)
    return bytes(new_header) + bytes(body)


def insert_into_name_index(orig_data, new_name, new_bt):
    """Inserts the (new_name, new_bt) entry into EVERY name-index table
    found in the file (see find_all_name_index_blocks - most files have
    just one, at pp=28, but e.g. ISO.DBI has two), each at its own
    correct alphabetical position, consistently shifting/updating the
    rest of the file (+16 bytes per table) via resize_patch_toc.

    Idempotent per table: a table that already contains `new_name` is
    left untouched (so calling this again after a partial/previous
    insert won't create a duplicate entry or raise).

    Returns the new, complete file byte sequence.
    """
    data = orig_data
    table_positions = find_all_name_index_blocks(data)
    if not table_positions:
        raise ValueError("No name-index table found in the file.")

    updated_any = False
    for _ in range(len(table_positions)):
        # Re-scan fresh each time: an earlier insertion in this loop may
        # have shifted every later byte offset in the file by +16.
        table_positions = find_all_name_index_blocks(data)
        target_pp = None
        for pp in sorted(table_positions):
            _, _, _, _, _, entries, _ = read_name_index_block(data, pp)
            if new_name not in {nm for nm, _ in entries}:
                target_pp = pp
                break
        if target_pp is None:
            break  # every table already has it - nothing left to do
        pp, header, bt, flag, old_sA, entries, is_raw = read_name_index_block(data, target_pp)
        new_entries = sorted(entries + [(new_name, new_bt)], key=lambda e: e[0])
        new_block = build_name_index_block(header, bt, flag, new_entries, is_raw)
        old_size = 28 + old_sA
        data = resize_patch_toc(data, pp, old_size, new_block)
        updated_any = True

    if not updated_any:
        raise ValueError(f"The name '{new_name}' is already present in every name-index table in the file.")
    return data


def verify_name_index(data):
    """Diagnostics: for EVERY name-index table found in the file (see
    find_all_name_index_blocks), checks
    (1) is sorted alphabetically (no ordering errors),
    (2) has no duplicate names,
    (3) every entry's bt matches the real block's actual bt,
    (4) every entry has a real MQRC block in the file;
    and additionally
    (5) flags any name present in one table but not another (informational
    - on the one file checked so far with two tables, a handful of names
    were already only in one of the two in the ORIGINAL, unmodified
    file, so this is reported but not treated as inherently an error).
    Returns the list of problems (empty list = OK)."""
    table_positions = find_all_name_index_blocks(data)
    problems = []
    if not table_positions:
        return [('no_name_index_table',)]

    real = {}
    p = 0
    while True:
        rp = data.find(b'MQRC', p)
        if rp == -1:
            break
        rbt = struct.unpack_from('<I', data, rp + 8)[0]
        rname = data[rp + 28:rp + 36].rstrip(b'\x00').decode('ascii', 'replace')
        real[rname] = rbt
        p = rp + 1

    all_name_sets = {}
    for pp in sorted(table_positions):
        _, _, _, _, _, entries, _ = read_name_index_block(data, pp)
        names_seen = set()
        for i, (name, ebt) in enumerate(entries):
            if name in names_seen:
                problems.append(('duplicate_name', pp, i, name))
            names_seen.add(name)
            if i > 0 and entries[i - 1][0] >= name:
                problems.append(('sort_order', pp, i, entries[i - 1][0], name))
            if name not in real:
                problems.append(('missing_block', pp, i, name))
            elif real[name] != ebt:
                problems.append(('bt_mismatch', pp, i, name, ebt, real[name]))
        all_name_sets[pp] = names_seen

    if len(all_name_sets) > 1:
        positions = sorted(all_name_sets)
        union = set().union(*all_name_sets.values())
        for pp in positions:
            missing = union - all_name_sets[pp]
            if missing:
                problems.append(('table_missing_names', pp, sorted(missing)))
    return problems


def _generate_new_name_and_bt(data, W, H, prefix='GP', forced_idx=None):
    """Generate a collision-free new name (e.g. 'GP004S00') and new bt
    value.
    If forced_idx is given, tries to use that index (stops with an error
    if the resulting name is already taken - this is intentional, so that
    experimental tests don't silently drift to a different index)."""
    suffix = 'S00' if W == 55 else ('L00' if W == 115 else None)
    if suffix is None:
        sys.exit(t('insert_bad_size', w=W, h=H))

    blocks = _scan_all_blocks(data)
    used_names = {nm for _, _, nm in blocks}
    used_bts = {bt for _, bt, _ in blocks}

    if forced_idx is not None:
        name = f"{prefix}{forced_idx:03d}{suffix}"
        if name in used_names:
            sys.exit(t('insert_name_taken', name=name))
    else:
        idx = 1
        pattern = re.compile(r'^' + re.escape(prefix) + r'(\d{3})' + re.escape(suffix) + r'$')
        used_idx = [int(m.group(1)) for _, _, nm in blocks if (m := pattern.match(nm))]
        if used_idx:
            idx = max(used_idx) + 1
        name = f"{prefix}{idx:03d}{suffix}"
        while name in used_names:  # extra safety loop, in case it still collides somehow
            idx += 1
            name = f"{prefix}{idx:03d}{suffix}"

    new_bt = max(used_bts) + 1
    return name, new_bt


def _make_backup(dbi_path):
    """Rotating .bak backup before overwrite (ow) mode.
    Keeps only ONE level of .bak (always the state right before the most
    recent overwrite) - it doesn't accumulate, but there's always one
    step back available."""
    bak_path = dbi_path + '.bak'
    shutil.copyfile(dbi_path, bak_path)
    return bak_path


def cmd_insert(img_path, dbi_path, prefix='GP', forced_idx=None, overwrite=False):
    """Insert a completely NEW portrait at the end of the file (AFTER the
    existing blocks, before the TOC), with an automatically generated
    name and bt, with the appropriate extension of the trailing TOC and
    the starting name-index table.

    IMPORTANT LIMITATION: this only guarantees that the DBI file remains
    internally consistent (the engine can read through the file without
    corruption). Whether the game actually USES this new portrait
    somewhere (e.g. whether a unit definition references it by name) is
    NOT guaranteed by this function - a separate, DBI-external reference
    must be set up for that.

    With overwrite=True, overwrites the ORIGINAL dbi_path (after making a
    rotating .bak backup of it first), so you don't need to juggle output
    filenames when inserting several images one after another.
    """
    init_codes = load_init_codes()
    with open(dbi_path, 'rb') as f:
        orig_data = f.read()

    # Global palette: the last bt==2 (palette) block in the file
    palette = None
    p = 0
    while True:
        pp = orig_data.find(b'MQRC', p)
        if pp == -1:
            break
        bt = struct.unpack_from('<I', orig_data, pp + 8)[0]
        if bt == 2:
            palette = [(orig_data[pp + 28 + i * 4 + 2], orig_data[pp + 28 + i * 4 + 1], orig_data[pp + 28 + i * 4])
                       for i in range(256)]
        p = pp + 1
    if palette is None:
        sys.exit(t('no_palette'))

    print(t('loading_image', path=img_path))
    rows, W, H = load_portrait_png(img_path, palette)
    if H != 67:
        sys.exit(t('insert_size_error', h=H))

    name, new_bt = _generate_new_name_and_bt(orig_data, W, H, prefix, forced_idx)
    print(t('insert_generated_name', name=name, bt=new_bt))

    print(t('compressing', w=W, h=H))
    buf, hp_end = make_hist_buffer(rows, W, H)
    compressed = compress(buf, init_codes)
    mqrc = build_mqrc(compressed, W, H, new_bt, name, hp_end)

    # Step 1 (NEW in v2.9): extend the starting NAME-INDEX table at the
    # appropriate alphabetical position - this is the name->bt resolution
    # structure (presumably) used by the engine, INDEPENDENT of the
    # chain-TOC. The lack of this was the reason why the v2.8 insert was
    # consistent at the file level, but the game still didn't recognize
    # the new portrait.
    print(t('extending_index', name=name))
    data_after_index = insert_into_name_index(orig_data, name, new_bt)
    print(t('insert_index_followup'))

    # Step 2: append the NEW portrait block to the end of the (already
    # index-extended) file, with the corresponding extension of the
    # chain-TOC - same logic as in v2.8, just now working on the updated
    # `data_after_index`.
    toc_start, count, entries = read_dbi_toc(data_after_index)
    new_sA = struct.unpack_from('<I', mqrc, 12)[0]
    new_block_offset = toc_start  # the new block starts exactly where the old TOC was

    entries[count]['next_bt'] = new_bt
    entries[count]['next_sA'] = new_sA
    entries[count]['next_sA2'] = new_sA

    new_entry = {'offset': new_block_offset, 'next_bt': 0, 'next_sA': 0, 'next_sA2': 0}
    entries.append(new_entry)
    entries[0]['offset'] = count + 1  # the header row's "offset" field = entry count

    toc_bytes = b''.join(
        struct.pack('<4I', e['offset'], e['next_bt'], e['next_sA'], e['next_sA2']) for e in entries
    )

    new_data = bytearray(data_after_index[:toc_start] + mqrc + toc_bytes)
    struct.pack_into('<I', new_data, 24, toc_start + len(mqrc))  # global TOC pointer

    out_path = dbi_path if overwrite else dbi_path.replace('.DBI', '_mod.DBI').replace('.dbi', '_mod.dbi')
    if not overwrite and out_path == dbi_path:
        out_path = dbi_path + '.mod'
    if overwrite:
        _make_backup(dbi_path)
    with open(out_path, 'wb') as f:
        f.write(bytes(new_data))
    print(t('insert_saved', path=out_path, suffix=(t('overwrite_suffix') if overwrite else ''),
            old=len(orig_data), new=len(new_data), delta=len(new_data)-len(orig_data)))

    bad = verify_dbi_toc(bytes(new_data))
    bad_new = [b for b in bad if not (b[0] == 'bad_link' and b[2].get('next_bt') == 197)]
    print(t('insert_chain_toc_check', result=(t('ok') if not bad_new else t('suspicious_entries', n=len(bad_new)))))

    idx_problems_final = verify_name_index(bytes(new_data))
    print(t('insert_name_index_check_final', result=(t('ok') if not idx_problems_final else idx_problems_final)))

    hist_v, hp_v = decompress(compressed, init_codes, hp_end)
    rows_v, _ = _rebuild_rows_v2_with_patches(hist_v, W, H, hp_v)
    ok = all(bytes(rows_v[r]) == bytes(rows[r][:W]) for r in range(H))
    print(t('pixel_match', result=(t('pixel_match_ok') if ok else t('pixel_match_err'))))
    print(t('insert_new_name', name=name))
    return name


def cmd_encode(img_path, dbi_path, target_name, overwrite=False):
    """Replace an EXISTING portrait-style block's image data, keeping its
    name/bt. UNIFIED (v2.16): the target block is now found via the
    universal scanner (scan_dbi_blocks/classify_block_kind), not the
    UNIT.DBI-specific read_portraits() (which required bt>=164 - MIDGARD's
    CF*/FH* portraits use bt values like 52/53/91 and were invisible to
    'replace' before this). Works on any .DBI file with portrait-style
    (W in (55,115)) blocks."""
    init_codes=load_init_codes()
    with open(dbi_path, 'rb') as f:
        orig_data = f.read()
    palette = _find_palette_in_dbi(orig_data)
    if palette is None:
        sys.exit(t('no_palette'))

    blocks = scan_dbi_blocks(orig_data, init_codes=init_codes, palette=palette)
    target = [b for b in blocks if b['name'].startswith(target_name) and b['kind'] == 'portrait']
    if not target:
        names = [b['name'] for b in blocks if b['kind'] == 'portrait']
        sys.exit(t('encode_no_portrait', name=target_name, names=names[:5]))
    pp = target[0]['pp']
    bt = struct.unpack_from('<I', orig_data, pp + 8)[0]
    name = target[0]['name']
    W, H = target[0]['W'], target[0]['H']
    sA = struct.unpack_from('<I', orig_data, pp + 12)[0]
    tgt = {'pp': pp, 'bt': bt, 'name': name, 'W': W, 'H': H, 'sA': sA, 'palette': palette}

    # Load image
    print(t('loading_image', path=img_path))
    rows,W2,H2=load_portrait_png(img_path, tgt['palette'])

    if W2!=tgt['W'] or H2!=tgt['H']:
        sys.exit(t('encode_size_error', w=W2, h=H2, tw=tgt['W'], th=tgt['H']))
    W, H = W2, H2

    # Compress
    print(t('compressing', w=W, h=H))
    buf,hp_end=make_hist_buffer(rows,W,H)
    compressed=compress(buf,init_codes)
    
    # Size check: the new stream's length decides which path is needed.
    orig_stream_len = tgt['sA'] - 20  # the original compressed stream's length
    needs_resize = len(compressed) > orig_stream_len

    if needs_resize:
        print(t('encode_resize_line1', n=len(compressed)))
        print(t('encode_resize_line2', name=target_name, n=orig_stream_len))
        print(t('encode_resize_line3'))
        print(t('encode_resize_line4'))
    else:
        # PADDING (2026-06-19): if the new stream is SHORTER (or equal), we
        # fill the gap with 0x00 bytes at the END of the compressed data,
        # so that the block size and the TOC offsets don't change at all
        # (the simplest, risk-free case).
        pad_len = orig_stream_len - len(compressed)
        if pad_len > 0:
            compressed = compressed + bytes(pad_len)
            print(t('encode_padding', n=pad_len))

    mqrc=build_mqrc(compressed,W,H,tgt['bt'],tgt['name'],hp_end)
    print(t('encode_orig_stream', old=tgt['sA']-20, new=len(compressed)))

    # Modify the DBI: replace the original MQRC block
    pp=tgt['pp']
    old_size=28+tgt['sA']  # the original block's size
    new_size=len(mqrc)

    if needs_resize:
        new_data = resize_patch_toc(orig_data, pp, old_size, mqrc)
        bad = verify_dbi_toc(new_data)
        # ignore the already-known bt=197 anomaly, which is independent of this change
        bad_new = [b for b in bad if not (b[0]=='bad_link' and b[2]['next_bt']==197)]
        if bad_new:
            print(t('encode_toc_warning', n=len(bad_new)))
        else:
            print(t('toc_check_ok'))
    else:
        new_data=orig_data[:pp]+mqrc+orig_data[pp+old_size:]

    # Save
    out_path = dbi_path if overwrite else dbi_path.replace('.DBI','_mod.DBI').replace('.dbi','_mod.dbi')
    if not overwrite and out_path == dbi_path:
        out_path = dbi_path + '.mod'
    if overwrite:
        _make_backup(dbi_path)
    with open(out_path,'wb') as f: f.write(new_data)
    print(t('encode_saved', path=out_path, suffix=(t('overwrite_suffix') if overwrite else '')))
    print(t('encode_block_delta', sign=('+' if new_size>=old_size else ''), delta=new_size-old_size))

    # Check: read it back
    print(t('encode_checking'))
    hist_v, hp_v = decompress(compressed, init_codes, hp_end)
    rows_v, _ = _rebuild_rows_v2_with_patches(hist_v, W, H, hp_v)
    ok = all(bytes(rows_v[r]) == bytes(rows[r][:W]) for r in range(H))
    print(t('pixel_match', result=(t('pixel_match_ok') if ok else t('pixel_match_err'))))

# --- Main --------------------------------------------------------------------

def main():
    global LANG
    args0 = sys.argv[1:]
    lang_override = None
    args1 = []
    for a in args0:
        if a.lower().startswith('--lang='):
            lang_override = a.split('=', 1)[1].lower()
        else:
            args1.append(a)
    if lang_override:
        if lang_override not in STRINGS:
            sys.exit(f"Unsupported --lang= value: '{lang_override}' (supported: {', '.join(STRINGS)})")
        LANG = lang_override

    if len(args1)<1 or args1[0].lower() in ('-h','--help','help','info'):
        print_help()
        sys.exit(0)

    cmd=args1[0].lower()
    args = args1[1:]

    # Strip the 'ow' (overwrite) suffix, if present - it can come at the
    # END of any (encode/insert/replace) command.
    overwrite = False
    if args and args[-1].lower() == 'ow':
        overwrite = True
        args = args[:-1]

    if cmd=='list' and len(args)>=1:
        cmd_list(args[0])

    elif cmd=='decode' and len(args)>=2:
        # python script.py decode ANY.DBI output_dir/ [NAME_PREFIX_FILTER]
        # UNIFIED (v2.12): auto-detects portrait vs. ISO-style blocks -
        # works the same way on UNIT.DBI, MIDGARD.DBI, CAPITAL.DBI, etc.
        name_filter = args[2] if len(args) >= 3 else None
        cmd_decode(args[0], args[1], name_filter)

    elif cmd=='decodeall':
        # python script.py decodeall [search_dir] [output_base_dir]
        # NEW (v2.20): finds every .DBI in search_dir (default: current
        # directory) and decodes each into its own ./NAME/ folder - see
        # cmd_decode_all()'s docstring. Speeds up the
        # "tweak codec -> re-decode everything -> eyeball for defects"
        # loop versus calling 'decode' once per file by hand.
        search_dir = args[0] if len(args) >= 1 else '.'
        out_base_dir = args[1] if len(args) >= 2 else None
        cmd_decode_all(search_dir, out_base_dir)

    elif cmd in ('encode', 'insert') and len(args)>=2:
        # python script.py encode image.png UNIT.DBI [PREFIX+INDEX] [ow]
        # python script.py encode image.png ANY_OTHER.DBI NAME [ow]
        # UNIFIED (v2.31): UNIT.DBI is a special, hidden case that keeps
        # using its own dedicated, more compact portrait encoder (see
        # cmd_encode's/cmd_isoencode's docstrings for why - already
        # round-trip validated as both correct and smaller than the
        # general ISO encoder for portrait-shaped images) with automatic
        # name generation. Every other file uses the general ISO-style
        # encoder and needs an explicit NAME (ISO object types use
        # meaningful prefixes - GUN/GSY/GLM/GIT/GRF/etc. - there's no
        # single "next number" scheme that would fit all of them, unlike
        # UNIT.DBI's GP### portraits).
        # ('insert' kept as an alias for older scripts/habits)
        img_, dbi_ = args[0], args[1]
        if os.path.splitext(os.path.basename(dbi_))[0].upper() == 'UNIT':
            prefix_, forced_idx_ = 'GP', None
            if len(args) >= 3:
                m = re.match(r'^([A-Za-z]+)(\d+)$', args[2])
                if not m:
                    sys.exit(t('main_invalid_prefix', val=args[2]))
                prefix_, forced_idx_ = m.group(1).upper(), int(m.group(2))
            cmd_insert(img_, dbi_, prefix_, forced_idx_, overwrite=overwrite)
        else:
            if len(args) < 3:
                sys.exit(t('main_encode_needs_name', dbi=dbi_, img=img_))
            cmd_isoencode(img_, dbi_, args[2], overwrite=overwrite)

    elif cmd=='replace' and len(args)>=3:
        # python script.py replace image.png ANY.DBI TARGET_NAME [ow]
        # UNIFIED (v2.16): auto-detects whether TARGET_NAME is a
        # portrait-style or ISO-style block (same classify_block_kind()
        # used by 'decode') and dispatches to the matching encoder - one
        # command now works for UNIT.DBI, MIDGARD.DBI, CAPITAL.DBI, etc.
        img_, dbi_, name_ = args[0], args[1], args[2]
        with open(dbi_, 'rb') as f:
            _data_peek = f.read()
        _init_codes_peek = load_init_codes()
        _palette_peek = _find_palette_in_dbi(_data_peek)
        _blocks_peek = scan_dbi_blocks(_data_peek, init_codes=_init_codes_peek, palette=_palette_peek)
        _hit = [b for b in _blocks_peek if b['name'].startswith(name_)]
        if not _hit:
            sys.exit(t('main_no_block_named', name=name_, dbi=dbi_,
                      names=[b['name'] for b in _blocks_peek][:5]))
        if _hit[0]['kind'] == 'portrait':
            cmd_encode(img_, dbi_, name_, overwrite=overwrite)
        else:
            cmd_isoreplace(img_, dbi_, _hit[0]['name'], overwrite=overwrite)

    elif cmd=='isoreplace' and len(args)>=3:
        # python script.py isoreplace image.png ISO.DBI TARGET_NAME [ow]
        # EXPERIMENTAL: replace an EXISTING ISO-style graphic block's
        # image data (keeps its name and bt).
        cmd_isoreplace(args[0], args[1], args[2], overwrite=overwrite)

    else:
        print_help()
        sys.exit(1)

if __name__=='__main__':
    main()
