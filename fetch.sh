#!/bin/bash
# Pull FCC exhibits for sen.se Cookie (COO001) and Mother (MOM001).
# Both filings dated 2014-03-31, US 915 MHz proprietary radio.
# Source: https://fcc.report/

set -euo pipefail
cd "$(dirname "$0")"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 sense-mother-re/0.1"

dl() {
  local out="$1" url="$2"
  if [[ -s "$out" ]]; then
    echo "skip  $out (already exists)"
    return
  fi
  echo "fetch $out"
  curl -fsSL -A "$UA" -o "$out" "$url"
}

# Cookie (COO001) — FCC ID 2ABGNCOO001
dl fcc/cookie/internal-photos.pdf  https://fcc.report/FCC-ID/2ABGNCOO001/2228967.pdf
dl fcc/cookie/external-photos.pdf  https://fcc.report/FCC-ID/2ABGNCOO001/2228966.pdf
dl fcc/cookie/rf-test-report.pdf   https://fcc.report/FCC-ID/2ABGNCOO001/2228964.pdf
dl fcc/cookie/user-manual.pdf      https://fcc.report/FCC-ID/2ABGNCOO001/2228970.pdf
dl fcc/cookie/label-info.pdf       https://fcc.report/FCC-ID/2ABGNCOO001/2228969.pdf
dl fcc/cookie/label-location.pdf   https://fcc.report/FCC-ID/2ABGNCOO001/2228968.pdf
dl fcc/cookie/test-setup.pdf       https://fcc.report/FCC-ID/2ABGNCOO001/2228965.pdf

# Mother (MOM001) — FCC ID 2ABGNMOM001
dl fcc/mother/internal-photos.pdf  https://fcc.report/FCC-ID/2ABGNMOM001/2229011.pdf
dl fcc/mother/external-photos.pdf  https://fcc.report/FCC-ID/2ABGNMOM001/2229010.pdf
dl fcc/mother/rf-test-report.pdf   https://fcc.report/FCC-ID/2ABGNMOM001/2229008.pdf
dl fcc/mother/user-manual.pdf      https://fcc.report/FCC-ID/2ABGNMOM001/2229014.pdf
dl fcc/mother/label-info.pdf       https://fcc.report/FCC-ID/2ABGNMOM001/2229013.pdf
dl fcc/mother/label-location.pdf   https://fcc.report/FCC-ID/2ABGNMOM001/2229012.pdf
dl fcc/mother/test-setup.pdf       https://fcc.report/FCC-ID/2ABGNMOM001/2229009.pdf

echo
echo "done. files:"
ls -lh fcc/cookie/ fcc/mother/
