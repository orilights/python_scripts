# [Pixiv Collection](https://github.com/orilights/PixivCollection) 项目相关脚本

## 教程

简要的使用教程

1. 爬取图片（推荐使用 [Powerful Pixiv Downloader](https://github.com/xuejianxianzun/PixivBatchDownloader) 浏览器拓展）并按照 `[pid]_p[part].[ext]` 命名，放置于 `image/original` 目录下
2. 下载或克隆本项目，安装 Python （开发环境为 Python 3.10）与相关依赖（pip install -r requirements.txt）
3. 获取 Pixiv 账号的 refresh token，具体步骤请参照 [Pixiv OAuth Flow](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362) 或 [Pixiv OAuth Flow (with Selenium)](https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde)
4. 将 `USER_ID` 和 `REFRESH_TOKEN` 填入 `example.py` 的对应位置
5. 执行 `python example.py`

脚本默认会进行以下操作：

1. 检查 refresh token 是否可用
2. 读取 `images.json` 中的数据
3. 获取用户公开收藏图片和不公开收藏图片各自的前两页，下载不存在于本地的图片
4. 获取新增图片的信息
5. 在 `image/preview` 目录下生成 WebP 格式预览图（尺寸不大于 2000*2000，质量 80）
6. 在 `image/thumbnail` 目录下生成 WebP 格式缩略图（尺寸不大于 500*1000，质量 70）
7. 将本地不存在的文件从数据中删除
8. 将数据保存到 `images.json` 文件

## 数据格式

以下为数据格式的 TS 定义，数据以 JSON 数组保存

```ts
interface Tag {
  name: string
  translated_name: string | null
}

interface Image {
  id: number
  part: number
  title: string
  size: [number, number]
  ext: string
  author: {
    id: number
    name: string
    account: string
  }
  tags: Tag[]
  created_at: string
  sanity_level: number
  x_restrict: number
  dominant_color: string
}
```

## 感谢

[upbit/pixivpy](https://github.com/upbit/pixivpy)

[xuejianxianzun/PixivBatchDownloader](https://github.com/xuejianxianzun/PixivBatchDownloader)

[fengsp/color-thief-py](https://github.com/fengsp/color-thief-py)
