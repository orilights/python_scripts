import os
import re
import shutil
from datetime import datetime, timedelta

from loguru import logger
from tqdm import tqdm


def get_log_date(log_line):
    date_pattern = r'\[(.*?)\]'
    date_match = re.search(date_pattern, log_line)

    if date_match:
        date_str = date_match.group(1)
        return datetime.strptime(date_str, "%d/%b/%Y:%H:%M:%S %z").date()
    else:
        return None


def split_file(log_file, save_dir, remain_days=7):
    '''
    将日志文件按照日期切分，并清理过期的日志文件
    :param log_file: 日志文件路径
    :param save_dir: 历史日志保存目录
    :param remain_days: 历史日志保留天数
    '''
    # 获取当前日期
    current_date = datetime.now().date()
    filename = os.path.basename(log_file)

    # 复制一份日志文件并删除原日志文件
    logger.info(f"复制日志文件 {filename}")
    shutil.copyfile(log_file, f"{log_file}.tmp")
    os.remove(log_file)

    # 向 nginx master 进程发送 USR1 信号，要求 nginx 重新打开日志文件
    os.system("kill -USR1 $(ps aux | grep nginx | grep master | awk '{print $2}')")

    # 创建日志保存目录
    os.makedirs(save_dir, exist_ok=True)
    logger.info(f'开始切割日志文件 {filename}')
    # 遍历日志文件
    with open(f'{log_file}.tmp', 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc='切割日志'):
            # 获取改行日志的日期
            log_date = get_log_date(line)

            if log_date:
                # 获取日志的年份和月份，用于创建子目录
                year_month = log_date.strftime('%Y-%m')
                log_subdir = os.path.join(save_dir, year_month)

                # 创建日志保存目录
                os.makedirs(log_subdir, exist_ok=True)

                # 构造新的日志文件路径
                new_log_file = f"{filename.rsplit('.', maxsplit=1)[0]}_{log_date}.log"
                new_log_file_path = os.path.join(log_subdir, new_log_file)

                # 将日志行写入对应的日志文件
                with open(new_log_file_path, 'a', encoding='utf-8') as new_log_file:
                    new_log_file.write(line)
    os.remove(f"{log_file}.tmp")
    logger.info(f'日志文件切割完成')

    # 清理过期的日志文件
    logger.info(f'开始清理过期日志文件, 保留天数: {remain_days}')
    for subdir in os.listdir(save_dir):
        subdir_path = os.path.join(save_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue

        for log_file in os.listdir(subdir_path):
            log_file_date_str = log_file.rsplit("_")[1].split(".")[0]
            log_file_date = datetime.strptime(log_file_date_str, "%Y-%m-%d").date()
            if current_date - log_file_date > timedelta(days=remain_days):
                logger.info(f'删除过期日志文件: {log_file}')
                os.remove(os.path.join(subdir_path, log_file))
    logger.info(f'过期日志文件清理完成')


def spilt_folder(folder_path, save_dir, remain_days=7):
    '''
    将日志文件夹下的所有日志文件按照日期切分，并清理过期的日志文件
    :param folder_path: 日志文件夹路径
    :param save_dir: 历史日志保存目录
    :param remain_days: 历史日志保留天数
    '''
    for file in os.listdir(folder_path):
        log_file = os.path.join(folder_path, file)
        # 仅处理 .log 结尾的日志文件
        if not os.path.isfile(log_file):
            continue
        if not file.endswith('.log'):
            continue
        log_name = file.rsplit('.', maxsplit=1)[0]
        log_save_dir = os.path.join(save_dir, log_name)
        split_file(log_file, log_save_dir, remain_days)
