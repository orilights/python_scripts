from .collection import PixivCollection

PATH_ORIGINAL = './image/original/'  # 原图保存路径
PATH_PREVIEW = './image/preview/'  # 预览图保存路径
PATH_THUMBNAIL = './image/thumbnail/'  # 缩略图保存路径
LOG_FILE = './logs/example_{time}.log'  # 日志文件路径

USER_ID = 20180111  # 用户ID
REFRESH_TOKEN = 'xxxxxx'  # refresh_token

c = PixivCollection()
c.add_logger(LOG_FILE, level='DEBUG')
c.set_path({
    'original': PATH_ORIGINAL,
    'preview': PATH_PREVIEW,
    'thumbnail': PATH_THUMBNAIL,
})
if not c.init(refresh_token=REFRESH_TOKEN):
    print('PixivAPI初始化失败，程序退出')
    exit(1)
c.read_data('collection.json')
c.clean()
c.download_bookmark(user_id=USER_ID, type='public', max_page=2)
c.download_bookmark(user_id=USER_ID, type='private', max_page=2)
c.update()
c.generate_preview()
c.generate_thumbnail()
c.check(try_fix=True)
c.save_data('collection.json')
c.export('images.json')
