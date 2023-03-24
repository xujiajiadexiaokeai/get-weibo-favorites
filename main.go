package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/youseebiggirl/requests"
)

type weibo struct {
	id         string
	isLongText bool // “查看更多”
	text       string
	links      []string // “网页链接”
}

var (
	srcCookie = "your cookie"
	baseUrl   = "https://weibo.com/ajax/favorites/all_fav?"
	page      = 1
	weiboChan = make(chan weibo, 1000)
)

func getFav() {
	ch := make(chan struct{}, 2)
	defer close(ch)
	defer close(weiboChan)
	done := false

	for !done {
		ch <- struct{}{}
		url := baseUrl + fmt.Sprintf("page=%v", page)
		fmt.Println(url)
		go func() {
			r := requests.GET(url, requests.WithCookie(srcCookie))
			if r.StatusCode() != http.StatusOK {
				err := fmt.Errorf("http GET status error: [%v]%v", r.StatusCode(), r.StatusText())
				log.Fatalln(err)
			}
			m := r.Map()
			data := m["data"].([]any)
			if len(data) == 0 {
				log.Println("no data, maybe is done")
				done = true
			}
			for _, d := range data {
				dd := d.(map[string]any)
				weibo := weibo{}
				weibo.id = dd["idstr"].(string)
				if _, ok := dd["isLongText"]; ok {
					weibo.isLongText = dd["isLongText"].(bool)
				}
				if _, ok := dd["text"]; ok {
					weibo.text = dd["text"].(string)
				} else {
					weibo.text = "no text"
				}
				if _, ok := dd["url_struct"]; ok {
					url_struct := dd["url_struct"].([]any)
					for _, u := range url_struct {
						uu := u.(map[string]any)
						weibo.links = append(weibo.links, uu["long_url"].(string))
					}
				}
				weiboChan <- weibo
			}

			<-ch
		}()
		page++
	}
}

func main() {
	f, err := os.OpenFile("favorites.csv", os.O_CREATE|os.O_RDWR, 0777)
	if err != nil {
		log.Fatalln(err)
	}
	defer f.Close()
	go func() {
		for w := range weiboChan {
			_, err := f.WriteString(fmt.Sprintf("%s\t%s\t%t\t%s\n", w.id, w.text, w.isLongText, strings.Join(w.links, " , ")))
			if err != nil {
				log.Fatalln(err)
			}
		}
	}()

	getFav()
}
