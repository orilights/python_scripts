import sys
import os
import subprocess
import re

KEYTOOL_PATH = 'keytool'  # 需要安装 JDK 并正确配置环境变量，或者直接指定 keytool 路径
CERT_FP_MD5 = 'D3:5C:B4:A4:96:F9:6A:15:AF:EB:44:A4:C9:69:4F:E7:43:5E:A5:79'  # 证书指纹 MD5


def verify(apk_path):
    print('')
    print('File: ' + apk_path)
    p = subprocess.Popen(
        [KEYTOOL_PATH, '-printcert', '-jarfile', apk_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        print(f'Error: {err}')
        return

    md5 = re.search(r'MD5:  ([0-9A-F:]+)', str(out))
    if md5 is None:
        print('Error: 获取证书指纹失败, 该 APK 没有签名或使用了弱算法签名')
        return
    md5 = md5.group(1)
    print(f'Info: 证书指纹 MD5: {md5}')
    if md5 != CERT_FP_MD5:
        print('Error: 证书指纹 MD5 不匹配')
        return

    print('Info: 证书指纹 MD5 匹配')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        input_path = sys.argv[1]
    else:
        input_path = input('请输入要验证的 APK 或目录: ')

    if not os.path.exists(input_path):
        print(f'Error: {input_path} 不存在')
        sys.exit(1)

    if os.path.isdir(input_path):
        for file in os.listdir(input_path):
            if file.endswith('.apk'):
                verify(os.path.join(input_path, file))
    else:
        verify(input_path)
