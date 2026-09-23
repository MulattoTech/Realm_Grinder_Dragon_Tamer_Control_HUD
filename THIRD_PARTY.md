# Third-Party Code and Licenses

This project incorporates, adapts, or references the following third-party works in accordance with the integrity and licensing instructions.

## 1. dox4242 / RG-tools (`savecodec2.js`, `pako.js`, `arch/artifacts.js`)
* **Repository:** https://github.com/dox4242/RG-tools
* **License:** MIT License
* **Original Copyright:**
  ```
  The MIT License (MIT)

  Royal Advisory Board
  https://github.com/nyanlathotep/royal-advisory-board
  https://nyanlathotep.github.io/royal-advisory-board
  Copyright (c) 2015 Nyanlathotep

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
  ```
* **Usage in this Project:** Used to inspect, extract, and decode the Adobe AIR SharedObject / exported save strings in read-only mode to reliably verify Reincarnation, Excavations, Artifacts, and Quest progression without modifying save values.

---

## 2. fennovj / py-rgtools
* **Repository:** https://github.com/fennovj/py-rgtools
* **License:** MIT License
* **Original Copyright:**
  ```
  MIT License

  Copyright (c) 2019 Fenno Vermeij

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in all
  copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.
  ```
* **Usage in this Project:** Referenced for save structure specification, formats, and Vigenère decryption logic (`therealmisalie`).

---

## 3. JayRizzo / rg_code
* **Repository:** https://github.com/JayRizzo/rg_code
* **License:** GPL-3.0
* **Usage in this Project:** Inspected for architectural concepts and research build notes. Per instructions, clean-room reimplementation was chosen for the Python orchestrator to avoid viral licensing entanglement.

---

## 4. Systemcluster / realm_grinder_autoclicker.ahk
* **Source:** https://gist.github.com/Systemcluster/b4f1e5568d9493c5bb48dbc0aa458d16
* **Copyright:** (c) 2019 Systemcluster
* **License Status:** No explicit open-source license provided on Gist.
* **Usage in this Project:** Architectural and behavioral reference ONLY. No code copied. The coordinate normalization and button detection concepts guided our clean-room Python Win32 window interaction engine.

## Source-backed progression additions (2026-09-23)

`data/reference_identifiers.json` contains factual identifier mappings parsed from the attributed dox4242 RG-tools reference already listed above; its source hash and URL are retained. No retrieved wiki JavaScript is executed. `data/installed_identifiers.json` contains only literal names, IDs and kinds observed in the user's installed game, scoped by binary hash, not game bytecode.

Wiki prose, templates and images retain the respective source's terms. The Fandom corpus identifies CC-BY-SA where the source does; musicfamily material is not presumed to have an open-code license. Full scraped source pages and extracted game texture atlases remain in local ignored caches. A source URL in a manifest is not a grant to redistribute its contents.

Three small UI matching snippets in `data/ui_reference` are private-project calibration references, not standalone game assets or a new license grant; game UI copyright remains with its rightsholders. Their binary scope, checksums and limited purpose are recorded in that directory's manifest. Original application artwork/branding and legacy scripts are preserved as project materials. No font files are included.

No application-wide license has been newly selected in this maintenance pass. Keep this repository private unless the owner reviews rights and chooses distribution terms.
