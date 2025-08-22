# wrongwordsTRUE

Scan Idena flips for `wrongWords` flags per epoch, aggregate offenders per identity, and create summaries and plots across recent epochs.

This repo contains three small Python tools:

- `find_wrongwords.py` - scans one epoch and prints a per-identity count of flips flagged with `wrongWords=True`.
- `findwrongwordshistoric.py` - scans a rolling window of recent epochs (default ~60) and collects results.
- `summarize_wrongwords.py` - reads the collected results and generates CSV summaries and PNG plots.

Background material about penalties for reported flips is included in
`Idena-Go.Hard.Fork.Implementation.Consensus.V13.Reported.Flips.Penalty(1).pdf`.

> The current repo stub shows basic usage like:
>
> - `python3 find_wrongwords.py`
> - `python3 findwrongwordshistoric.py`
>
> and a live log that displays progress and a per-epoch table with an extra `>1` marker for identities with more than one offending flip.

---

## Table of contents

- [Quick start](#quick-start)
- [Installation](#installation)
- [Scripts and usage](#scripts-and-usage)
  - [1) find_wrongwords.py - single epoch](#1-find_wrongwordspy---single-epoch)
  - [2) findwrongwordshistoric.py - rolling window](#2-findwrongwordshistoricpy---rolling-window)
  - [3) summarize_wrongwords.py - CSV and plots](#3-summarize_wrongwordspy---csv-and-plots)
- [Outputs](#outputs)
- [Examples](#examples)
- [Tips - performance and rate limits](#tips---performance-and-rate-limits)
- [Troubleshooting](#troubleshooting)
- [Development notes](#development-notes)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Quick start

```bash
# 1) clone
git clone https://github.com/ubiubi18/wrongwordsTRUE.git
cd wrongwordsTRUE

# 2) create a virtualenv
python3 -m venv .venv
# - macOS/Linux
source .venv/bin/activate
# - Windows PowerShell
# .\.venv\Scripts\Activate.ps1

# 3) install deps
pip install -U pip
pip install requests pandas matplotlib python-dateutil

# 4) run a single-epoch scan
python3 find_wrongwords.py

# 5) run a rolling multi-epoch scan
python3 findwrongwordshistoric.py

# 6) build summaries and plots
python3 summarize_wrongwords.py
```

If your Python is called python instead of python3, just swap the command name.

## Installation

### Requirements

- Python 3.9 or newer
- Internet access to query public Idena endpoints
- Python packages
  - `requests` - HTTP calls for flip data
  - `pandas` - tabular aggregation for summaries
  - `matplotlib` - plotting PNG charts
  - `python-dateutil` - time helpers

Install everything with:

```bash
pip install requests pandas matplotlib python-dateutil
```

If you only run the single-epoch scanner and you do not need plots, you can get by with just:

```bash
pip install requests
```

## Scripts and usage

### 1) find_wrongwords.py - single epoch

Scans flips for one epoch and prints a compact table of identities with their wrongWords counts. The script shows a live progress log, then a final summary.

Run:

```bash
python3 find_wrongwords.py
```

Save output to a file:

macOS/Linux:

```bash
python3 find_wrongwords.py | tee runs/wrongwords_latest.txt
```

Windows PowerShell:

```powershell
python3 find_wrongwords.py | Tee-Object -FilePath runs\wrongwords_latest.txt
```

Notes:

- The table marks identities with `>1` if they have more than one offending flip in the scanned epoch.
- If you need a specific epoch and the script does not accept a flag, run the historic scanner below and pick the epoch you want from its outputs.

### 2) findwrongwordshistoric.py - rolling window

Scans a span of recent epochs (the repo notes "last 60 epochs") and aggregates results for each epoch. This is useful to observe patterns across time.

Run:

```bash
python3 findwrongwordshistoric.py
```

Log and capture:

macOS/Linux:

```bash
python3 findwrongwordshistoric.py | tee runs/wrongwords_last60.log
```

Windows PowerShell:

```powershell
python3 findwrongwordshistoric.py | Tee-Object -FilePath runs\wrongwords_last60.log
```

This script will create per-epoch results in the working directory or a `results/` folder depending on configuration. If nothing gets written automatically, keep the console captures and feed them to the summarizer or export CSV using the summarizer.

### 3) summarize_wrongwords.py - CSV and plots

Reads the outputs produced by the scanners and generates:

- a clean CSV summary per epoch and overall
- PNG plots that visualize reported wrongWords counts over time

The repo already includes example artifacts like `result_sample wrongwords_epoch166.csv` and PNGs `output(2).png`, `output(3).png`, and `output(4).png` to illustrate the expected outputs.

Run:

```bash
python3 summarize_wrongwords.py
```

Heads-up for headless servers:

If matplotlib complains about displays, use the non-interactive backend:

macOS/Linux:

```bash
export MPLBACKEND=Agg
python3 summarize_wrongwords.py
```

Windows PowerShell:

```powershell
setx MPLBACKEND Agg
python3 summarize_wrongwords.py
```

## Outputs

Depending on your run, you should see a mix of:

- **Console tables** - per-epoch lists like:

  ```
  address                         wrongWordsCount
  0xabc...                        0
  0xdef...                        3  >1
  0x123...                        2  >1
  ...
  ```

- **CSV files** - for example:
  - `wrongwords_epoch166.csv` or `result_sample wrongwords_epoch166.csv`
  - Columns typically include `address` and `wrongWordsCount` with an optional marker for `>1`.

- **PNG plots** - for example:
  - `output(2).png`
  - `output(3).png`
  - `output(4).png`

If your files are named slightly differently, keep the defaults and adjust the `summarize_wrongwords.py` input paths accordingly.

## Examples

### Example - single epoch to CSV then open in a spreadsheet

```bash
# 1) run the scan and capture text
python3 find_wrongwords.py | tee runs/epoch_latest.txt

# 2) post-process into CSV using summarize script (expects collected inputs)
python3 summarize_wrongwords.py
```

### Example - full workflow on a fresh machine

```bash
git clone https://github.com/ubiubi18/wrongwordsTRUE.git
cd wrongwordsTRUE
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install requests pandas matplotlib python-dateutil

# scan latest epoch
python3 find_wrongwords.py

# scan last ~60 epochs
python3 findwrongwordshistoric.py

# summarize and plot
python3 summarize_wrongwords.py
```

## Tips - performance and rate limits

- Be gentle with public endpoints - add short sleeps if you see 429 responses.
- If the API exposes pagination, do not parallelize too aggressively.
- If needed, cache raw responses locally so re-runs do not re-fetch unchanged epochs.

## Troubleshooting

- **HTTP 429 or timeouts** - reduce concurrency and add `time.sleep()` between requests.
- **ModuleNotFoundError: requests** - run `pip install requests`.
- **Matplotlib display errors** - set `MPLBACKEND=Agg` as shown above.
- **Empty outputs** - check that the epoch actually has published flips and that your clock is correct.

## Development notes

- The repo’s quick-start usage and the presence of the sample CSV and PNGs come from the main branch file listing and README stub.
- The background PDF on reported flips penalties is bundled in the repo for reference.

## License

MIT Licence

## Acknowledgments

- Idena community and documentation
- Included vibe coding proposal for hardfork to fork out bad players:
  - `Idena-Go.Hard.Fork.Implementation.Consensus.V13.Reported.Flips.Penalty(1).pdf`
