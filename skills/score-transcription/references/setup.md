# Tested tool setup

The encoder needs Python's standard library. Validation needs lxml, PDF work
needs PyMuPDF, and rendering needs MuseScore. Audiveris is optional for direct
visual transcription. Tested: Ubuntu 24.04, Linux x86_64, Python 3.12. Other
platforms need appropriate upstream binaries and launcher changes; untested.

Replace the example paths with your resolved skill and tools directories:

```sh
python3 -m venv /path/to/tools/python
/path/to/tools/python/bin/pip install -r /path/to/skill/assets/requirements.txt
/path/to/tools/python/bin/python /path/to/skill/scripts/bootstrap.py --tools /path/to/tools
/path/to/tools/python/bin/python /path/to/skill/scripts/bootstrap.py --tools /path/to/tools --check
```

The bootstrap currently downloads all pinned tools, including optional Audiveris.
Review its download manifest first and obtain permission for network/install
actions when needed. Installs stay under the chosen tools directory; no system
packages or shell startup files are changed. Audiveris includes Java and requires
`dpkg-deb` for extraction. MuseScore AppImage extraction avoids FUSE. Diagnose
missing system libraries from actual launch logs rather than guessing packages.

Pins: MuseScore 4.7.4, Audiveris 5.11.0, full legacy-compatible Finnish/German/
English Tesseract data. Languages are per-score choices, not mandatory output
languages. `tessdata_fast` failed with this Audiveris version. SHA-256 verification
occurs before extraction/execution; changed upstream branch contents deliberately
fail verification rather than silently upgrading.

`--check` checks archives, entrypoints, language hashes and Python dependencies;
it does not prove every extracted binary or runtime library matches. A successful
render and, if used, OMR run are separate runtime tests. Supply `--tools` or
`KENGRAVER_TOOLS` when running outside an ancestor containing `.tools`.

MusicXML 4.0 schemas are bundled with their original notices. Schema checking
does not fetch external resources. Copy the entire skill folder when sharing;
large binaries and Python packages do not accompany it.
