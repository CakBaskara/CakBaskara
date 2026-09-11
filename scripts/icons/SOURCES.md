# Toolbox icon sources

All 96 SVGs are unmodified Simple Icons source files pinned to commit
`777807a262bb7384ff406fd4b35fdcd02e9514c3`:
https://github.com/simple-icons/simple-icons/tree/777807a262bb7384ff406fd4b35fdcd02e9514c3/icons

The Simple Icons project is distributed under CC0-1.0. Brand names and trademarks
remain the property of their respective owners. See upstream
[license](https://github.com/simple-icons/simple-icons/blob/777807a262bb7384ff406fd4b35fdcd02e9514c3/LICENSE.md)
and [disclaimer](https://github.com/simple-icons/simple-icons/blob/777807a262bb7384ff406fd4b35fdcd02e9514c3/DISCLAIMER.md).

Keep the SVG geometry intact. Badge colors, default toolbox categories and
detection rules belong in `catalog.json`; badge sizing belongs in
`scripts/make_info_card.py`. New icon colors use the upstream brand hex as the
badge background with whichever of white or `#111111` contrasts more.
Java uses the OpenJDK logo and C# the .NET logo; Simple Icons no longer ships
the trademarked originals.

To add an icon, copy `<slug>.svg` from the same revision, add its catalog entry,
and record its digest in `manifest.json`.
`manifest.json` records normalized UTF-8 SHA-256 digests to detect accidental edits.
