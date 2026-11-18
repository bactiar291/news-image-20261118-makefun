# news-image-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/bactiar291/news-image-20261118-makefun/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard)
[![reward](https://make.fun/badge/news-image-20261118/bactiar291/news-image-20261118-makefun/reward.svg)](https://make.fun/bounty/news-image-20261118)

A deterministic, standard-library Python raster front page for the news of 18 November 2026. It writes one 1000x1000 PNG to `MAKEFUN_OUTPUT_DIR`, or `/output` by default.

## Run

```sh
python3 -P -s main.py
```

For a local capture, set `MAKEFUN_OUTPUT_DIR` to a writable directory. Run focused checks with `python3 -B tests/verify.py`.

