from playwright.sync_api import sync_playwright, Response


def get_appcustomconfig():

    def get_response(response: Response):
        if not response.url.startswith(
                'https://music.163.com/weapi/appcustomconfig'):
            return
        if response.status != 200:
            return
        data = response.json()['data']
        if data.get('web-pc-beta-download-links'):
            # PC Beta版
            print(data['web-pc-beta-download-links'])
        if data.get('linux_download_links'):
            # Linux版
            print(data['linux_download_links'])
        if data.get('web-tv-download-link'):
            # TV版和车机版
            print(data['web-tv-download-link'])

    with sync_playwright() as p:
        browser = p.webkit.launch()
        page = browser.new_page()
        page.on("response", get_response)
        page.goto("https://music.163.com/st/download")
        page.wait_for_timeout(5000)
        browser.close()


if __name__ == '__main__':
    get_appcustomconfig()
