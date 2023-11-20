# APK 证书指纹 MD5 验证脚本

APK 证书指纹 MD5 验证脚本，依赖 keytool 工具，需要安装 JDK，仅在 JDK 1.8.0 上测试可用

支持批量验证文件夹下的所有 APK 文件

## 使用方法

打开 py 文件，填写 KEYTOOL_PATH 与 CERT_FP_MD5 信息

然后直接运行

```bash
python ./apk_cert_verify.py <file|folder>
```
