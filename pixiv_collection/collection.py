import json
import os
import sys
import time
from io import StringIO

from loguru import logger
from pixivpy3 import AppPixivAPI
from PIL import Image

from colorthief import ColorThief

MAX_RETRY = 3
WAIT_TIME = 1.5
PREVIEW_SIZE = (2000, 2000)
THUMBNAIL_SIZE = (500, 1000)
PREVIEW_QUALITY = 80
THUMBNAIL_QUALITY = 70
LOG_FORMAT = '<g>[{time:YYYY-MM-DD HH:mm:ss.SSS}]</g> <lvl>[{level}] {message}</lvl>'


def timestamp():
    return int(time.time())


def rgb2hex(rgbcolor):
    r, g, b = rgbcolor
    result = (r << 16) + (g << 8) + b
    return hex(result).replace('0x', '#')


def get_dominant_color(img: Image.Image):
    dominant_color = ColorThief(img).get_color(quality=1)
    return rgb2hex(dominant_color)


class PixivCollection():

    def __init__(self):
        logger.remove(handler_id=None)
        logger.add(sys.stdout, level='INFO', format=LOG_FORMAT)
        self.__api = None
        self.__cache = {}
        self.__path = {
            'original': './image/original/',
            'preview': './image/preview/',
            'thumbnail': './image/thumbnail/',
        }
        self.authors = {}
        self.images = {}
        self.tags = {}
        self.files = {}

    def __get_illust_info(self, illust_id: int | str):
        '''API 获取插画信息'''

        illust_id = int(illust_id)
        if self.__cache.get(f'illust_info_{illust_id}'):
            return self.__cache[f'illust_info_{illust_id}']
        result = {}
        retry = 0
        success = False
        while not success and retry <= MAX_RETRY:
            try:
                result = self.__api.illust_detail(illust_id)
                logger.debug(json.dumps(result))
                if result.get('error', None):
                    logger.warning(
                        f'获取插画{illust_id}信息失败,原因: {result["error"]["user_message"]}'
                    )
                    return None
                if result.get('illust', None):
                    success = True
            except Exception as e:
                retry += 1
                logger.exception(e)
                if retry <= MAX_RETRY:
                    logger.error(f'获取插画{illust_id}信息失败,重试第{retry}次')
                time.sleep(WAIT_TIME)
        if not success:
            return None
        # 缓存插画信息
        self.__cache[f'illust_info_{illust_id}'] = result
        time.sleep(WAIT_TIME)
        return result

    def __get_user_info(self, user_id: int | str):
        '''API 获取用户信息'''

        user_id = int(user_id)
        result = {}
        retry = 0
        success = False
        while not success and retry <= MAX_RETRY:
            try:
                result = self.__api.user_detail(user_id)
                logger.debug(json.dumps(result))
                if result.get('error', None):
                    logger.info(
                        f'获取用户{user_id}信息失败,原因: {result["error"]["user_message"]}'
                    )
                    return None
                if result.get('user', None):
                    success = True
            except Exception as e:
                retry += 1
                logger.exception(e)
                if retry <= MAX_RETRY:
                    logger.error(f'获取用户{user_id}信息失败,重试第{retry}次')
                time.sleep(WAIT_TIME)
        if not success:
            return None
        time.sleep(WAIT_TIME)
        return result

    def __get_file_info(self, filename: str):
        '''获取图片文件信息'''

        file_path = self.__path['original'] + filename
        image_id = int(filename.split('_')[0])
        part = int(filename.split('.')[0].split('p')[1])
        ext = filename.split('.')[-1]
        image_obj = Image.open(file_path)
        size = image_obj.size
        dominant_color = get_dominant_color(image_obj)
        image_obj.close()
        return {
            'id': image_id,
            'part': part,
            'size': size,
            'ext': ext,
            'dominant_color': dominant_color,
        }

    def __download_image(self, download_link: str):
        '''下载图片'''

        retry = 0
        success = False
        filename = download_link.split("/")[-1]
        logger.info(f'下载图片: {download_link}')
        while not success and retry <= 3:
            try:
                self.__api.download(download_link,
                                    path=f'{self.__path["original"]}',
                                    fname=filename)
                # 检查图片完整性
                img = Image.open(f'{self.__path["original"]}{filename}')
                img.load()
                img.close()
                success = True
            except Exception as e:
                if os.path.exists(f'{self.__path["original"]}{filename}'):
                    os.remove(f'{self.__path["original"]}{filename}')
                logger.exception(e)
                retry += 1
                if retry <= 3:
                    logger.info(f'下载失败,重试第{retry}次')
        return success

    def __generate_image_preview(self,
                                 file: dict,
                                 size: tuple[int, int] = PREVIEW_SIZE):
        '''生成图片预览图'''

        filename = f'{file["id"]}_p{file["part"]}.{file["ext"]}'
        filename_preview = f'{file["id"]}_p{file["part"]}.webp'
        img = Image.open(self.__path["original"] + filename)
        img.thumbnail(size)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new(img.mode[:-1], img.size, 'white')
            background.paste(img, img.split()[-1])
            img = background
        if img.mode == 'P':
            img = img.convert('RGB')
        img.save(self.__path["preview"] + filename_preview,
                 'WEBP',
                 quality=PREVIEW_QUALITY)

    def __generate_image_thumbnail(self,
                                   file: dict,
                                   size: tuple[int, int] = THUMBNAIL_SIZE):
        '''生成图片缩略图'''

        filename = f'{file["id"]}_p{file["part"]}.{file["ext"]}'
        filename_thumbnail = f'{file["id"]}_p{file["part"]}.webp'
        img = Image.open(self.__path["original"] + filename)
        img.thumbnail(size)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new(img.mode[:-1], img.size, 'white')
            background.paste(img, img.split()[-1])
            img = background
        if img.mode == 'P':
            img = img.convert('RGB')
        img.save(self.__path["thumbnail"] + filename_thumbnail,
                 'WEBP',
                 quality=THUMBNAIL_QUALITY)

    def __delete_image_preview(self, file: dict):
        '''删除图片预览图'''

        filename_preview = f'{file["id"]}_p{file["part"]}.webp'
        if os.path.exists(self.__path['preview'] + filename_preview):
            logger.info(f'删除预览图: {self.__path["preview"]}{filename_preview}')
            os.remove(self.__path['preview'] + filename_preview)

    def __delete_image_thumbnail(self, file: dict):
        '''删除图片缩略图'''

        filename_thumbnail = f'{file["id"]}_p{file["part"]}.webp'
        if os.path.exists(self.__path['thumbnail'] + filename_thumbnail):
            logger.info(
                f'删除缩略图: {self.__path["thumbnail"]}{filename_thumbnail}')
            os.remove(self.__path['thumbnail'] + filename_thumbnail)

    def __update_data(self, type: str, key: str | int, value: dict):
        '''更新数据'''
        logger.debug(f'更新数据: {type}:{key}')
        if type == 'author':
            self.authors[str(key)] = {
                'update': timestamp(),
                'data': value,
            }
        elif type == 'image':
            self.images[str(key)] = {
                'update': timestamp(),
                'data': value,
            }
        elif type == 'tag':
            self.tags[str(key)] = {
                'update': timestamp(),
                'data': value,
            }
        elif type == 'file':
            self.files[str(key)] = {
                'update': timestamp(),
                'data': value,
            }
        else:
            logger.error(f'未知数据类型: {type}')

    def __size_match(self, size1: tuple[int, int], size2: tuple[int, int]):
        '''判断尺寸是否匹配'''

        return size1[0] == size2[0] and size1[1] == size2[1]

    def convert_image_info(self, image_info: dict):
        return {
            'id': image_info['id'],
            'author_id': image_info['user']['id'],
            'title': image_info['title'],
            'tags': [tag["name"] for tag in image_info['tags']],
            'created_at': image_info['create_date'],
            'sanity_level': image_info['sanity_level'],
            'x_restrict': image_info['x_restrict'],
            'bookmark': image_info['total_bookmarks'],
            'view': image_info['total_view'],
        }

    def add_logger(self, target, level='INFO'):
        if isinstance(target, str):
            logger.add(target, level=level, encoding='utf-8')
        if isinstance(target, StringIO):
            logger.add(target, level=level)

    def set_path(self, path: dict):
        '''设置图片存储路径'''
        for key in path:
            path[key] = path[key].replace('\\', '/')
            if not os.path.exists(path[key]):
                os.makedirs(path[key])
            if path[key][-1] != '/':
                path[key] += '/'
        self.__path = path

    def init(self, refresh_token):
        '''初始化PixivAPI'''

        try:
            api = AppPixivAPI()
            logger.debug(api.auth(refresh_token=refresh_token))
            api.set_accept_language('zh-cn')
            logger.info('PixivAPI初始化成功')
            self.__api = api
            return True
        except Exception as e:
            logger.exception(e)
            logger.error('PixivAPI初始化失败')
            self.__api = None
            return None

    def read_data(self, file_path: str):
        '''读取数据'''

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

            self.authors = data['authors']
            self.images = data['images']
            self.tags = data['tags']
            self.files = data['files']

        logger.info(
            f'读取数据成功, 文件:{len(self.files)} 图片:{len(self.images)} 作者:{len(self.authors)} 标签:{len(self.tags)}'
        )

    def save_data(self, file_path: str):
        '''保存数据'''

        self.authors = dict(
            sorted(self.authors.items(), key=lambda x: int(x[0])))
        self.images = dict(sorted(self.images.items(),
                                  key=lambda x: int(x[0])))
        self.files = dict(
            sorted(self.files.items(),
                   key=lambda x: x[1]['data']['id'] * 1000 + x[1]['data'][
                       'part']))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    'authors': self.authors,
                    'images': self.images,
                    'tags': self.tags,
                    'files': self.files,
                },
                f,
                indent=4,
                ensure_ascii=False)
        logger.info(
            f'保存数据成功, 文件:{len(self.files)} 图片:{len(self.images)} 作者:{len(self.authors)} 标签:{len(self.tags)}'
        )

    def download_bookmark(self,
                          user_id: int,
                          type='public',
                          max_page=1,
                          update_image_data=True):
        '''下载用户收藏'''

        download_list = []
        local_files = os.listdir(self.__path['original'])
        id_list = [int(filename.split('_')[0]) for filename in local_files]
        cur_page = 1
        next_url = None

        while cur_page <= max_page:
            logger.info(f'获取用户{user_id} {type}收藏第{cur_page}页')
            cur_page += 1
            images = []
            if next_url:
                qs = self.__api.parse_qs(next_url)
                res = self.__api.user_bookmarks_illust(**qs)
            else:
                res = self.__api.user_bookmarks_illust(user_id, restrict=type)
            next_url = res['next_url']
            images = res['illusts']

            logger.debug(json.dumps(images))

            for image in images:
                # 跳过动图
                if image['type'] != 'illust':
                    continue
                # 跳过已被删除或设置为非公开的图片
                if image['visible'] == False:
                    logger.warning(f'图片{image["id"]}已被删除或设置为非公开,跳过下载')
                    continue
                # 缓存插画信息
                self.__cache[f'illust_info_{image["id"]}'] = {'illust': image}
                if image['id'] in id_list:
                    if update_image_data:
                        # 更新图片数据
                        self.__update_data('image', image['id'],
                                           self.convert_image_info(image))
                        self.__update_data(
                            'author', image['user']['id'], {
                                'id': image['user']['id'],
                                'name': image['user']['name'],
                                'account': image['user']['account'],
                            })
                        for tag in image['tags']:
                            tag_name = tag['name']
                            self.__update_data('tag', tag_name, tag)
                else:
                    # 判断是否为多图
                    if image['page_count'] == 1:
                        download_list.append(
                            image['meta_single_page']['original_image_url'])
                    else:
                        for page in image['meta_pages']:
                            download_list.append(
                                page['image_urls']['original'])

            if next_url is None:
                break

            time.sleep(WAIT_TIME)

        if len(download_list) == 0:
            logger.info('没有需要下载的图片')
            return
        logger.info(f'开始下载{len(download_list)}张图片')

        for image_link in download_list:
            success = self.__download_image(image_link)
            if not success:
                logger.error(f'下载失败: {image_link}, 多次重试失败, 跳过该图片')

    def generate_preview(self, overwrite=False, max_size=PREVIEW_SIZE):
        '''生成预览图'''

        for filename in self.files:
            file = self.files[filename]['data']
            if not os.path.exists(
                    f'{self.__path["preview"]}{file["id"]}_p{file["part"]}.webp'
            ) or overwrite:
                logger.info(f'生成大图: {file["id"]}_{file["part"]}')
                self.__generate_image_preview(file, max_size)

    def generate_thumbnail(self, overwrite=False, max_size=THUMBNAIL_SIZE):
        '''生成缩略图'''

        for filename in self.files:
            file = self.files[filename]['data']
            if not os.path.exists(
                    f'{self.__path["thumbnail"]}{file["id"]}_p{file["part"]}.webp'
            ) or overwrite:
                logger.info(f'生成预览图: {file["id"]}_{file["part"]}')
                self.__generate_image_thumbnail(file, max_size)

    def clean(self):
        '''清理无效数据'''

        image_id_list = set(
            [self.files[file]['data']['id'] for file in self.files])
        for image_id in self.images.copy():
            if int(image_id) not in image_id_list:
                logger.info(f'删除图片数据: {image_id}')
                del self.images[image_id]

        author_id_list = set([
            self.images[image_id]['data']['author_id']
            for image_id in self.images
        ])
        for author_id in self.authors.copy():
            if int(author_id) not in author_id_list:
                logger.info(f'删除作者数据: {author_id}')
                del self.authors[author_id]

        tag_name_list = set([
            tag_name for image_id in self.images
            for tag_name in self.images[image_id]['data']['tags']
        ])
        for tag_name in self.tags.copy():
            if tag_name not in tag_name_list:
                logger.info(f'删除标签数据: {tag_name}')
                del self.tags[tag_name]

    def diff(self):
        '''检测文件变动'''

        local_files = os.listdir(self.__path['original'])

        # 检测冲突文件
        index = {}
        for filename in local_files:
            filename, ext = filename.split('.')
            if filename not in index:
                index[filename] = []
            index[filename].append(ext)
        for filename in index:
            if len(index[filename]) > 1:
                # 手动解决冲突
                logger.warning(f'检测到冲突文件')
                for idx, ext in enumerate(index[filename]):
                    file_path = f'{self.__path["original"]}{filename}.{ext}'
                    im = Image.open(file_path)
                    print(
                        f'[{idx}] {filename}.{ext} {im.size} {os.path.getsize(file_path)}'
                    )
                    im.close()
                try:
                    select = int(input('请选择要保留的文件，默认为第0项: '))
                    if select < 0 or select >= len(index[filename]):
                        select = 0
                except:
                    select = 0
                logger.info(
                    f'保留文件 [{select}]: {filename}.{index[filename][select]}')
                for idx, ext in enumerate(index[filename]):
                    if idx != select:
                        file_path = f'{self.__path["original"]}{filename}.{ext}'
                        logger.info(f'删除文件 [{idx}]: {filename}.{ext}')
                        local_files.remove(f'{filename}.{ext}')
                        os.remove(file_path)

        # 检测删除文件
        for filename in self.files.copy():
            if filename not in local_files:
                logger.warning(f'检测到删除文件: {filename}')
                file_info = self.files[filename]['data']
                del self.files[filename]
                self.__delete_image_preview(file_info)
                self.__delete_image_thumbnail(file_info)

        # 检测新增文件
        for filename in local_files:
            if filename not in self.files:
                logger.info(f'检测到新增文件: {filename}')
                file_info = self.__get_file_info(filename)
                self.__update_data('file', filename, file_info)

        # 检测变动文件
        for filename in self.files:
            file = self.files[filename]['data']
            image_obj = Image.open(self.__path['original'] + filename)
            file_act_size = image_obj.size
            image_obj.close()
            if not self.__size_match(file['size'], file_act_size):
                logger.info(f'检测到尺寸变动文件: {filename}')
                file_info = self.__get_file_info(filename)
                self.__update_data('file', filename, file_info)
                self.__delete_image_preview(file_info)
                self.__delete_image_thumbnail(file_info)

    def update(self):
        '''更新图片数据'''
        for filename in self.files:
            image_id = filename.split('_')[0]
            if image_id in self.images:
                continue

            image_info = self.__get_illust_info(image_id)

            if image_info is None:
                logger.error(f'获取插画信息失败: {image_id}')
                continue

            logger.info(f'获取插画信息成功: {image_id}')

            author_id = image_info['illust']['user']['id']

            self.__update_data('image', image_id,
                               self.convert_image_info(image_info['illust']))

            self.__update_data(
                'author', author_id, {
                    'id': author_id,
                    'name': image_info['illust']['user']['name'],
                    'account': image_info['illust']['user']['account'],
                })

            for tag in image_info['illust']['tags']:
                tag_name = tag['name']
                self.__update_data('tag', tag_name, tag)
        logger.info('图片数据更新完成')

    def check(self,
              chexk_tag=False,
              check_title=False,
              check_bookmark=False,
              check_view=False):
        '''检查数据'''
        for filename in self.files:
            file = self.files[filename]['data']
            image_id = str(file['id'])

            # 检测无标签图片
            if chexk_tag:
                if len(self.images[image_id]['data']['tags']) == 0:
                    logger.warning(f'检测到无标签图片: {file["id"]}_{file["part"]}')

            # 检测无标题图片
            if check_title:
                if self.images[image_id]['data']['title'] == '':
                    logger.warning(f'检测到无标题图片: {file["id"]}_{file["part"]}')

            # 检测无搜藏数图片
            if check_bookmark:
                if self.images[image_id]['data']['bookmark'] <= 0:
                    logger.warning(f'检测到无搜藏数图片: {file["id"]}_{file["part"]}')

            # 检测无浏览数图片
            if check_view:
                if self.images[image_id]['data']['view'] <= 0:
                    logger.warning(f'检测到无浏览数图片: {file["id"]}_{file["part"]}')

    def export(self, file_path: str, filter_max_sl: int = -1):
        '''导出数据'''
        result = []
        for file in self.files:
            image_id = str(self.files[file]['data']['id'])
            if filter_max_sl != -1:
                if self.images[image_id]['data'][
                        'sanity_level'] > filter_max_sl:
                    continue
            author_id = str(self.images[image_id]['data']['author_id'])
            image = {
                'id':
                self.files[file]['data']['id'],
                'part':
                self.files[file]['data']['part'],
                'title':
                self.images[image_id]['data']['title'],
                'size':
                self.files[file]['data']['size'],
                'ext':
                self.files[file]['data']['ext'],
                'author':
                self.authors[author_id]['data'],
                'tags': [
                    self.tags[tag]['data']
                    for tag in self.images[image_id]['data']['tags']
                ],
                'created_at':
                self.images[image_id]['data']['created_at'],
                'sanity_level':
                self.images[image_id]['data']['sanity_level'],
                'x_restrict':
                self.images[image_id]['data']['x_restrict'],
                'bookmark':
                self.images[image_id]['data']['bookmark'],
                'view':
                self.images[image_id]['data']['view'],
                'dominant_color':
                self.files[file]['data']['dominant_color'],
            }
            result.append(image)

        result.sort(key=lambda x: x['id'] * 1000 + 999 - x['part'],
                    reverse=True)
        logger.info(f'导出{len(result)}条数据至 {file_path}')

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
