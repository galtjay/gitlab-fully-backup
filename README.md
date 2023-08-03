# gitlab-fully-backup 
- provide a way to back up gitlab fully.
- need Python 3.7 or higher.

#### The program is based on Python 3. If you are using an older linux distribution, you can follow the steps below to install Python 3. 
#### 程序基于python3，假如你使用较老的linux发行版，可以按照下边的流程进行python3的安装。
```shell
yum -y install zlib-devel bzip2-devel openssl-devel ncurses-devel sqlite-devel readline-devel tk-devel gcc make
wget https://www.python.org/ftp/python/3.9.17/Python-3.9.17.tar.xz
tar -Jxvf Python-3.9.17.tar.xz
cd Python-3.9.17/
./configure  prefix=/usr/local/python3 
make && make install
/usr/local/python3/bin/python3   -V
```
- 配置文件：config.txt，定义企业微信hook地址，MINIO的备份桶，以及存储的周期。
- 安装依赖： pip install -r requirements.txt 
- 如何运行： /usr/local/python3/bin/python3 main.py ，使用虚拟环境也可以运行。
- 定时任务： 0 23 * * *  /usr/local/python3/bin/python3 /path/to/main.py


- Configuration File: config.txt, defines the Enterprise WeChat hook address, the backup bucket for MINIO, and the retention period.
- Install Dependencies: pip install -r requirements.txt
- How to Run: /usr/local/python3/bin/python3 main.py, you can also run it using a virtual environment.
- Scheduled Task: 0 23 * * * /usr/local/python3/bin/python3 /path/to/main.py

