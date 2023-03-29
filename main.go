package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/spf13/cobra"
	"github.com/youseebiggirl/requests"
)

var (
	baseUrl      = "https://weibo.com/ajax/favorites/all_fav?"
	page         = 1
	weiboChan    = make(chan weibo, 1000)
	workerNumber = 2 // Maximum number of workers that can run at the same time
)

func getWeiboFav(cookie string, pageNumber int, wg *sync.WaitGroup) {

	workerCh := make(chan struct{}, workerNumber)
	defer close(workerCh)
	done := make(chan bool)

	for {
		select {
		case <-done:
			log.Println("no data, maybe is done")
			return
		default:
			if pageNumber != 0 && page > pageNumber {
				return
			} else {
				workerCh <- struct{}{}
				url := baseUrl + fmt.Sprintf("page=%v", page)
				get(url, cookie, workerCh, done, wg)
				page++
			}
		}
	}
}

func get(url, cookie string, workerCh chan struct{}, done chan bool, wg *sync.WaitGroup) {
	log.Println("start get", url)
	r := requests.GET(url, requests.WithCookie(cookie))
	if r.StatusCode() != http.StatusOK {
		err := fmt.Errorf("http GET status error: [%v]%v", r.StatusCode(), r.StatusText())
		log.Fatalln(err)
	}
	m := r.Map()
	data := m["data"].([]any)
	if len(data) == 0 {
		done <- true
	}
	for _, d := range data {
		dd := d.(map[string]any)
		wg.Add(1)
		weiboChan <- parseWeibo(dd)
	}

	<-workerCh
}

type weibo struct {
	id         string
	isLongText bool // “查看更多”
	text       string
	links      []string // “网页链接”
}

func parseWeibo(d map[string]any) weibo {
	weibo := weibo{}
	weibo.id = d["idstr"].(string)
	if _, ok := d["isLongText"]; ok {
		weibo.isLongText = d["isLongText"].(bool)
	}
	if _, ok := d["text"]; ok {
		weibo.text = d["text"].(string)
	} else {
		weibo.text = "no text"
	}
	if _, ok := d["url_struct"]; ok {
		url_struct := d["url_struct"].([]any)
		for _, u := range url_struct {
			uu := u.(map[string]any)
			weibo.links = append(weibo.links, uu["long_url"].(string))
		}
	}
	return weibo
}

var rootCmd = &cobra.Command{
	Use:     "get-weibo-favorites",
	Example: "  get-weibo-favorites -c <your-weibo-cookie>",
	Short:   "A command-line tool to crawl Weibo favorites",
	Long:    `A command-line tool to crawl Weibo favorites and save them to a CSV file.`,
	PreRun: func(cmd *cobra.Command, args []string) {
		cookie, _ := cmd.Flags().GetString("cookie")
		if cookie == "" {
			log.Println("cookie is required")
			cmd.Help()
			os.Exit(1)
		}
	},
	Run: func(cmd *cobra.Command, args []string) {
		cookie, _ := cmd.Flags().GetString("cookie")
		pageNumber, _ := cmd.Flags().GetInt("page")

		f, err := createCSV()
		if err != nil {
			log.Fatalln(err)
		}
		defer f.Close()
		wg := new(sync.WaitGroup)
		go func() {
			for w := range weiboChan {
				_, err := f.WriteString(fmt.Sprintf("%s\t%s\t%t\t%s\n", w.id, w.text, w.isLongText, strings.Join(w.links, " , ")))
				if err != nil {
					log.Fatalln(err)
				}
				wg.Done()
			}
		}()
		defer close(weiboChan)
		getWeiboFav(cookie, pageNumber, wg)
		wg.Wait()
	},
}

func createCSV() (*os.File, error) {
	startTime := time.Now().Format("2006-01-02-15:04")
	fileName := fmt.Sprintf("weiboFavorites-%s.csv", startTime)
	f, err := os.OpenFile(fileName, os.O_CREATE|os.O_RDWR, 0777)
	if err != nil {
		return nil, err
	}
	return f, nil
}

func init() {
	rootCmd.Flags().StringP("cookie", "c", "", "your Weibo cookie")
	rootCmd.MarkFlagRequired("cookie")
	rootCmd.Flags().IntP("page", "p", 0, "the page number to end at. If you don't specify a page number, it will crawl all pages.")

}

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
