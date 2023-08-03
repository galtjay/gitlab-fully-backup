import wecom
from configparser import ConfigParser
import os
from minio import Minio
from datetime import datetime, timedelta
import time
import shutil
import subprocess
import logging

# 初始化minio实例：client , 完整的API使用文档：https://min.io/docs/minio/linux/developers/python/API.html
config = ConfigParser()
config.read("config.txt")
MINIO_ENDPOINT = config.get("MINIO", "MINIO_ENDPOINT")
MINIO_ACCESS_KEY = config.get("MINIO", "MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = config.get("MINIO", "MINIO_SECRET_KEY")
GITLAB_BUCKET_NAME = config.get("MINIO", "GITLAB_BUCKET_NAME")

LOCAL_STORE_DAYS = config.get("BACKUP", "LOCAL_STORE_DAYS")
MINIO_STORE_DAYS = config.get("BACKUP", "MINIO_STORE_DAYS")

client = Minio(MINIO_ENDPOINT,
               access_key=MINIO_ACCESS_KEY,
               secret_key=MINIO_SECRET_KEY,
               secure=False)  # Set to True if using HTTPS
# 初始化企业微信机器人实例
wecombot = wecom.WeComBot()
today_str = datetime.now().date().strftime("%Y%m%d")
today_dir = "/var/opt/gitlab/backups/gitlab_backup_" + today_str

# 初始化日志
logging.basicConfig(
    filename='backup.log',  # 指定输出文件的名称
    level=logging.DEBUG,  # 设置日志记录级别，debug info warning error critical
    format='%(asctime)s - %(levelname)s - %(message)s'  # 设置日志输出格式
)

# 在/var/opt/gitlab/backups/中创建YYYYMMDD的文件夹
os.makedirs(today_dir, exist_ok=True)


## 备份总共包含4个部分：1.gitlab数据 2.gitlab配置 3./etc/ssh文件 4./var/opt/gitlab/.ssh/authorized_keys 文件

# gitlab数据 执行gitlab-backup create STRATEGY=copy  将会在本地/var/opt/gitlab/backups/ 中产生一个tar包
# 将tar包移动至/var/opt/gitlab/backups/today_dir中
def bak_gitlabdata():
    try:
        result = subprocess.run("gitlab-backup create STRATEGY=copy", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            file_name_prefix = result.stdout.splitlines()[-2].split()[5]
            file_path = "/var/opt/gitlab/backups/" + file_name_prefix + "_gitlab_backup.tar"
            destination_path = today_dir + "/" + file_name_prefix + "_gitlab_backup.tar"
            shutil.move(file_path, destination_path)
            if os.path.exists(destination_path):
                logging.info("Gitlab data backup success!")
                return True
            else:
                logging.error(f"{file_path} move failed")
                return False
        else:
            logging.error(f"Gitlab data backup failed,error code：{result.returncode}")
            # 输出命令的错误输出结果
            logging.error(result.stderr)
            return False
    except Exception as e:
        logging.error(f"Gitlab data backup failed:{e}")
        return False


# gitlab配置 执行gitlab-ctl backup-etc --backup-path /var/opt/gitlab/backups/today_dir
# 例如：gitlab-ctl backup-etc --backup-path /var/opt/gitlab/backups/gitlab_backup_20230731
# 将直接生成一个tar包

def bak_gitlab_conf():
    try:
        result = subprocess.run("gitlab-ctl backup-etc --backup-path " + today_dir, shell=True, capture_output=True,
                                text=True)
        if result.returncode == 0:
            logging.info("Gitlab config files backup success!")
            return True
        else:
            logging.error(f"Gitlab config files backup failed,error code：{result.returncode}")
            # 输出命令的错误输出结果
            logging.error(result.stderr)
            return False
    except Exception as e:
        logging.error(f"Gitlab config files backup failed:{e}")
        return False


# /etc/ssh/*
# etc_ssh = os.listdir("/etc/ssh/")
# print(today_str)

def bak_ssh_conf():
    command = "tar -cf " + today_dir + "/gitlab_sshconf_backup" + today_str + ".tar /etc/ssh/"
    try:
        result = subprocess.run(command, shell=True, capture_output=True,
                                text=True)
        if result.returncode == 0:
            logging.info("Gitlab ssh config files backup success!")
            return True
        else:
            logging.error(f"Gitlab ssh config files backup failed,error code：{result.returncode}")
            # 输出命令的错误输出结果
            logging.error(result.stderr)
            return False
    except Exception as e:
        logging.error(f"Gitlab ssh config files backup failed:{e}")
        return False


# /var/opt/gitlab/.ssh/authorized_keys
def bak_authorized_keys():
    try:
        shutil.copy("/var/opt/gitlab/.ssh/authorized_keys", today_dir)
        logging.info(f"Gitlab authorized_keys backup success")
        return True
    except Exception as e:
        logging.error(f"Gitlab authorized_keys backup failed:{e}")
        return False


def upload_folder_to_minio(client, bucket_name, folder_path):
    start = '/var/opt/gitlab/backups/'
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            object_name = os.path.relpath(file_path, start)
            # print(file_path, object_name)
            try:
                client.fput_object(bucket_name, object_name, file_path)
                logging.info(f"已上传文件：{file_path} 到MinIO存储桶：{bucket_name} 的对象：{object_name}")
            except Exception as e:
                logging.error(f"上传文件：{file_path} 失败 - {e}")
                return False
    return True


def get_folder_size(folder_path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            total_size += os.path.getsize(file_path)
    return total_size


def get_previous_days(start_date, num_days):
    date_format = '%Y%m%d'
    start_date = datetime.strptime(start_date, date_format)
    # 创建一个空列表来存储结果日期
    result_dates = []
    # 循环推算指定天数的日期，并添加到结果列表中
    for i in range(num_days):
        previous_date = start_date - timedelta(days=i)
        result_dates.append(previous_date.strftime(date_format))

    return result_dates


def remove_files_not_in_list(folder_path, name_list):
    # 获取文件夹下的所有第一级文件和文件夹的名称
    entries = os.listdir(folder_path)
    for entry in entries:
        entry_path = os.path.join(folder_path, entry)
        # 判断当前文件或文件夹的名称是否不在给定的列表中
        if entry not in name_list:
            try:
                # 如果不在列表中，删除文件或文件夹
                if os.path.isfile(entry_path):
                    os.remove(entry_path)
                elif os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                logging.info(f"已删除：{entry_path}")
                print(f"已删除：{entry_path}")
            except Exception as e:
                logging.error(f"删除失败：{entry_path} - {e}")
                print(f"删除失败：{entry_path} - {e}")


def remove_objects_not_in_list(client, bucket_name, name_list):
    # 获取存储桶中的所有对象
    objects = client.list_objects(bucket_name, prefix='', recursive=True)
    for obj in objects:
        object_name = obj.object_name
        name = object_name.split('/')[0]
        # 判断当前对象名是否不在给定的列表中
        if name not in name_list:
            try:
                # 删除对象
                client.remove_object(bucket_name, object_name)
                logging.info(f"已删除：{object_name}")
                print(f"已删除：{object_name}")
            except Exception as e:
                logging.error(f"删除失败：{object_name} - {e}")
                print(f"删除失败：{object_name} - {e}")


def manage_backups():
    local_list = get_previous_days(today_str, int(LOCAL_STORE_DAYS))
    minio_list = get_previous_days(today_str, int(MINIO_STORE_DAYS))
    local_file_list = ['gitlab_backup_' + date for date in local_list]
    minio_file_list = ['gitlab_backup_' + date for date in minio_list]
    remove_files_not_in_list("/var/opt/gitlab/backups/", local_file_list)
    remove_objects_not_in_list(client, GITLAB_BUCKET_NAME, minio_file_list)
    local_now = os.listdir("/var/opt/gitlab/backups/")
    minio_now = []
    for obj in client.list_objects(GITLAB_BUCKET_NAME, prefix='/', recursive=False):
        minio_now.append(obj.object_name.split('/')[0])
    return local_now, minio_now


def backup():
    start_time = time.time()
    text_markdown = "# Gitlab备份情况(" + today_str + "):\n"
    if bak_gitlabdata():
        text_markdown = text_markdown + " 1. Gitlab_data: 备份成功。\n"
    else:
        text_markdown = text_markdown + " 1. Gitlab_data: 备份失败！\n"

    if bak_gitlab_conf():
        text_markdown = text_markdown + " 2. Gitlab_config: 备份成功。\n"
    else:
        text_markdown = text_markdown + " 2. Gitlab_config: 备份失败！\n"

    if bak_ssh_conf():
        text_markdown = text_markdown + " 3. SSH_config: 备份成功。\n"
    else:
        text_markdown = text_markdown + " 3. Gitlab_config: 备份失败！\n"

    if bak_authorized_keys():
        uncommented_lines = 0
        with open(today_dir + "/authorized_keys", 'r') as file:
            for line in file:
                if not line.strip().startswith('#'):
                    uncommented_lines += 1
        text_markdown = text_markdown + " 4. Authorized_keys: 备份成功，目前有效的公钥数：" + str(
            uncommented_lines) + " 。\n"
    else:
        text_markdown = text_markdown + " 4. Gitlab_config: 备份失败！\n"
    # print(today_dir)
    size_bytes = get_folder_size(today_dir)
    size_mb = size_bytes / (1024 * 1024)
    size_gb = size_bytes / (1024 * 1024 * 1024)

    if upload_folder_to_minio(client, GITLAB_BUCKET_NAME, today_dir):
        # text_markdown = text_markdown + f"{today_dir}上传至MINIO成功。\n"
        pass
    else:
        text_markdown = text_markdown + f"{today_dir}上传至MINIO失败!!!\n"

    r = manage_backups()
    local_list = str(r[0]).strip("[").strip("]")
    minio_list = str(r[1]).strip("[").strip("]")
    text_markdown = text_markdown + "------\n"
    text_markdown = text_markdown + f"**目前配置的历史备份冗余规则为：本地服务器存放{LOCAL_STORE_DAYS}天，MINIO存放{MINIO_STORE_DAYS}天，备份数据存放情况如下：**\n"
    text_markdown = text_markdown + f" 1. 本地服务器上存放的备份数据：<font color=\"info\">{local_list}</font>。\n"
    text_markdown = text_markdown + f" 2. MINIO上存放的备份数据：<font color=\"info\">{minio_list}</font>。\n"
    text_markdown = text_markdown + f" 3. 本地备份位于rails主节点/var/opt/gitlab/backups下，远程备份位于MINIO上{GITLAB_BUCKET_NAME}桶中。 \n"
    text_markdown = text_markdown + f" 4. 备份日志为backup.log，位于主程序同级目录。 \n"

    end_time = time.time()
    elapsed_time = end_time - start_time
    text_markdown = text_markdown + "------\n"
    # text_markdown = text_markdown + f"** 此次备份的文件的总大小{size_mb:.2f} MB({size_gb:.2f} GB)。**\n"
    # text_markdown = text_markdown + f"** 此次备份的文件的总共耗时{elapsed_time:.2f}秒。**\n"
    text_markdown = text_markdown + f"**此次备份文件的总大小< font color =\"warning\">{size_mb:.2f}</font> MB(<font color=\"warning\">{size_gb:.2f}</font> GB)。**\n"
    text_markdown = text_markdown + f"**此次备份的总共耗时<font color=\"warning\">{elapsed_time:.2f}</font>秒。**\n"
    print(text_markdown)
    wecombot.send_markdown_message(text_markdown)


if __name__ == "__main__":
    backup()
