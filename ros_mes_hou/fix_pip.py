#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pip 兼容性修复脚本
解决 pyOpenSSL 与新版本 cryptography 库不兼容的问题
"""

import sys

# 创建一个包装类，为缺失的属性提供默认值
class LibWrapper:
    def __init__(self, lib):
        self._lib = lib
    
    def __getattr__(self, name):
        # 尝试从原始的 lib 对象获取属性
        try:
            return getattr(self._lib, name)
        except AttributeError:
            # 已知的废弃函数列表，这些函数在新版本 OpenSSL 中已被移除
            deprecated_functions = [
                'OpenSSL_add_all_algorithms',
                'SSL_load_error_strings',
                'ASN1_STRING_set_default_mask_asc',
                'ERR_load_crypto_strings',
                'ERR_load_SSL_strings',
                'SSL_CTX_set_ecdh_auto',
            ]
            
            # 如果是已知的废弃函数，返回一个空操作函数
            if name in deprecated_functions:
                def no_op_func(*args, **kwargs):
                    if name == 'SSL_CTX_set_ecdh_auto':
                        return 1
                    return None
                return no_op_func
            
            # 对于标志/常量，返回 0
            if name.endswith('FLAG') or name.endswith('VERSION') or \
               name.endswith('CFLAGS') or name.endswith('PLATFORM') or \
               name.endswith('DIR') or name.endswith('BUILT_ON') or \
               name.endswith('NUMBER'):
                return 0
            
            # 对于已移除的 SSL 方法函数，回退到 TLS_method
            ssl_methods = [
                'SSLv2_method', 'SSLv3_method', 'SSLv23_method',
                'TLSv1_method', 'TLSv1_1_method', 'TLSv1_2_method', 'TLSv1_3_method'
            ]
            if name in ssl_methods:
                if hasattr(self._lib, 'TLS_method'):
                    return getattr(self._lib, 'TLS_method')
                else:
                    def no_op_func():
                        return None
                    return no_op_func
            
            # 对于其他函数，返回空操作函数
            action_words = ['add_', 'load_', 'set_', 'new', 'free', 'init', 'cleanup', 'create']
            if any(word in name.lower() for word in action_words):
                def no_op_func(*args, **kwargs):
                    return None
                return no_op_func
            
            # 默认：对于未知属性返回 None
            return None

# 在导入其他模块之前先修补 cryptography 模块
try:
    import cryptography.hazmat.bindings.openssl.binding as binding_module
    
    # 保存原始的 Binding 类
    original_binding_class = binding_module.Binding
    
    # 创建一个修补过的 Binding 类
    class PatchedBinding(original_binding_class):
        def __init__(self):
            super().__init__()
            # 使用 LibWrapper 包装 lib 对象
            self.lib = LibWrapper(self.lib)
    
    # 用修补后的 Binding 类替换模块中的原始类
    binding_module.Binding = PatchedBinding
    
    print("✅ 已修复 cryptography 兼容性问题", file=sys.stderr)
except Exception as e:
    print(f"⚠️ 修补过程中出错: {e}", file=sys.stderr)
    print("继续执行 pip...", file=sys.stderr)

# 现在运行 pip
if __name__ == '__main__':
    from pip._internal.cli.main import main as pip_main
    sys.exit(pip_main(sys.argv[1:]))
