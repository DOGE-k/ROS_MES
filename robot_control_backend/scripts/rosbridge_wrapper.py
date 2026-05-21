#!/usr/bin/env python3
import sys

# 创建一个包装类，为缺失的属性提供默认值
# 用于解决 pyOpenSSL 19.0.0 与新版本 cryptography 库的兼容性问题
class LibWrapper:
    def __init__(self, lib):
        self._lib = lib
    
    def __getattr__(self, name):
        # 尝试从原始的 lib 对象获取属性
        try:
            return getattr(self._lib, name)
        except AttributeError:
            # 已知的废弃函数列表，这些函数在新版本 OpenSSL 中已被移除
            废弃函数列表 = [
                'OpenSSL_add_all_algorithms',
                'SSL_load_error_strings',
                'ASN1_STRING_set_default_mask_asc',
                'ERR_load_crypto_strings',
                'ERR_load_SSL_strings',
                'SSL_CTX_set_ecdh_auto',  # 这个函数在 OpenSSL 3.0 中被移除
            ]
            
            # 如果是已知的废弃函数，返回一个空操作函数
            if name in 废弃函数列表:
                def 空操作函数(*args, **kwargs):
                    # 对于 SSL_CTX_set_ecdh_auto，返回 1 表示操作成功
                    if name == 'SSL_CTX_set_ecdh_auto':
                        return 1
                    return None
                return 空操作函数
            
            # 对于标志/常量（通常以 FLAG, VERSION, CFLAGS 等结尾），返回 0
            # 这些常量在新版本 OpenSSL 中已被移除或重命名
            if name.endswith('FLAG') or \
               name.endswith('VERSION') or \
               name.endswith('CFLAGS') or \
               name.endswith('PLATFORM') or \
               name.endswith('DIR') or \
               name.endswith('BUILT_ON') or \
               name.endswith('NUMBER'):
                return 0
            
            # 对于已移除的 SSL 方法函数，回退到 TLS_method
            # 旧版本的 SSL/TLS 方法在新版本中已被移除
            ssl方法列表 = [
                'SSLv2_method', 'SSLv3_method', 'SSLv23_method',
                'TLSv1_method', 'TLSv1_1_method', 'TLSv1_2_method', 'TLSv1_3_method'
            ]
            if name in ssl方法列表:
                # 如果有 TLS_method 可用，返回它作为替代
                if hasattr(self._lib, 'TLS_method'):
                    return getattr(self._lib, 'TLS_method')
                else:
                    def 空操作函数():
                        return None
                    return 空操作函数
            
            # 对于其他函数（通常包含 add_, load_, set_, new, free 等动作词），返回空操作函数
            动作词列表 = ['add_', 'load_', 'set_', 'new', 'free', 'init', 'cleanup', 'create']
            if any(动作词 in name.lower() for 动作词 in 动作词列表):
                def 空操作函数(*args, **kwargs):
                    return None
                return 空操作函数
            
            # 默认：对于未知属性返回 None
            return None

# 在导入其他模块之前先修补 cryptography 模块
import cryptography.hazmat.bindings.openssl.binding as 绑定模块

# 保存原始的 Binding 类
原始绑定类 = 绑定模块.Binding

# 创建一个修补过的 Binding 类
class 修补绑定类(原始绑定类):
    def __init__(self):
        super().__init__()
        # 使用 LibWrapper 包装 lib 对象
        self.lib = LibWrapper(self.lib)

# 用修补后的 Binding 类替换模块中的原始类
绑定模块.Binding = 修补绑定类

print("成功修补 cryptography 绑定模块", file=sys.stderr)

# 现在导入并运行 rosbridge_websocket
sys.path.insert(0, '/opt/ros/noetic/lib/rosbridge_server')
with open('/opt/ros/noetic/lib/rosbridge_server/rosbridge_websocket', 'r') as f:
    exec(f.read())
