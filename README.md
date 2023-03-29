# Weibo Favorites Backup Tool

This is a command-line tool for backing up and restoring Weibo favorites ("我的收藏"). With this tool, you can easily download all of your favorite Weibo posts and save them to your local machine.

# Motivation

I collected too many posts in Weibo, which was inconvenient to manage. After a period of time, I found that some of them had become invalid, so I decided to write a command line tool to back up and restore them.

# How to Use

## Installation

To install the Weibo Favorites Backup Tool, follow these steps:

1. Clone the repository:

    ```
    git clone https://github.com/xujiajiadexiaokeai/get-weibo-favorites.git
    ```

2. Install dependencies:

    ```
    go mod tidy
    ```

3. Build the tool:

    ```
    go build
    ```
4. Install the tool:
   
   ```
   go install
   ```

## Backup and Restore

To backup or restore your Weibo favorites, follow these steps:

1. Log in to Weibo to get your cookie.

2. Execute the `get-weibo-favorites` tool with the following options:

    - `-c <your-weibo-cookie>`: Required. Specifies your Weibo cookie.

    - `-p <page-number>`: Optional. Specifies the page number of your Weibo favorites to download. If not specified, all pages will be downloaded.
  

### Examples

- Backup all favorites
    ```sh
    $ get-weibo-favorites -c <your-weibo-cookie>
    ```

- Backup first page of favorites
    ```sh
    $ get-weibo-favorites -c <your-weibo-cookie> -p 1 
    ```
- CSV Example
  
| id | url | text | isLongText | links |
|:---:|:---:|:---:|:---:|:---:|
| 4884450687058493 | https://weibo.com/1727858283/MzqWMtCeF | 有人分析了ChatGPT的Browsing插件工作原理，你甚至可以加一些自定义命令，让它执行更复杂的工作。<br /><br />首先它有一些内置的函数：<br /><br />- search(query: str, recency_days: int): 根据关键词从搜索引擎搜索最近若干天的内容<br /><br />- click(id: str): 打开具有给定id的网页，显示它。显示的结果中的ID映射到一个URL ​​​ ...<span class="expand">展开</span> | true | https://twitter-thread.com/t/1639681620264337415 , https://twitter-thread.com/t/1640626881404755970 |

# License
Apache License 2.0