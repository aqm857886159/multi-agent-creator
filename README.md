# Topic Radar (选题雷达)

Multi-agent workflow for content discovery and curation using LangGraph.

## Features
- **Dual Engine Collection**: "Hunter Mode" (low follower, high engagement) & "Monitor Mode" (KOL tracking).
- **Automated Discovery**: Uses Firecrawl to find new influencers if the list is empty.
- **Smart Filtering**: Hybrid rules for viral content detection.
- **AI Architect**: Generates content proposals based on data insights.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Environment:
   Copy `.env.example` to `.env` (if not auto-created) and fill in:
   - `OPENAI_API_KEY` (for LLM)
   - `FIRECRAWL_API_KEY` (for Discovery)
   - `REDDIT_...` (for Reddit Search)

3. Configure Settings:
   Edit `config/settings.yaml` to define your target domains and whitelist KOLs.

## Usage

Run the main script:
```bash
python main.py
```

## Modules

- `core/`: State definitions, Graph logic, Config.
- `nodes/`: The functional steps (Discovery, Aggregation, Filtering, Architecture).
- `tools/`: Wrappers for Firecrawl, DrissionPage, yt-dlp, PRAW.

## Notes for Optimization
- **Async**: Currently runs sequentially. For production, convert `aggregator.py` to use `asyncio` for parallel scraping.
- **Headless Browser**: `DouyinScout` defaults to headless. If you encounter anti-bot pages, try setting `headless=False` in `nodes/aggregator.py` or using a persistent user profile.
- **Proxies**: Strongly recommended for `yt-dlp` and `DrissionPage` to avoid IP bans.

