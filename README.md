# Weibo Favorites Backup Tool

This is a command-line tool for backing up and restoring Weibo favorites ("我的收藏"). With this tool, you can easily download all of your favorite Weibo posts and save them to your local machine.

# Motivation

I collected too many posts in Weibo, which was inconvenient to manage. After a period of time, I found that some of them had become invalid, so I decided to write a command line tool to back up and restore them.

# How to Use

## Installation

To install the Weibo Favorites Crawler, follow these steps:

1. Clone the repository:
    ```bash
    git clone https://github.com/xujiajiadexiaokeai/get-weibo-favorites.git
    cd get-weibo-favorites
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

The crawler consists of two main scripts:

1. `weibo_auth.py`: Used to obtain Weibo cookies through browser automation
2. `weibo_crawler.py`: The main script for crawling your Weibo favorites

### Getting Cookies

First, you need to get your Weibo cookies:

```bash
python weibo_auth.py
```

This will:
1. Open a Chrome browser window
2. Navigate to Weibo's login page
3. Wait for you to manually log in
4. Save your cookies to `weibo_cookies.json` after successful login

### Crawling Favorites

After obtaining the cookies, you can start crawling your favorites:

```bash
python weibo_crawler.py
```

The script will:
1. Load cookies from `weibo_cookies.json`
2. Fetch your Weibo favorites page by page
3. Save the results to `favorites.json`

### Testing

To test if the crawler is working correctly:

```bash
python test_crawler.py
```

This will attempt to fetch the first page of your favorites and save them to `test_favorites.json`.

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