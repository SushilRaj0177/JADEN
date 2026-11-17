"""Downloads the two public datasets the real-data evaluations run on.

  care       Ministry of Health, Labour and Welfare, 介護サービス情報公表システム open data:
             one CSV per care service with every office's name, address as typed, building,
             municipality code and coordinates. Licence: CC BY (see the page for the terms).
  companies  National Tax Agency, 法人番号公表サイト, full download (CSV, Unicode): every
             corporation's registered address with its municipality code and postal code.
             Licence: the site's terms of use (compatible with CC BY 4.0).

The files are large (about 95 MB and 270 MB) and are not part of this repository. They go to
~/.cache/jaden-realdata unless --data says otherwise, together with a provenance.json holding
the source, the date of the data, the sizes and the SHA-256 of every file.

Usage:
    python benchmarks/realdata/download.py care companies [--data DIR]
"""

import argparse
import datetime
import hashlib
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_DATA = Path.home() / ".cache" / "jaden-realdata"
USER_AGENT = "JADEN-realdata-evaluation/1.0"
CARE_PAGE = "https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html"
COMPANIES_PAGE = "https://www.houjin-bangou.nta.go.jp/download/zenken/"
TOKEN_FIELD = "jp.go.nta.houjin_bangou.framework.web.common.CNSFWTokenProcessor.request.token"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch(opener: urllib.request.OpenerDirector, url: str, data: Any = None, timeout: int = 1800) -> bytes:
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=timeout) as response:
        return response.read()


def download_care(folder: Path) -> Dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener()
    page = _fetch(opener, CARE_PAGE).decode("utf-8", errors="replace")
    links = sorted(set(re.findall(r'href="(/content/[^"]+/jigyosho_\d+\.csv)"', page)))
    if not links:
        raise SystemExit("no jigyosho_NNN.csv links on the page: its layout has changed")
    as_of = re.search(r"(\d{4}年[0-9０-９]+月末時点)", page)
    files: List[Dict[str, Any]] = []
    for link in links:
        target = folder / link.rsplit("/", 1)[1]
        if not target.exists() or target.stat().st_size < 1000:
            print("fetch", link)
            target.write_bytes(_fetch(opener, "https://www.mhlw.go.jp" + link))
        files.append({"file": target.name, "bytes": target.stat().st_size, "sha256": _sha256(target)})
    return {"source": CARE_PAGE, "publisher": "厚生労働省 介護サービス情報公表システム", "licence": "CC BY",
            "as_of": as_of.group(1) if as_of else "unknown", "files": files}


def download_companies(folder: Path) -> Dict[str, Any]:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "zenkoku.zip"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    if not target.exists() or target.stat().st_size < 1_000_000:
        page = _fetch(opener, COMPANIES_PAGE).decode("utf-8", errors="replace")
        token = re.search(re.escape(TOKEN_FIELD) + r'" value="([^"]+)"', page)
        section = page[page.find('id="csv-unicode"'):page.find('id="xml-unicode"')]
        file_no = re.search(r"doDownload\((\d+)\)", section)   # the first entry of the section is 全国
        if not token or not file_no:
            raise SystemExit("the download form was not found: the page layout has changed")
        form = urllib.parse.urlencode({TOKEN_FIELD: token.group(1), "event": "download",
                                       "selDlFileNo": file_no.group(1)}).encode("ascii")
        print("fetch nationwide CSV (Unicode), file", file_no.group(1))
        target.write_bytes(_fetch(opener, COMPANIES_PAGE + "index.html", data=form))
    with zipfile.ZipFile(target) as z:
        inner = next(i for i in z.infolist() if i.filename.endswith(".csv"))
    stamp = re.search(r"(\d{4})(\d{2})(\d{2})", inner.filename)
    return {"source": COMPANIES_PAGE, "publisher": "国税庁 法人番号公表サイト", "licence": "法人番号公表サイト利用規約",
            "as_of": "-".join(stamp.groups()) if stamp else "unknown", "file": inner.filename,
            "rows_bytes": inner.file_size, "bytes": target.stat().st_size, "sha256": _sha256(target)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("datasets", nargs="+", choices=["care", "companies"])
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = ap.parse_args()
    for name in args.datasets:
        folder = args.data / name
        meta = download_care(folder) if name == "care" else download_companies(folder)
        meta["downloaded"] = datetime.date.today().isoformat()
        (folder / "provenance.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"{name}: data as of {meta['as_of']} in {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
