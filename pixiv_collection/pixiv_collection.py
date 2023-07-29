from io import StringIO
import sys, os, json, time

from loguru import logger
from pixivpy3 import *
from PIL import Image

from colorthief import ColorThief

IMAGE_DELETED = 'https://s.pximg.net/common/images/limit_unknown_360.png'
WAIT_TIME = 1.5
MAX_RETRY = 3
THUMBNAIL_SIZE = (500, 1000)
LARGE_SIZE = (2000, 2000)


def rgb2hex(rgbcolor):
    r, g, b = rgbcolor
    result = (r << 16) + (g << 8) + b
    return hex(result).replace('0x', '#')


class PixivCollection():

    def __init__(
        self,
        refresh_token,
        data_file,
        path_original,
        path_large,
        path_thumbnail,
        log_file: str = None,
        string_io: StringIO = None,
    ) -> None:
        self.__init_logger(log_file, string_io)
        self._cache = {}
        self.data_file = data_file
        self.path_original = path_original
        self.path_large = path_large
        self.path_thumbnail = path_thumbnail
        self.__init_pixivapi(refresh_token)
        self.api_available = True
        if self._api is None:
            self.api_available = False
        self.images = self.__read_json(data_file)

    def __init_logger(self, log_file: str, string_io: StringIO):
        '''初始化日志'''
        logger.remove(handler_id=None)
        logger.add(sys.stdout, level='INFO')
        if log_file:
            logger.add(log_file, level='DEBUG', encoding='utf-8')
        if string_io:
            logger.add(string_io, level='INFO')

    @staticmethod
    def __read_json(file_name) -> list[dict]:
        '''读取数据'''
        if not os.path.exists(file_name):
            return []
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def __write_json(data, file_name):
        '''写出数据'''
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info(f'写出数据成功，共{len(data)}条')

    def __init_pixivapi(self, refresh_token):
        '''初始化PixivAPI'''
        try:
            api = AppPixivAPI()
            api.auth(refresh_token=refresh_token)
            api.set_accept_language('zh-cn')
            logger.info('PixivAPI初始化成功')
            self._api = api
        except Exception as e:
            logger.exception(e)
            logger.error('PixivAPI初始化失败')
            return None

    def __filter_images_sl(self, images: list[dict], max_sanity_level: int):
        '''使用健全度过滤图片'''
        images_filtered = [image for image in images if image['sanity_level'] <= max_sanity_level]
        return images_filtered

    def __sort_images(self):
        '''排序图片'''
        # 按id降序排列，同id按part升序排列
        self.images.sort(key=lambda x: x['id'] * 1000 + 999 - x['part'], reverse=True)

    def __get_illust_info(self, illust_id: int):
        '''获取插画信息'''
        if self._cache.get(f'illust_info_{illust_id}'):
            return self._cache[f'illust_info_{illust_id}']
        result = {}
        retry = 0
        success = False
        while not success and retry <= MAX_RETRY:
            try:
                result = self._api.illust_detail(illust_id)
                logger.debug(json.dumps(result))
                if result.get('error', None):
                    logger.info(f'获取{illust_id}信息失败，原因：{result["error"]["user_message"]}')
                    return None
                if result.get('illust', None):
                    success = True
            except Exception as e:
                retry += 1
                logger.exception(e)
                if retry <= MAX_RETRY:
                    logger.error(f'获取{illust_id}信息失败，重试第{retry}次')
                time.sleep(WAIT_TIME)
        if not success:
            return None
        self._cache[f'illust_info_{illust_id}'] = result
        time.sleep(WAIT_TIME)
        return result

    def __download_image(self, download_link: str):
        '''下载图片'''
        retry = 0
        success = False
        filename = download_link.split("/")[-1]
        if not success and retry <= 3:
            try:
                logger.info(f'下载图片: {download_link}')
                self._api.download(download_link, path=f'{self.path_original}', fname=filename)
                # 检查图片完整性
                img = Image.open(f'{self.path_original}{filename}')
                img.load()
                img.close()
                success = True
            except Exception as e:
                if os.path.exists(f'{self.path_original}{filename}'):
                    os.remove(f'{self.path_original}{filename}')
                logger.exception(e)
                retry += 1
                if retry <= 3:
                    logger.info(f'下载失败，重试第{retry}次')
        return success

    def __generate_image_thumbnail(self, image: dict, size: tuple[int, int] = THUMBNAIL_SIZE):
        '''生成图片预览'''
        filename = f'{image["id"]}_p{image["part"]}.{image["ext"]}'
        filename_thumbnail = f'{image["id"]}_p{image["part"]}.webp'
        img = Image.open(self.path_original + filename)
        img.thumbnail(size)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new(img.mode[:-1], img.size, 'white')
            background.paste(img, img.split()[-1])
            img = background
        if img.mode == 'P':
            img = img.convert('RGB')
        img.save(self.path_thumbnail + filename_thumbnail, 'WEBP', quality=70)

    def __generate_image_large(self, image: dict, size: tuple[int, int] = THUMBNAIL_SIZE):
        '''生成图片大图'''
        filename = f'{image["id"]}_p{image["part"]}.{image["ext"]}'
        filename_large = f'{image["id"]}_p{image["part"]}.webp'
        img = Image.open(self.path_original + filename)
        img.thumbnail(size)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new(img.mode[:-1], img.size, 'white')
            background.paste(img, img.split()[-1])
            img = background
        if img.mode == 'P':
            img = img.convert('RGB')
        img.save(self.path_large + filename_large, 'WEBP', quality=80)

    @staticmethod
    def __get_dominant_color(img: Image.Image):
        dominant_color = ColorThief(img).get_color(quality=1)
        return rgb2hex(dominant_color)

    def download_bookmark(self, user_id, type='public', max_page=1):
        '''下载收藏夹图片'''
        download_list = []
        cur_page = 1
        next_url = None

        while cur_page <= max_page:
            logger.info(f'获取用户{user_id} {type}收藏第{cur_page}页')
            cur_page += 1
            qs = None
            images = []
            if next_url is not None:
                qs = self._api.parse_qs(next_url)
            if qs:
                res = self._api.user_bookmarks_illust(**qs)
                next_url = res['next_url']
                images = res['illusts']
            else:
                res = self._api.user_bookmarks_illust(user_id, restrict=type)
                next_url = res['next_url']
                images = res['illusts']

            logger.debug(json.dumps(images))

            for image in images:
                if image['page_count'] == 1:
                    image_link = image['meta_single_page']['original_image_url']
                    # 跳过已被删除或设置为非公开的图片
                    if image_link == IMAGE_DELETED:
                        logger.warning(f'图片{image["id"]}已被删除或设置为非公开，跳过下载')
                        continue
                    if not os.path.exists(f'{self.path_original}{image_link.split("/")[-1]}'):
                        download_list.append(image['meta_single_page']['original_image_url'])
                else:
                    # 仅下载所有页都不存在的图片
                    exist = False
                    for page in image['meta_pages']:
                        if os.path.exists(f'{self.path_original}{page["image_urls"]["original"].split("/")[-1]}'):
                            exist = True
                            break
                    if not exist:
                        for page in image['meta_pages']:
                            download_list.append(page['image_urls']['original'])

        if len(download_list) == 0:
            logger.info('没有需要下载的图片')
            return
        logger.info(f'开始下载{len(download_list)}张图片')

        for image_link in download_list:
            success = self.__download_image(image_link)
            if not success:
                logger.error(f'下载失败: {image_link}，多次重试失败，跳过该图片')

    def match_images(self):
        '''从Pixiv匹配图片信息'''
        images_id_list = [f'{image["id"]}_{image["part"]}' for image in self.images]

        # 读取目录下图片
        files = os.listdir(f'{self.path_original}')
        files.sort(key=lambda x: int(x.split('_')[0]), reverse=True)

        # 检测重复图片
        file_exist = []
        for file in files:
            if file.split('.')[0] in file_exist:
                logger.warning(f'检测到重复图片{file}')
            else:
                file_exist.append(file.split('.')[0])

        # 匹配图片数据
        for file in files:
            illust_id = int(file.split('_')[0])
            part = int(file.split('.')[0].split('p')[1])

            if f'{illust_id}_{part}' in images_id_list:
                continue

            # 获取图片信息
            result = self.__get_illust_info(illust_id)

            if result is None:
                logger.error(f'跳过{illust_id}信息获取，原因：多次失败')
                continue

            logger.info(f'获取{illust_id}_{part}信息成功')
            self.images.append({
                'id': illust_id,
                'part': part,
                'title': result['illust']['title'],
                'size': Image.open(f'{self.path_original}{file}').size,
                'ext': file.split('.')[-1],
                'author': {
                    'id': result['illust']['user']['id'],
                    'name': result['illust']['user']['name'],
                    'account': result['illust']['user']['account'],
                },
                'tags': result['illust']['tags'],
                'created_at': result['illust']['create_date'],
                'sanity_level': result['illust']['sanity_level'],
                'x_restrict': result['illust']['x_restrict'],
            })
        logger.info('图片数据匹配结束')
        self.__sort_images()

    def generate_thumbnail(self, overwrite=False, max_size=THUMBNAIL_SIZE):
        '''生成预览图'''
        for image in self.images:
            if not os.path.exists(f'{self.path_thumbnail}{image["id"]}_p{image["part"]}.webp') or overwrite:
                logger.info(f'生成{image["id"]}_{image["part"]}预览图')
                self.__generate_image_thumbnail(image, max_size)

    def generate_large(self, overwrite=False, max_size=LARGE_SIZE):
        '''生成预览图'''
        for image in self.images:
            if not os.path.exists(f'{self.path_large}{image["id"]}_p{image["part"]}.webp') or overwrite:
                logger.info(f'生成{image["id"]}_{image["part"]}大图')
                self.__generate_image_large(image, max_size)

    def clean_deleted_images(self):
        '''清理已删除的图片数据'''
        copy = self.images.copy()
        for image in copy:
            filename = f'{image["id"]}_p{image["part"]}.{image["ext"]}'
            filename_thumbnail = f'{image["id"]}_p{image["part"]}.webp'
            if not os.path.exists(f'{self.path_original}{filename}'):
                logger.info(f'删除数据,{image["id"]}_{image["part"]}，原因:图片已删除')
                self.images.remove(image)
                if os.path.exists(f'{self.path_thumbnail}{filename_thumbnail}'):
                    os.remove(f'{self.path_thumbnail}{filename_thumbnail}')
                if os.path.exists(f'{self.path_large}{filename_thumbnail}'):
                    os.remove(f'{self.path_large}{filename_thumbnail}')
        logger.info('图片数据清理结束')

    def fix_from_download_history(self, download_history_file: str):
        '''尝试从下载记录中修复数据'''
        logger.info('修复数据开始')
        history = self.__read_json(download_history_file)

        images_to_fix = []
        for image in self.images:
            if image['author']['id'] == 0:
                images_to_fix.append(image)
        logger.info(f'待修复图片{len(images_to_fix)}张')
        for image in images_to_fix:
            for history_image in history:
                if image['id'] == history_image['idNum']:
                    image['title'] = history_image['title']
                    image['author']['id'] = history_image['userId']
                    image['author']['name'] = history_image['user']
                    image['author']['account'] = history_image['user']
                    image['tags'] = []
                    for tag in history_image['tags']:
                        image['tags'].append({
                            'name': tag,
                            'translated_name': None,
                        })
                    image['created_at'] = history_image['date']
                    image['sanity_level'] = history_image['sl']
                    image['x_restrict'] = history_image['xRestrict']
                    logger.info(f'修复{image["id"]}_{image["part"]}数据成功')
                    break
        logger.info('修复数据结束')

    def check(self, try_fix=False):
        '''检查可能存在的问题'''
        index_images = {}
        for image in self.images:
            # 检测重复数据
            if index_images.get(image["id"] * 1000 + image["part"]):
                logger.warning(f'检测到可能重复的图片：{image["id"]}_{image["part"]}')
            else:
                index_images[image["id"] * 1000 + image["part"]] = 1

            # 检测无标签图片
            if len(image['tags']) == 0:
                logger.warning(f'检测到无标签的图片：{image["id"]}_{image["part"]}')
            # 检测无标题图片
            if image['title'] == '':
                logger.warning(f'检测到无标题的图片：{image["id"]}_{image["part"]}')

            # 检测尺寸不匹配的图片
            try:
                filename = f'{image["id"]}_p{image["part"]}.{image["ext"]}'
                filename_thumbnail = f'{image["id"]}_p{image["part"]}.webp'
                img = Image.open(self.path_original + filename)
                if img.size[0] != image['size'][0] or img.size[1] != image['size'][1]:
                    logger.warning(f'检测到尺寸不匹配的图片：{image["id"]}_{image["part"]}，记录尺寸：{image["size"]}，实际尺寸：{img.size}')
                    if try_fix:
                        image['size'] = img.size
                        logger.info(f'已修正图片{image["id"]}_{image["part"]}尺寸，{image["size"]}')
                        if os.path.exists(self.path_thumbnail + filename_thumbnail):
                            os.remove(self.path_thumbnail + filename_thumbnail)
                        logger.info(f'更新图片{image["id"]}_{image["part"]}预览图')
                        self.__generate_image_thumbnail(image)
                        if os.path.exists(self.path_large + filename_thumbnail):
                            os.remove(self.path_large + filename_thumbnail)
                        logger.info(f'更新图片{image["id"]}_{image["part"]}大图')
                        self.__generate_image_large(image)
                if image.get('dominant_color') is None:
                    color = self.__get_dominant_color(img)
                    logger.info(f'获取图片{image["id"]}_{image["part"]}主色：{color}')
                    image['dominant_color'] = color
            except:
                logger.warning(f'检测到可能损坏的图片：{image["id"]}_{image["part"]}')

    def save(self, filename: str, filter_max_sl: int = -1):
        '''保存数据'''
        data = self.images

        if filter_max_sl != -1:
            data = self.__filter_images_sl(data, filter_max_sl)

        self.__write_json(data, filename)
        logger.info(f'保存数据至{filename}文件，共{len(data)}条数据')
