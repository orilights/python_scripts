from .pixiv_collection import PixivCollection

PATH_ORIGINAL = './image/original/'  # 原图保存路径
PATH_PREVIEW = './image/preview/'  # 预览图保存路径
PATH_THUMBNAIL = './image/thumbnail/'  # 缩略图保存路径
DATA_FILE = './images.json'  # 数据文件路径
LOG_FILE = './logs/example_{time}.log'  # 日志文件路径

USER_ID = 20180111  # 用户ID
REFRESH_TOKEN = 'xxxxxx'  # refresh_token

collection = PixivCollection(REFRESH_TOKEN, DATA_FILE, PATH_ORIGINAL, PATH_PREVIEW, PATH_THUMBNAIL, LOG_FILE)
if collection.api_available == False:
    print('PixivAPI初始化失败，程序退出')
    exit(1)
collection.download_bookmark(USER_ID, type='public', max_page=2)
collection.download_bookmark(USER_ID, type='private', max_page=2)
collection.match_images()
collection.clean_deleted_images()
collection.generate_preview(overwrite=False)
collection.generate_thumbnail(overwrite=False)
collection.check(try_fix=True)
collection.save(DATA_FILE)

