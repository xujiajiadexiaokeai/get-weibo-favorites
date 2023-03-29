get-weibo-favorites
---

# Weibo Favorites Backup Tool

This is a command-line tool for backing up and restoring Weibo favorites ("我的收藏"). With this tool, you can easily download all of your favorite Weibo posts and save them to your local machine.

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

# License
Apache License 2.0