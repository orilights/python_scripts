import re, json, os

import requests
from loguru import logger

DATA_FILE = './version.json'

NETEASE_API = {
    'Windows': 'https://music.163.com/api/pc/package/download/latest',
    'Android_32': 'https://music.163.com/api/android/download/latest',
    'Android_3264': 'https://music.163.com/api/android/download/latest2',
    'Mac': 'https://music.163.com/api/osx/download/latest'
}

VERSION_PATTERN = '_(\d+\.\d+\.\d+\.\d+)'
VERSION_PATTERN_MAC = '_(\d+\.\d+\.\d+\_\d+)'


def check_version(platform):
    if platform not in NETEASE_API:
        logger.warning(f'平台 {platform} 不存在')
        return

    api = NETEASE_API[platform]
    flag_new_version = 0
    new_version = ''
    file_url = ''
    data = {}

    try:
        res = requests.get(url=api, allow_redirects=False)
        logger.debug(f'request {api}, status code: {res.status_code}')
        if res.ok and res.status_code == 302:
            file_url = res.headers['Location']
            logger.debug(f'latest file url: {file_url}')
            pattern = VERSION_PATTERN
            if platform == 'Mac':
                pattern = VERSION_PATTERN_MAC
            version_str = re.findall(pattern, file_url)[0]
            server_version = version_str.rsplit('.', 1)
            if platform == 'Mac':
                server_version = version_str.rsplit('_', 1)
            server_version_name = server_version[0]
            server_version_code = int(server_version[1])
            logger.info(f'[{platform}] 服务器版本: {server_version_name}[{server_version_code}]')

            if os.path.exists(DATA_FILE):
                data = json.loads(open(DATA_FILE, 'r').read())
            if platform not in data:
                flag_new_version = 1
                logger.info(f'[{platform}] 本地版本: 无数据')
                new_version = f'{server_version_name}[{server_version_code}]'
            else:
                local_version_name = data[platform]['versionName']
                local_version_code = data[platform]['versionCode']
                logger.info(f'[{platform}] 本地版本: {local_version_name}[{local_version_code}]')

                if local_version_code < server_version_code:
                    flag_new_version = 1
                    new_version = f'{server_version_name}[{server_version_code}]'
                else:
                    logger.info(f'[{platform}] 未检测到新版本')
        else:
            logger.warning('获取新版本错误，请检查网络')
    except Exception as e:
        logger.warning('获取新版本错误，请检查配置')
        logger.error(e)

    if flag_new_version == 1:
        logger.info(f'[{platform}] 检测到新版本: {new_version}')
        logger.info(f'[{platform}] 新版本链接: {file_url}')
        data[platform] = {
            'versionName': server_version_name,
            'versionCode': server_version_code,
            'download': file_url,
        }
        open(DATA_FILE, 'w').write(json.dumps(data, indent=4))


if __name__ == '__main__':

    for platform in NETEASE_API:
        check_version(platform)
