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
        logger.add(sys.stdout, level='INFO')
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

    def __get_illust_info(self, illust_id: int):
        '''获取插画信息'''
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
                    logger.info(f'获取插画{illust_id}信息失败,原因：{result["error"]["user_message"]}')
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
        self.__cache[f'illust_info_{illust_id}'] = result
        time.sleep(WAIT_TIME)
        return result

    def __get_user_info(self, user_id: int):
        '''获取用户信息'''
        result = {}
        retry = 0
        success = False
        while not success and retry <= MAX_RETRY:
            try:
                result = self.__api.user_detail(user_id)
                logger.debug(json.dumps(result))
                if result.get('error', None):
                    logger.info(f'获取用户{user_id}信息失败,原因：{result["error"]["user_message"]}')
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

    def __download_image(self, download_link: str):
        '''下载图片'''
        retry = 0
        success = False
        filename = download_link.split("/")[-1]
        logger.info(f'下载图片: {download_link}')
        while not success and retry <= 3:
            try:
                self.__api.download(download_link, path=f'{self.__path["original"]}', fname=filename)
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

    def __generate_image_preview(self, file: dict, size: tuple[int, int] = PREVIEW_SIZE):
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
        img.save(self.__path["preview"] + filename_preview, 'WEBP', quality=PREVIEW_QUALITY)

    def __generate_image_thumbnail(self, file: dict, size: tuple[int, int] = THUMBNAIL_SIZE):
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
        img.save(self.__path["thumbnail"] + filename_thumbnail, 'WEBP', quality=THUMBNAIL_QUALITY)

    def __update_data(self, data: dict, key: str | int, value: dict):
        '''更新数据'''
        data[str(key)] = {
            'update': timestamp(),
            'data': value,
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
            api.auth(refresh_token=refresh_token)
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

        logger.info(f'读取数据成功, 文件:{len(self.files)} 图片:{len(self.images)} 作者:{len(self.authors)} 标签:{len(self.tags)}')

    def save_data(self, file_path: str):
        '''保存数据'''
        self.authors = dict(sorted(self.authors.items(), key=lambda x: int(x[0])))
        self.images = dict(sorted(self.images.items(), key=lambda x: int(x[0])))
        self.files = dict(sorted(self.files.items(), key=lambda x: x[1]['data']['id'] * 1000 + x[1]['data']['part']))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                'authors': self.authors,
                'images': self.images,
                'tags': self.tags,
                'files': self.files,
            },
                      f,
                      indent=4,
                      ensure_ascii=False)
        logger.info(f'保存数据成功, 文件:{len(self.files)} 图片:{len(self.images)} 作者:{len(self.authors)} 标签:{len(self.tags)}')

    def download_bookmark(self, user_id: int, type='public', max_page=1):
        '''下载用户收藏'''
        download_list = []
        id_list = [int(image_id) for image_id in self.images]
        cur_page = 1
        next_url = None

        while cur_page <= max_page:
            logger.info(f'获取用户{user_id} {type}收藏第{cur_page}页')
            cur_page += 1
            qs = None
            images = []
            if next_url is not None:
                qs = self.__api.parse_qs(next_url)
            if qs:
                res = self.__api.user_bookmarks_illust(**qs)
                next_url = res['next_url']
                images = res['illusts']
            else:
                res = self.__api.user_bookmarks_illust(user_id, restrict=type)
                next_url = res['next_url']
                images = res['illusts']

            logger.debug(json.dumps(images))

            for image in images:
                # 跳过已被删除或设置为非公开的图片
                if image['visible'] == False:
                    logger.warning(f'图片{image["id"]}已被删除或设置为非公开,跳过下载')
                    continue
                if image['id'] not in id_list:
                    if image['page_count'] == 1:
                        image_link = image['meta_single_page']['original_image_url']
                        download_list.append(image['meta_single_page']['original_image_url'])
                    else:
                        for page in image['meta_pages']:
                            download_list.append(page['image_urls']['original'])

        if len(download_list) == 0:
            logger.info('没有需要下载的图片')
            return
        logger.info(f'开始下载{len(download_list)}张图片')

        for image_link in download_list:
            success = self.__download_image(image_link)
            if not success:
                logger.error(f'下载失败: {image_link},多次重试失败,跳过该图片')

    def generate_preview(self, overwrite=False, max_size=PREVIEW_SIZE):
        '''生成预览图'''
        for filename in self.files:
            file = self.files[filename]['data']
            if not os.path.exists(f'{self.__path["preview"]}{file["id"]}_p{file["part"]}.webp') or overwrite:
                logger.info(f'生成{file["id"]}_{file["part"]}大图')
                self.__generate_image_preview(file, max_size)

    def generate_thumbnail(self, overwrite=False, max_size=THUMBNAIL_SIZE):
        '''生成缩略图'''
        for filename in self.files:
            file = self.files[filename]['data']
            if not os.path.exists(f'{self.__path["thumbnail"]}{file["id"]}_p{file["part"]}.webp') or overwrite:
                logger.info(f'生成{file["id"]}_{file["part"]}预览图')
                self.__generate_image_thumbnail(file, max_size)

    def clean(self):
        '''清理无效数据'''
        for filename in self.files.copy():
            if not os.path.exists(self.__path['original'] + filename):
                logger.info(f'删除文件数据: {self.__path["original"]}{filename}')
                file = self.files[filename]['data']
                del self.files[filename]
                filename_preview = f'{file["id"]}_p{file["part"]}.webp'
                if os.path.exists(self.__path['preview'] + filename_preview):
                    logger.info(f'删除预览图文件: {self.__path["preview"]}{filename_preview}')
                    os.remove(self.__path['preview'] + filename_preview)
                filename_thumbnail = f'{file["id"]}_p{file["part"]}.webp'
                if os.path.exists(self.__path['thumbnail'] + filename_thumbnail):
                    logger.info(f'删除缩略图文件: {self.__path["thumbnail"]}{filename_thumbnail}')
                    os.remove(self.__path['thumbnail'] + filename_thumbnail)

        image_id_list = set([self.files[file]['data']['id'] for file in self.files])
        for image_id in self.images.copy():
            if int(image_id) not in image_id_list:
                logger.info(f'删除图片数据: {image_id}')
                del self.images[image_id]

        author_id_list = set([self.images[image_id]['data']['author_id'] for image_id in self.images])
        for author_id in self.authors.copy():
            if int(author_id) not in author_id_list:
                logger.info(f'删除作者数据: {author_id}')
                del self.authors[author_id]

        tag_name_list = set(
            [tag_name for image_id in self.images for tag_name in self.images[image_id]['data']['tags']])
        for tag_name in self.tags.copy():
            if tag_name not in tag_name_list:
                logger.info(f'删除标签数据: {tag_name}')
                del self.tags[tag_name]

    def update(self):
        '''更新图片数据'''
        image_files = os.listdir(self.__path['original'])

        for file in image_files:
            if file in self.files:
                continue
            image_id = int(file.split('_')[0])
            part = int(file.split('.')[0].split('p')[1])

            image_info = self.__get_illust_info(image_id)

            if image_info is None:
                logger.error(f'跳过{image_id}信息获取,原因：多次失败')

            logger.info(f'获取插画{image_id}信息成功')

            author_id = image_info['illust']['user']['id']

            image_obj = Image.open(self.__path['original'] + file)

            self.__update_data(
                self.files, file, {
                    'id': image_id,
                    'part': part,
                    'size': image_obj.size,
                    'ext': file.split('.')[-1],
                    'dominant_color': get_dominant_color(image_obj),
                })

            self.__update_data(
                self.images, image_id, {
                    'id': image_id,
                    'author_id': author_id,
                    'title': image_info['illust']['title'],
                    'tags': [tag["name"] for tag in image_info['illust']['tags']],
                    'created_at': image_info['illust']['create_date'],
                    'sanity_level': image_info['illust']['sanity_level'],
                    'x_restrict': image_info['illust']['x_restrict'],
                    'bookmark': image_info['illust']['total_bookmarks'],
                    'view': image_info['illust']['total_view'],
                })

            self.__update_data(
                self.authors, author_id, {
                    'id': author_id,
                    'name': image_info['illust']['user']['name'],
                    'account': image_info['illust']['user']['account'],
                })

            for tag in image_info['illust']['tags']:
                tag_name = tag['name']
                self.__update_data(self.tags, tag_name, tag)
        logger.info('图片数据更新完成')

    def check(self, try_fix=False, chexk_tag=False, check_title=False, check_bookmark=False, check_view=False):
        '''检查数据'''
        for filename in self.files:
            file = self.files[filename]['data']
            image_id = str(file['id'])

            # 检测无标签图片
            if chexk_tag and len(self.images[image_id]['data']['tags']) == 0:
                logger.warning(f'检测到无标签图片: {file["id"]}_{file["part"]}')

            # 检测无标题图片
            if check_title and self.images[image_id]['data']['title'] == '':
                logger.warning(f'检测到无标题图片: {file["id"]}_{file["part"]}')

            # 检测无搜藏数图片
            if check_bookmark and self.images[image_id]['data']['bookmark'] <= 0:
                logger.warning(f'检测到无搜藏数图片: {file["id"]}_{file["part"]}')

            # 检测无浏览数图片
            if check_view and self.images[image_id]['data']['view'] <= 0:
                logger.warning(f'检测到无浏览数图片: {file["id"]}_{file["part"]}')

            # 检测尺寸不匹配图片
            try:
                image_obj = Image.open(self.__path['original'] + filename)
                if image_obj.size[0] != file['size'][0] or image_obj.size[1] != file['size'][1]:
                    logger.warning(
                        f'检测到尺寸不匹配图片: {file["id"]}_{file["part"]}, 记录尺寸: {file["size"]}, 实际尺寸: {image_obj.size}')
                    if try_fix:
                        file['size'] = image_obj.size

                        # 重新生成预览图
                        if os.path.exists(f'{self.__path["preview"]}{file["id"]}_p{file["part"]}.webp'):
                            os.remove(f'{self.__path["preview"]}{file["id"]}_p{file["part"]}.webp')
                        logger.info(f'重新生成{file["id"]}_{file["part"]}预览图')
                        self.__generate_image_preview(file)

                        # 重新生成缩略图
                        if os.path.exists(f'{self.__path["thumbnail"]}{file["id"]}_p{file["part"]}.webp'):
                            os.remove(f'{self.__path["thumbnail"]}{file["id"]}_p{file["part"]}.webp')
                        logger.info(f'重新生成{file["id"]}_{file["part"]}缩略图')
                        self.__generate_image_thumbnail(file)

                        # 重新计算主色
                        logger.info(f'重新计算{file["id"]}_{file["part"]}主色')
                        file['dominant_color'] = get_dominant_color(image_obj)
            except Exception as e:
                logger.exception(e)
                logger.warning(f'检测到可能损坏的图片: {file["id"]}_{file["part"]}')

    def export(self, file_path: str, filter_max_sl: int = -1):
        '''导出数据'''
        result = []
        for file in self.files:
            image_id = str(self.files[file]['data']['id'])
            if filter_max_sl != -1:
                if self.images[image_id]['data']['sanity_level'] > filter_max_sl:
                    continue
            author_id = str(self.images[image_id]['data']['author_id'])
            image = {
                'id': self.files[file]['data']['id'],
                'part': self.files[file]['data']['part'],
                'title': self.images[image_id]['data']['title'],
                'size': self.files[file]['data']['size'],
                'ext': self.files[file]['data']['ext'],
                'author': self.authors[author_id]['data'],
                'tags': [self.tags[tag]['data'] for tag in self.images[image_id]['data']['tags']],
                'created_at': self.images[image_id]['data']['created_at'],
                'sanity_level': self.images[image_id]['data']['sanity_level'],
                'x_restrict': self.images[image_id]['data']['x_restrict'],
                'bookmark': self.images[image_id]['data']['bookmark'],
                'view': self.images[image_id]['data']['view'],
                'dominant_color': self.files[file]['data']['dominant_color'],
            }
            result.append(image)

        result.sort(key=lambda x: x['id'] * 1000 + 999 - x['part'], reverse=True)
        logger.info(f'导出{len(result)}条数据至 {file_path}')

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)