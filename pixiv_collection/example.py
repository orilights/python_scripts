from io import StringIO

from pixiv_collection import PixivCollection

PATH_ORIGINAL = './image/original/'  # 原图保存路径
PATH_LARGE = './image/large/'  # 大图保存路径
PATH_THUMBNAIL = './image/thumbnail/'  # 缩略图保存路径
DATA_FILE = './images.json'  # 数据文件路径
LOG_FILE = './logs/update_collection_{time}.log'  # 日志文件路径

USER_ID = 20180111  # 用户ID
REFRESH_TOKEN = 'xxxxxx'  # refresh_token

logs = StringIO()

collection = PixivCollection(REFRESH_TOKEN, DATA_FILE, PATH_ORIGINAL, PATH_LARGE, PATH_THUMBNAIL, LOG_FILE, logs)
if collection.api_available == False:
    print('PixivAPI初始化失败，程序退出')
    exit(1)
collection.download_bookmark(USER_ID, type='public', max_page=2)
collection.download_bookmark(USER_ID, type='private', max_page=2)
collection.match_images()
collection.generate_thumbnail(overwrite=False)
collection.generate_large(overwrite=False)
collection.clean_deleted_images()
collection.check(try_fix=True)
collection.save(DATA_FILE)

print('全部任务执行完成，程序结束')
