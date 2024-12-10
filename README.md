# Weibo Favorites Backup Tool

This is a command-line tool for backing up and restoring Weibo favorites ("我的收藏"). With this tool, you can easily download all of your favorite Weibo posts and save them to your local machine.

# Motivation

I collected too many posts in Weibo, which was inconvenient to manage. After a period of time, I found that some of them had become invalid, so I decided to write a command line tool to back up and restore them.

# How to Use

## Installation

To install the Weibo Favorites Backup Tool, follow these steps:

1. Clone the repository:
```bash
git clone https://github.com/xujiajiadexiaokeai/get-weibo-favorites.git
cd get-weibo-favorites
```

2. Install dependencies:
```bash
pip install -e .
```

## Usage

The tool has two main components:

1. A crawler for backing up your Weibo favorites
2. A web interface for managing and viewing your backed-up favorites

### Getting Cookies

First, you need to get your Weibo cookies:

```bash
python -m weibo_favorites.crawler.auth
```

This will:
1. Open a Chrome browser window
2. Navigate to Weibo's login page
3. Wait for you to manually log in
4. Save your cookies to `data/weibo_cookies.json` after successful login

### Scheduling Crawl Favorites

After obtaining the cookies, you can initiate the scheduling process to back up your favorites:

```bash
python -m weibo_favorites.scheduler
```

This will:
1. Load cookies from `data/weibo_cookies.json`
2. Periodically fetch your Weibo favorites page by page
3. Save the results to `data/weibo_favorites.db`

### Running the Web Interface

```bash
python -m weibo_favorites.web.app
```

The web interface will be available at `http://localhost:5001`

The interface will display:
1. Crawler running status
2. Crawler running logs
3. Backed-up favorites

## Configuration

All configuration items are managed in `src/weibo_favorites/config.py`:

- Data file paths: `DATA_DIR`
- Log file paths: `LOGS_DIR`
- API configuration: `BASE_URL`, `REQUEST_DELAY`
- Logging configuration: `LOG_LEVEL`, `LOG_FORMAT`

## Data Format

The crawler saves favorites in JSON format. Each favorite contains:

- Basic information:
  - `id`: Weibo ID (string)
  - `created_at`: Creation time of the Weibo post
  - `collected_at`: Time when the post was collected by the crawler
  - `url`: Direct link to the Weibo post
  - `source`: Post source (e.g., "iPhone客户端", "微博 weibo.com")

- Content:
  - `text`: Raw text content of the post
  - `text_html`: HTML formatted text content
  - `is_long_text`: Whether the post is a long text post
  - `links`: List of external links in the post

- User information:
  - `user_id`: User ID (string)
  - `user_name`: Username (screen name)

Example:
```json
{
    "id": "4884450687058493",
    "created_at": "Tue Mar 28 20:15:47 +0800 2023",
    "url": "https://weibo.com/1727858283/MzqWMtCeF",
    "user_name": "Example User",
    "user_id": "1727858283",
    "is_long_text": true,
    "text": "这是一条微博的原始文本内容",
    "text_html": "这是一条微博的<a href='...'>HTML格式</a>文本内容",
    "source": "iPhone客户端",
    "links": ["https://example.com/link1", "https://example.com/link2"],
    "collected_at": "2023-12-20 15:30:45"
}
```

# License
Apache License 2.0